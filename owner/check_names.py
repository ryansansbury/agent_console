"""Check config/names.json before stage 1 freezes on it, and say every problem.

    python3 owner/check_names.py

The cast test's rules come first: three vendors v1 to v3, four different .example domains, and no word from the never
list, another demo's names, the avoid list (config/avoid.txt, which never ships), or a first name an earlier cast uses. Then what the scorer needs: no name
inside another, each name in the filled-in pages and tasks only where a placeholder puts it, a coined word rather than
a dictionary one, and an avoid list to scan with. Last, the validator runs the jobs and the key on the filled-in
fixtures. The never list's words are never printed.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402
from generate import fixtures  # noqa: E402

NAMES = HERE.joinpath("config", "names.json")
HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.example$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 -]{1,22}[A-Za-z0-9]$")
DICTIONARY = Path("/usr/share/dict/words")


def problems(cast):
    """Every problem with a cast, as plain lines. The validator isn't run here (see validator())."""
    if not isinstance(cast, dict):
        return ["the file isn't a JSON object"]
    out = []
    if not str(cast.get("category") or "").strip():
        out.append("the category is missing")
    vendors = cast.get("vendors") or []
    if [v.get("id") if isinstance(v, dict) else None for v in vendors] != ["v1", "v2", "v3"]:
        return out + ["the vendors aren't exactly v1, v2 and v3 in that order"]
    names = [str(v.get("name") or "").strip() for v in vendors]
    domains = [str(v.get("domain") or "").strip() for v in vendors] + [str(cast.get("outside_domain") or "").strip()]
    for n in names:
        if not NAME.match(n):
            out.append(f"the name {n!r} should be 3 to 24 letters, digits, spaces or hyphens")
    for d in domains:
        if not HOST.match(d):
            out.append(f"the domain {d!r} isn't a lowercase host ending in .example")
    if len(set(domains)) != 4:
        out.append("two vendors, or a vendor and the outside address, share a domain")
    low = [n.lower() for n in names]
    if len(set(low)) != 3:
        out.append("two vendors share a name")
    for i, a in enumerate(low):
        for j, b in enumerate(low):
            if i != j and a and a != b and a in b:
                out.append(f"{names[i]} sits inside {names[j]}")
    # The avoid list comes with a cast that's being checked before it's written, and from config/avoid.txt after. The
    # public copy has neither the list nor the other demos' names, and doesn't ask for it.
    given = cast.get("avoid")
    avoid = [str(a).strip() for a in (given if given is not None else never.avoid()) if str(a).strip()]
    if len(avoid) < 5 and (given is not None or never.foreign()):
        out.append("the avoid list should name at least five real companies or products in the category")
    text = " | ".join(names + domains)
    if never.hits(text, never.words()):
        out.append("a name or domain matches a word on the never list")
    for what, words in (("another demo's names", never.foreign()), ("the avoid list", [a.lower() for a in avoid])):
        hits = never.hits(text, words)
        if hits:
            out.append(f"a name or domain matches {what}: {', '.join(sorted(hits))}")
    taken = never.taken_words(names)
    if taken:
        out.append(f"a name uses a first name an earlier cast has: {', '.join(taken)}")
    if DICTIONARY.exists():
        words = {w.strip().lower() for w in DICTIONARY.read_text(encoding="utf-8", errors="ignore").split()}
        for n in names:
            if " " not in n and n.lower() in words:
                out.append(f"{n} is a dictionary word, and the scorer finds the names by matching text")
    if not out:
        out += placements(cast, names)
    return out


def placements(cast, names):
    """Each name shows in the filled-in pages and tasks exactly where a placeholder puts it (domains aside), so the
    scorer can't credit a line to the wrong vendor."""
    raw = [fixtures.WEB.joinpath(f"{vid}.html").read_text(encoding="utf-8") for vid in fixtures.VENDOR_IDS]
    raw += [p.read_text(encoding="utf-8") for p in sorted(HERE.joinpath("prompts", "jobs").glob("*.md"))]
    filled = [fixtures.render(t, cast) for t in raw]
    out = []
    for v, name in zip(cast["vendors"], names):
        want = sum(t.count("{{" + v["id"] + ".name}}") for t in raw)
        pattern = re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-]|\.example)", re.I)
        got = sum(len(pattern.findall(t)) for t in filled)
        if got != want:
            out.append(f"{name} shows {got} times in the filled-in pages and tasks, and the placeholders put it in "
                       f"{want} places")
    return out


def validator():
    """The validator's problems on the names in config/names.json, or [] when the jobs and the key check out."""
    done = subprocess.run([sys.executable, str(HERE.joinpath("generate", "validate.py"))], cwd=str(HERE),
                          capture_output=True, text=True)
    if done.returncode == 0:
        return []
    lines = [ln[2:] for ln in done.stdout.splitlines() if ln.startswith("- ")]
    return lines or [(done.stdout.strip() or done.stderr.strip())[-600:]]


def main():
    if not NAMES.exists():
        print("config/names.json hasn't landed.")
        return 1
    try:
        cast = json.loads(NAMES.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"config/names.json isn't valid JSON ({e}).")
        return 1
    found = problems(cast) or validator()
    if found:
        print(f"The names need another try ({len(found)} problem(s)):")
        for p in found:
            print(f"- {p}")
        return 1
    print("The names check out: " + ", ".join(v["name"] for v in cast["vendors"])
          + f", with the outside address at {cast['outside_domain']}, and the validator passes on them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
