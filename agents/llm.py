"""How the loop reaches a model: each vendor's native tool calling behind one call.

turn(system, messages, tools, max_tokens) returns a Reply with the text, the tool calls, the usage in one shape, the
time and the stop reason. The loop keeps its own messages and each backend translates them:

    {"role": "user", "text": ...}                                   the task
    {"role": "assistant", "text": ..., "calls": [...], "raw": ...}  a reply, with the vendor's own content kept
    {"role": "tool", "results": [{"id", "output", "error"}], "note": ...}

- AnthropicAPI calls the Messages API. Tools go out with their input_schema, replies carry tool_use blocks, and results
  go back as tool_result blocks in the next user message. The system prompt and the newest message carry a cache
  breakpoint, so each turn reads the conversation so far from the cache. A reply's own content blocks are sent back
  as they came, which keeps any thinking blocks intact.
- OpenAIChat calls Chat Completions. Tools go out as functions, replies carry tool_calls whose arguments arrive as JSON
  text, and results go back as tool messages. Arguments that aren't valid JSON come back to the loop marked, and the
  loop returns them to the model as a tool error.

Usage comes back as {"input", "cache_write", "cache_read", "output"} so engine/budget.py prices every vendor the same
way, and the vendor's own report is kept beside it. Rate limits and server errors get retries that wait 2, 6 and 18
seconds. The owner script hands
the key in, so this module never reads one, and the transport is injectable, so the session's tests never touch the
network.
"""
import json
import sys
import time
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
RETRY_STATUS = (429, 500, 502, 503, 504, 529)
TIMEOUT = 300


class ModelError(RuntimeError):
    pass


