"""One loop for every model, and the session it records.

run() sends the task, lets the model call tools, runs each call through the console's tools (the policy first), and
sends the results back, until the model replies without calling a tool or something ends the session:

    done             the model replied without a tool call
    waiting          a call waits for a person (the push)
    stopped-denial   a deny under a rule marked stop (the secrets file)
    stopped-budget   the next call could pass the session's budget
    step-cap, turn-cap, time-cap   40 tool calls, 30 model calls or 15 minutes
    error            the model's API failed after its retries

A reply with several tool calls runs them in order, and the session ends at the first that stops or waits. A reply cut
off at its length limit runs none of its calls, since their arguments may be cut too (a write would save half a file).

Before every model call the budget checks the estimated input and caps the reply (engine/budget.py). The warning comes
once. When the money left pays for this reply and not much more, a note goes with this call, so the agent hears it
while it can still answer. When spending passes 80% first, the note rides along with the next tool results.

Session records every event with its time, and writes the audit entries for it into the morning's chain. Each text
passes the sanitizer it was handed before it's stored or hashed, so nothing raw is kept and the chain is hashed over
what gets written.
"""
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from engine import audit

PACIFIC = ZoneInfo("America/Los_Angeles")
WARN_NOTE = "[console] This session has spent 80% of its budget."
LAST_NOTE = "[console] The money left in this session's budget pays for this reply and not much more."
CUT_REASONS = ("max_tokens", "length")
CUT_OUTPUT = ("This call didn't run because the reply was cut off at its length limit, and its arguments may be cut "
              "too.")
STATES = ("done", "waiting", "stopped-denial", "stopped-budget", "step-cap", "turn-cap", "time-cap", "error")


def estimate_tokens(obj):
    """A deliberately high token count for text or JSON: a character in three, so the budget errs on the safe side."""
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return len(text) // 3 + 1


class Session:
    def __init__(self, job, model, run, settings, task, chain=None, clean=None, clock=time.time, offset_ms=0):
        self.job, self.model, self.run, self.settings, self.task = job, model, run, settings, task
        self.chain = chain if chain is not None else audit.Chain()
        self.clean = clean or (lambda value: value)
        self.clock, self.t0, self.offset_ms = clock, clock(), offset_ms
        self.events, self.end_state, self.totals = [], None, {"cost_micro": 0, "tool_calls": 0, "model_calls": 0,
                                                              "input_tokens": 0, "output_tokens": 0}
        self.recorded = datetime.fromtimestamp(self.t0, PACIFIC).isoformat(timespec="seconds")
        self._audit("console", "start", f"{job} with {model.get('label', model.get('id'))}")

    def _now(self):
        return datetime.fromtimestamp(self.clock(), PACIFIC).isoformat(timespec="seconds")

    def _audit(self, actor, action, target, verdict="", rule="", result=""):
        entry = self.chain.append(at=self._now(), session=self.job, actor=actor, action=action,
                                  target=self.clean(str(target or "")), verdict=verdict or "", rule=rule or "",
                                  result=result or "")
        return entry["seq"]

    def _event(self, kind, audit_seqs=(), **fields):
        event = self.clean(dict(fields))
        event.update(seq=len(self.events) + 1, t_ms=round((self.clock() - self.t0) * 1000), kind=kind,
                     audit=list(audit_seqs))
        self.events.append(event)
        return event

    def model_call(self, reply, cost_micro):
        u = reply["usage"]
        self.totals["cost_micro"] += cost_micro
        self.totals["model_calls"] += 1
        self.totals["input_tokens"] += u["input"] + u["cache_write"] + u["cache_read"]
        self.totals["output_tokens"] += u["output"]
        return self._event("model", text=reply["text"], calls=[{k: c.get(k) for k in ("id", "name", "args")}
                                                               for c in reply["calls"]],
                           usage=u, cost_micro=cost_micro, ms=reply.get("ms", 0), stop_reason=reply.get("stop_reason"),
                           served_by=reply.get("model"), thinking_chars=reply.get("thinking_chars", 0))

    def call(self, call_id, result):
        self.totals["tool_calls"] += 1
        out = []
        for ev in result["events"]:
            seqs = []
            if ev["kind"] == "call":
                verdict = ev["verdict"] or "refused"
                rule = ev["rule"] or "tool-layer"
                seqs.append(self._audit("agent", ev["tool"], ev["target"], verdict, rule,
                                        audit.digest(self.clean(ev["output"])) if ev["ran"] else ""))
                if ev.get("answer"):
                    seqs.append(self._audit("script", "answer", ev["target"], ev["answer"], ev["rule"]))
                if ev.get("refused") and ev["verdict"] == "allow":
                    seqs.append(self._audit("console", "refuse", ev["target"], "refused", "tool-layer"))
            elif ev["kind"] == "cut" and ev.get("cuts"):
                seqs.append(self._audit("reader", "cut", ev["url"], "quarantine", "reader",
                                        audit.digest(" ".join(c["text"] for c in ev["cuts"]))))
            elif ev["kind"] == "masked":
                seqs.append(self._audit("console", "mask", ev["target"], "masked", "secrets"))
            out.append(self._event(ev["kind"], seqs, call_id=call_id, **{k: v for k, v in ev.items() if k != "kind"}))
        return out

    def budget(self, level, spent, limit, reason=None):
        """A budget note. A warning's reason is "last" when it went with the last reply the money paid for, and
        "share" when spending passed 80% first."""
        target = f"{spent} of {limit} micro-dollars" + (", the last reply" if reason == "last" else "")
        seq = self._audit("budget", level, target, level, "budget")
        return self._event("budget", [seq], level=level, reason=reason, spent_micro=spent, limit_micro=limit)

    def end(self, state, detail="", reply=""):
        seq = self._audit("console", "end", state)
        self.end_state = {"state": state, "detail": self.clean(detail), "reply": self.clean(reply or "")}
        self._event("end", [seq], state=state, detail=detail, reply=reply or "")
        self.totals["ms"] = round((self.clock() - self.t0) * 1000)
        return state

    def record(self):
        return {"schema": 1, "job": self.job, "run": self.run, "model": self.model, "recorded": self.recorded,
                "offset_ms": self.offset_ms, "settings": self.settings, "task": self.clean(self.task),
                "events": self.events, "end": self.end_state, "totals": self.totals}


