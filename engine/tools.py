"""The console's own tools: shell, read, write, edit and fetch. Each call passes the policy before it runs.

A call goes through the same steps every time:
1. facts(): the call becomes plain facts. A command is split into words with shlex and never handed to a shell, so
   pipes, chains, redirects and substitutions show up as operators instead of doing anything. Every word after the
   program that isn't an option counts as a possible path, and every path is normalized against /workspace.
2. The policy decides (engine/policy.py), and an ask goes to the approver (engine/approvals.py), which can approve,
   decline, or leave the call waiting for a person.
3. Only an allowed or approved call acts, and the tool layer still refuses what it can't do safely, whatever the
   policy said: a path that leads outside the project once symlinks are followed, a host that isn't one of the fixture
   pages, a command it can't split. git runs with flags that skip hooks and allow only local transport.
4. The output shows /workspace instead of the real folder, has every protected value masked, and is cut to a fixed
   size with its head and tail kept.

The process runner and the web are handed in. Owner scripts pass the real ones (engine/process.run and the fixture
server), and the session's tests pass fakes, so the session never starts a program or opens a socket. Each call returns
a Result with the events for the recording, in order.
"""
import json
import shlex
import time
import urllib.parse
from pathlib import Path

from engine import policy as decide_policy
from engine.workspace import Outside, normalize

HERE = Path(__file__).resolve().parent.parent
SCHEMAS = HERE.joinpath("config", "tools.json")
KINDS = {"shell": "shell", "read_file": "read", "write_file": "write", "edit_file": "edit", "fetch_url": "fetch"}
REQUIRED = {"shell": ("command",), "read_file": ("path",), "write_file": ("path", "content"),
            "edit_file": ("path", "old", "new"), "fetch_url": ("url",)}
GIT_FLAGS = ("-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "credential.helper=",
             "-c", "protocol.allow=never", "-c", "protocol.file.allow=always", "-c", "commit.gpgsign=false",
             "-c", "core.fsmonitor=false")
OPERATOR_CHARS = set("|&;<>()")
LIMITS = {"command_seconds": 60, "output_chars": 8000}
TARGET_CHARS = 200


class Unreadable(ValueError):
    """A command the tool layer can't split into words."""


def facts(kind, args):
    """The facts the policy decides on, for one call. Pure, so a test and a run agree."""
    if kind == "shell":
        return shell_facts(args["command"])
    if kind in ("read", "write", "edit"):
        vpath, outside = normalize(args["path"])
        f = {"tool": kind, "paths": [vpath], "outside": outside}
        if kind == "write":
            f["bytes"] = len(args["content"].encode("utf-8"))
        elif kind == "edit":
            f["bytes"] = len(args["new"].encode("utf-8"))
        return f
    if kind == "fetch":
        parts = urllib.parse.urlsplit(args["url"].strip())
        host = (parts.hostname or "").rstrip(".").lower()
        return {"tool": "fetch", "url": args["url"].strip(), "scheme": parts.scheme.lower(), "host": host,
                "method": "GET", "query_len": len(parts.query)}
    raise ValueError(f"no such tool kind {kind}")