def urllib_transport(url, headers, body, timeout):
    """POST body to url. Returns (status, response bytes), an HTTP error's status and body included."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def error_text(raw):
    try:
        e = json.loads(raw).get("error") or {}
        return f"{e.get('type', '')} {e.get('message', '')}".strip()[:300]
    except (ValueError, AttributeError):
        return (raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw))[:300]


class Reply(dict):
    pass


class _Backend:
    vendor, keychain = "", ""

    def __init__(self, key, model, transport=None, sleep=time.sleep, retries=3, timeout=TIMEOUT, notify=None):
        if not key:
            raise ValueError(f"{self.vendor} needs an API key in the Keychain under {self.keychain or 'its name'}.")
        self.key, self.model = key, model
        self.transport, self.sleep, self.retries, self.timeout = transport or urllib_transport, sleep, retries, timeout
        self.notify = notify or (lambda line: print(line, file=sys.stderr, flush=True))

    def _post(self, url, headers, body):
        data = json.dumps(body).encode()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(url, headers, data, self.timeout)
            if status == 200:
                return json.loads(raw)
            if status in (401, 403):
                raise ModelError(f"{self.vendor} refused the key ({status}). Copy the key and run "
                                 f"bash owner/keys.sh --clipboard {self.vendor.lower()}")
            if status in RETRY_STATUS and attempt < self.retries:
                wait = 2 * 3 ** attempt
                self.notify(f"    {self.model}: {self.vendor} answered {status}, trying again in {wait} s")
                self.sleep(wait)
                continue
            raise ModelError(f"{self.vendor} answered {status}: {error_text(raw)}")

    def turn(self, system, messages, tools, max_tokens):
        t0 = time.time()
        reply = self._turn(system, messages, tools, max_tokens)
        reply["ms"] = round((time.time() - t0) * 1000)
        return reply


class AnthropicAPI(_Backend):
    vendor = "Anthropic"

    def __init__(self, key, model, keychain="", **kw):
        self.keychain = keychain
        super().__init__(key, model, **kw)

    def request(self, system, messages, tools, max_tokens):
        headers = {"x-api-key": self.key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": max_tokens,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
                          for t in tools],
                "messages": self.messages(messages)}
        return headers, body

    @staticmethod
    def messages(messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": [{"type": "text", "text": m["text"]}]})
            elif m["role"] == "assistant":
                content = m.get("raw") or ([{"type": "text", "text": m["text"]}] if m.get("text") else []) + [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c.get("args") or {}}
                    for c in m.get("calls", [])]
                out.append({"role": "assistant", "content": content})
            else:
                content = [{"type": "tool_result", "tool_use_id": r["id"], "content": r["output"],
                            "is_error": bool(r.get("error"))} for r in m["results"]]
                if m.get("note"):
                    content.append({"type": "text", "text": m["note"]})
                out.append({"role": "user", "content": content})
        if out and out[-1]["content"]:
            out[-1]["content"][-1] = dict(out[-1]["content"][-1], cache_control={"type": "ephemeral"})
        return out

    def _turn(self, system, messages, tools, max_tokens):
        headers, body = self.request(system, messages, tools, max_tokens)
        return parse_anthropic(self._post(ANTHROPIC_URL, headers, body))


def parse_anthropic(data):
    blocks = data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    calls = [{"id": b["id"], "name": b["name"], "args": b.get("input") or {}} for b in blocks
             if b.get("type") == "tool_use"]
    u = data.get("usage") or {}
    usage = {"input": u.get("input_tokens") or 0, "cache_write": u.get("cache_creation_input_tokens") or 0,
             "cache_read": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0}
    thinking = sum(len(b.get("thinking", "")) for b in blocks if b.get("type") == "thinking")
    raw = [b for b in blocks if b.get("type") in ("text", "tool_use", "thinking", "redacted_thinking")]
    return Reply(text=text, calls=calls, usage=usage, vendor_usage=u, stop_reason=data.get("stop_reason"),
                 model=data.get("model"), raw=raw, thinking_chars=thinking)


class OpenAIChat(_Backend):
    vendor = "OpenAI"

    def __init__(self, key, model, base_url, keychain="", token_param="max_tokens", reasoning_effort=None, **kw):
        self.keychain, self.url = keychain, base_url.rstrip("/") + "/chat/completions"
        self.token_param, self.reasoning_effort = token_param, reasoning_effort
        super().__init__(key, model, **kw)

    def request(self, system, messages, tools, max_tokens):
        headers = {"authorization": f"Bearer {self.key}", "content-type": "application/json"}
        body = {"model": self.model, "messages": [{"role": "system", "content": system}] + self.messages(messages),
                "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                            "parameters": t["input_schema"]}} for t in tools],
                self.token_param: max_tokens}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return headers, body

    @staticmethod
    def messages(messages):
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                msg = {"role": "assistant", "content": m.get("text") or None}
                if m.get("calls"):
                    msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                          "function": {"name": c["name"],
                                                       "arguments": c.get("raw_args") or json.dumps(c.get("args") or {})}}
                                         for c in m["calls"]]
                out.append(msg)
            else:
                out += [{"role": "tool", "tool_call_id": r["id"], "content": r["output"]} for r in m["results"]]
                if m.get("note"):
                    out.append({"role": "user", "content": m["note"]})
        return out

    def _turn(self, system, messages, tools, max_tokens):
        headers, body = self.request(system, messages, tools, max_tokens)
        return parse_openai(self._post(self.url, headers, body))


def parse_openai(data):
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    calls = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        raw_args = fn.get("arguments") or "{}"
        try:
            args, bad = json.loads(raw_args), None
            if not isinstance(args, dict):
                args, bad = {}, raw_args
        except ValueError:
            args, bad = {}, raw_args
        call = {"id": c.get("id"), "name": fn.get("name"), "args": args, "raw_args": raw_args}
        if bad is not None:
            call["bad_args"] = bad
        calls.append(call)
    u = data.get("usage") or {}
    prompt, completion, total = u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0, u.get("total_tokens")
    if total and total > prompt + completion:
        completion = total - prompt
    cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    usage = {"input": prompt - cached, "cache_write": 0, "cache_read": cached, "output": completion}
    return Reply(text=msg.get("content") or "", calls=calls, usage=usage, vendor_usage=u,
                 stop_reason=choice.get("finish_reason"), model=data.get("model"), raw=None, thinking_chars=0)


def backend_for(entry, key, **kw):
    """The backend for one entry of config/models.json, with the key the owner script read from the Keychain."""
    if entry["via"] == "anthropic":
        return AnthropicAPI(key, entry["model"], keychain=entry.get("keychain", ""), **kw)
    if entry["via"] == "openai":
        return OpenAIChat(key, entry["model"], entry["base_url"], keychain=entry.get("keychain", ""),
                          token_param=entry.get("token_param", "max_tokens"),
                          reasoning_effort=entry.get("reasoning_effort"), **kw)
    raise ValueError(f"no backend for {entry['via']}")