def with_note(message, note):
    """The message the next call sends, with the console's note added: beside the tool results, or after the task when
    it's the first call."""
    if message["role"] == "tool":
        return dict(message, note=note)
    return dict(message, text=message["text"] + "\n\n" + note)


def run(backend, system, task, schemas, tools, budget, session, limits, clock=time.time):
    messages = [{"role": "user", "text": task}]
    estimate = estimate_tokens(system) + estimate_tokens(schemas) + estimate_tokens(task)
    t0, note, steps = clock(), None, 0
    while True:
        if session.totals["model_calls"] >= limits["model_calls"]:
            return session.end("turn-cap", f"the session reached its limit of {limits['model_calls']} model calls")
        if clock() - t0 > limits["minutes"] * 60:
            return session.end("time-cap", f"the session reached its limit of {limits['minutes']} minutes")
        # The estimate holds room for the last-reply note whenever it could still go with this call.
        go, max_tokens, last = budget.before(estimate + (0 if budget.warned else estimate_tokens(LAST_NOTE)))
        if not go:
            session.budget("stop", budget.spent, budget.limit)
            return session.end("stopped-budget", "the next call could pass the session's budget")
        if last:
            session.budget("warn", budget.spent, budget.limit, reason="last")
            messages[-1] = with_note(messages[-1], LAST_NOTE)
        try:
            reply = backend.turn(system, messages, schemas, max_tokens)
        except Exception as e:  # the model layer already retried, so any failure ends the session
            return session.end("error", f"{type(e).__name__}: {e}")
        cost, warn = budget.after(reply["usage"])
        session.model_call(reply, cost)
        if warn:
            session.budget("warn", budget.spent, budget.limit, reason="share")
            note = WARN_NOTE
        u = reply["usage"]
        estimate = u["input"] + u["cache_write"] + u["cache_read"] + u["output"]
        messages.append({"role": "assistant", "text": reply["text"], "calls": reply["calls"], "raw": reply.get("raw")})
        if not reply["calls"]:
            return session.end("done", reply=reply["text"])
        results, ended = [], None
        cut = reply.get("stop_reason") in CUT_REASONS
        for c in reply["calls"]:
            if steps >= limits["tool_calls"]:
                ended = ("step-cap", f"the session reached its limit of {limits['tool_calls']} tool calls")
                break
            if cut:
                results.append({"id": c["id"], "output": CUT_OUTPUT, "error": True})
                raw = c.get("bad_args") if c.get("bad_args") is not None else json.dumps(c.get("args") or {})
                session._event("bad-call", call_id=c["id"], name=c.get("name"), reason="cut", raw_args=raw[:500])
                continue
            if c.get("bad_args") is not None:
                output = "This call didn't run because its arguments weren't valid JSON."
                results.append({"id": c["id"], "output": output, "error": True})
                session._event("bad-call", call_id=c["id"], name=c.get("name"), reason="json",
                               raw_args=c["bad_args"][:500])
                continue
            r = tools.call(c["name"], c.get("args") or {})
            steps += 1
            session.call(c["id"], r)
            results.append({"id": c["id"], "output": r["output"], "error": not r["ran"]})
            if r.stops:
                ended = ("stopped-denial", f"a call was denied under the rule {r['rule']}, which ends the session")
                break
            if r.waiting:
                ended = ("waiting", "a call is waiting for a person")
                break
        if ended:
            return session.end(*ended)
        messages.append({"role": "tool", "results": results, "note": note})
        estimate += sum(estimate_tokens(r["output"]) for r in results) + (estimate_tokens(note) if note else 0)
        note = None
