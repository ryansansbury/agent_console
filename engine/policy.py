"""The console's policy: every tool call is decided allow, ask or deny before it runs, and the decision names its rule.

The tools turn a call into facts first (engine/tools.py): the command's words, the paths as the project sees them and
whether any escapes it, shell operators, the host, the size of a write and the length of a query. This module decides
on those facts alone, so a run, the build's replay and the visitor's browser (site/policy.js) reach the same verdict,
which the parity vectors prove.

Rules are read top to bottom and the first one that matches decides. A call no rule matches gets the policy's
"unmatched" verdict, which is deny. A rule matches when every condition it lists holds:
- tools: the kinds of call it covers (shell, read, write, edit, fetch);
- outside: true when a path escapes the project;
- paths: a path matches a pattern. A pattern without a slash matches the file's name, and one with a slash matches the
  path inside the project, where * stays inside a folder and ** crosses folders;
- commands: the command's words match a pattern's words in order. A lone * matches any number of words, and a word
  with * in it matches one word;
- operators: true when the command holds a pipe, a chain, a redirect or a substitution;
- hosts: the host matches a pattern, where * matches anything;
- max_bytes and max_query: the write is bigger, or the query longer, than the limit.
A deny from a rule marked stop ends the session.
"""
import re

UNMATCHED = "no-rule"
VIRTUAL = "/workspace"


def decide(facts, policy):
    """{"verdict", "rule", "stop"} for one call's facts."""
    for rule in policy["rules"]:
        if matches(rule, facts):
            return {"verdict": rule["verdict"], "rule": rule["id"],
                    "stop": bool(rule.get("stop")) and rule["verdict"] == "deny"}
    return {"verdict": policy.get("unmatched", "deny"), "rule": UNMATCHED, "stop": False}


def matches(rule, f):
    if "tools" in rule and f.get("tool") not in rule["tools"]:
        return False
    if "outside" in rule and bool(f.get("outside")) != bool(rule["outside"]):
        return False
    if "paths" in rule and not any(path_match(p, path) for p in rule["paths"] for path in f.get("paths") or []):
        return False
    if "commands" in rule:
        argv = f.get("argv") or []
        if not argv or not any(command_match(c, argv) for c in rule["commands"]):
            return False
    if "operators" in rule and bool(f.get("operators")) != bool(rule["operators"]):
        return False
    if "hosts" in rule:
        host = f.get("host") or ""
        if not host or not any(glob(h.lower(), host.lower()) for h in rule["hosts"]):
            return False
    if "max_bytes" in rule and not f.get("bytes", 0) > rule["max_bytes"]:
        return False
    if "max_query" in rule and not f.get("query_len", 0) > rule["max_query"]:
        return False
    return True


def glob(pattern, text, slash=False):
    """Whole-text match where * matches any run of characters. With slash=True, * stops at a slash and ** doesn't."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i) and slash:
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + ("[^/]*" if slash else ".*"), i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.fullmatch(out, text, re.S) is not None


def path_match(pattern, path):
    """A pattern without a slash is tried on the file's name, and one with a slash on the path inside the project."""
    if "/" not in pattern:
        return glob(pattern, path.rstrip("/").split("/")[-1], slash=True)
    if path == VIRTUAL or path.startswith(VIRTUAL + "/"):
        rel = path[len(VIRTUAL) + 1:]
    else:
        rel = path.lstrip("/")
    return glob(pattern, rel, slash=True)


def command_match(pattern, argv):
    return _words(pattern.split(), list(argv))


def _words(pat, words):
    if not pat:
        return not words
    if pat[0] == "*":
        return any(_words(pat[1:], words[i:]) for i in range(len(words) + 1))
    return bool(words) and glob(pat[0], words[0]) and _words(pat[1:], words[1:])


def decision_view(policy):
    """The policy without its words: what decides a call and nothing a copy edit could change. The freeze and the
    recordings' stale check hash this, so rewording a rule's label or reason never makes a run stale."""
    return {"unmatched": policy.get("unmatched", "deny"),
            "rules": [{k: v for k, v in r.items() if k not in ("label", "why")} for r in policy["rules"]]}


def rule_by_id(policy, rule_id):
    for rule in policy["rules"]:
        if rule["id"] == rule_id:
            return rule
    return None