def split_words(command):
    """The command's words the way a shell would quote them, with operators as words of their own."""
    try:
        lex = shlex.shlex(command.strip(), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        words = list(lex)
    except ValueError as e:
        raise Unreadable(str(e)) from None
    if not words:
        raise Unreadable("the command is empty")
    return words


def shell_facts(command):
    raw = command.strip()
    words = split_words(raw)
    operators = any(w and set(w) <= OPERATOR_CHARS for w in words)
    operators = operators or "`" in raw or "$(" in raw or "${" in raw or any(w.startswith("$") for w in words)
    argv = [w for w in words]
    argv[0] = argv[0].rstrip("/").split("/")[-1] or argv[0]
    paths, outside = [], False
    for w in words[1:]:
        if set(w) <= OPERATOR_CHARS:
            continue
        candidate = w.split("=", 1)[1] if w.startswith("-") and "=" in w else (None if w.startswith("-") else w)
        if not candidate:
            continue
        vpath, out = normalize(candidate)
        paths.append(vpath)
        outside = outside or out
    return {"tool": "shell", "argv": argv, "operators": operators, "paths": paths, "outside": outside}


def target(kind, args):
    """A short line naming what a call touches, for the audit log and the trace."""
    text = {"shell": args.get("command"), "fetch": args.get("url")}.get(kind, args.get("path"))
    text = " ".join(str(text or "").split())
    return text if len(text) <= TARGET_CHARS else text[:TARGET_CHARS - 1] + "…"


def cap(text, limit):
    """text cut to the limit with its head and tail kept, and whether it was cut."""
    if len(text) <= limit:
        return text, False
    head, tail = int(limit * 0.65), int(limit * 0.3)
    cut = len(text) - head - tail
    return f"{text[:head]}\n[... {cut} characters cut ...]\n{text[-tail:]}", True


def schemas(names, path=None):
    """The tool schemas for a job, in the order config/tools.json lists them."""
    data = json.loads(Path(path or SCHEMAS).read_text(encoding="utf-8"))
    return [t for t in data["tools"] if t["name"] in names]


class Result(dict):
    """One call's outcome: the decision, the answer if a person was asked, what ran, the output the agent gets, and
    the events for the recording."""

    @property
    def waiting(self):
        return self.get("answer") == "wait"

    @property
    def stops(self):
        return bool(self.get("stop"))


class Tools:
    def __init__(self, ws, policy, approver, runner=None, web=None, reader=None, fixture_hosts=(), allowed=None,
                 limits=None, clock=time.time, clean=None):
        self.ws, self.policy, self.approver = ws, policy, approver
        self.runner, self.web, self.reader = runner, web, reader
        self.fixture_hosts = {h.lower() for h in fixture_hosts}
        self.allowed = set(allowed) if allowed is not None else set(KINDS)
        self.limits = dict(LIMITS, **(limits or {}))
        self.clock = clock
        # The owner's sanitizer, so the agent is given the same text the recording shows (a traceback names Python's
        # install folder, which the recording shows as python3).
        self.clean = clean or (lambda s: s)

    def labels(self):
        return {r["id"]: r["label"] for r in self.policy["rules"]}

    def call(self, name, args):
        t0 = self.clock()
        if name not in KINDS or name not in self.allowed:
            return self._result(name, args, None, t0, refused=f"there is no tool called {name} in this session")
        missing = [k for k in REQUIRED[name] if not isinstance(args.get(k), str)]
        if missing:
            return self._result(name, args, None, t0, refused=f"the call needs {', '.join(missing)} as text")
        kind = KINDS[name]
        try:
            f = facts(kind, args)
        except Unreadable as e:
            return self._result(name, args, None, t0, refused=f"the command couldn't be read ({e})")
        d = decide_policy.decide(f, self.policy)
        label = self.labels().get(d["rule"], "no rule covers this call")
        answer = None
        if d["verdict"] == "ask":
            answer = self.approver(f, d)
            if answer == "wait":
                return self._result(name, args, f, t0, d, answer=answer, output="Waiting for a person to decide.")
            if answer != "approve":
                return self._result(name, args, f, t0, d, answer=answer,
                                    output=f"A person declined this call (rule: {label}). It did not run.")
        elif d["verdict"] != "allow":
            return self._result(name, args, f, t0, d,
                                output=f"The console's policy denied this call (rule: {label}). It did not run.")
        try:
            output, extra = getattr(self, "_" + kind)(args, f)
        except Outside as e:
            return self._result(name, args, f, t0, d, answer=answer, refused=f"the tool layer refused it: {e}")
        except ToolRefusal as e:
            return self._result(name, args, f, t0, d, answer=answer, refused=f"the tool layer refused it: {e}")
        return self._result(name, args, f, t0, d, answer=answer, output=output, ran=True, **extra)

    # ------------------------------------------------------------------ the tools themselves
    def _read(self, args, f):
        path = self.ws.resolve(args["path"])
        if not path.is_file():
            return f"No file at {f['paths'][0]}.", {"exit_code": 1}
        data = path.read_bytes()
        if b"\0" in data[:4096]:
            return f"{f['paths'][0]} is a binary file of {len(data)} bytes.", {}
        return data.decode("utf-8", errors="replace"), {}

    def _write(self, args, f):
        path = self.ws.resolve(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return f"Wrote {f['bytes']} bytes to {f['paths'][0]}.", {}

    def _edit(self, args, f):
        path = self.ws.resolve(args["path"])
        if not path.is_file():
            return f"No file at {f['paths'][0]}.", {"exit_code": 1}
        text = path.read_text(encoding="utf-8")
        n = text.count(args["old"]) if args["old"] else 0
        if n != 1:
            why = "isn't in the file" if n == 0 else f"matches {n} places, so add more of the text around it"
            return f"The edit didn't run because the old text {why}.", {"exit_code": 1}
        path.write_text(text.replace(args["old"], args["new"], 1), encoding="utf-8")
        return f"Edited {f['paths'][0]}.", {}

    def _shell(self, args, f):
        if self.runner is None:
            raise ToolRefusal("this session has no process runner")
        argv = split_words(args["command"])
        if f["argv"][0] == "git":
            argv = [argv[0]] + list(GIT_FLAGS) + argv[1:]
        code, out = self.runner(argv, self.ws.real_project, self.ws.variables, self.limits["command_seconds"])
        return (out if out.strip() else f"(no output, exit code {code})"), {"exit_code": code}

    def _fetch(self, args, f):
        if f["scheme"] not in ("http", "https"):
            raise ToolRefusal("only web addresses can be fetched")
        if f["host"] not in self.fixture_hosts or self.web is None:
            raise ToolRefusal("this console reaches only its own fixture pages, and nothing else on the network")
        status, html = self.web(f["url"])
        if status != 200:
            return f"The page answered {status}.", {"exit_code": status}
        page = self.reader(html, f["url"]) if self.reader else {"given": html}
        return page["given"], {"page": page}

    # ------------------------------------------------------------------ the result and its events
    def _result(self, name, args, f, t0, d=None, answer=None, output="", ran=False, refused=None, exit_code=None,
                page=None):
        kind = KINDS.get(name, name)
        if refused:
            output = f"This call didn't run because {refused}."
        output = self.clean(self.ws.to_virtual(output))
        output, masked = self.ws.mask(output)
        output, truncated = cap(output, self.limits["output_chars"])
        r = Result(name=name, tool=kind, args=args, facts=f, verdict=(d or {}).get("verdict"),
                   rule=(d or {}).get("rule"), stop=bool((d or {}).get("stop")), answer=answer, ran=ran,
                   refused=refused, output=output, truncated=truncated, masked=masked, exit_code=exit_code,
                   ms=round((self.clock() - t0) * 1000), target=target(kind, args))
        events = [{"kind": "call", **{k: r[k] for k in ("name", "tool", "args", "facts", "verdict", "rule", "stop",
                                                          "answer", "ran", "refused", "output", "truncated",
                                                          "masked", "exit_code", "ms", "target")}}]
        if page is not None and (page.get("cuts") or page.get("hidden") or not page.get("on", True)):
            events.append({"kind": "cut", "url": f["url"], **{k: page.get(k) for k in
                                                             ("on", "raw_text", "given", "cuts", "hidden",
                                                              "invisible", "nonce")}})
        if masked:
            events.append({"kind": "masked", "target": r["target"], "count": masked})
        r["events"] = events
        return r


class ToolRefusal(Exception):
    """Something the tool layer won't do, whatever the policy said."""
