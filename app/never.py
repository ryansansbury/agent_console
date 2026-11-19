"""Words that must never ship, and the scan that enforces it.

Four lists. The never list comes from tools/lint_copy.py's NEVER tuple and reference/private_words.txt (a line written
rot13:... is decoded first), and neither file ships. The foreign list, config/foreign_words.txt, holds the other demos'
companies and people, since each project stands alone. The avoid list, config/avoid.txt, holds the real companies in
the vendors' field, so no page or recording names one. It never ships, like the foreign lists, and an "avoid" entry
in config/names.json is read when the file isn't there. A match is a whole
word or phrase without regard to case, so "cat" never matches "category."

The first-names list, config/foreign_first_names.txt, holds the first names the earlier casts already use. It checks
this build's own names in the cast test, never its prose, since ordinary words like "mark" are on it.
"""
import codecs
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
NAMES = HERE.joinpath("config", "names.json")
AVOID = HERE.joinpath("config", "avoid.txt")


def words(private=None, tool=None):
    out = []
    private = Path(private or HERE.joinpath("reference", "private_words.txt"))
    if private.exists():
        for line in private.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(codecs.decode(line[6:], "rot13").lower() if line.startswith("rot13:") else line.lower())
    tool = Path(tool or HERE.joinpath("tools", "lint_copy.py"))
    if tool.exists():
        spec = importlib.util.spec_from_file_location("lint_copy_never", str(tool))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out += [w.lower() for w in getattr(mod, "NEVER", ())]
    return tuple(dict.fromkeys(out))


def _list(path):
    path = Path(path)
    if not path.exists():
        return ()
    return tuple(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.strip().startswith("#"))


def foreign(path=None):
    return _list(path or HERE.joinpath("config", "foreign_words.txt"))


def first_names(path=None):
    return _list(path or HERE.joinpath("config", "foreign_first_names.txt"))


def names(path=None):
    """The cleared cast from config/names.json, or None until the file exists."""
    path = Path(path or NAMES)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def avoid(path=None):
    """The real companies to keep out of everything: config/avoid.txt (one a line, # for notes), or the "avoid" entry
    of a names file when that's the path given or the text file isn't there."""
    path = Path(path) if path else (AVOID if AVOID.exists() else NAMES)
    if path.suffix == ".txt":
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return tuple(w.strip().lower() for w in lines if w.strip() and not w.strip().startswith("#"))
    cast = names(path)
    return tuple(w.strip().lower() for w in (cast or {}).get("avoid", ()) if w.strip())


def taken_words(cast_names, taken=None):
    """The words in this build's names that an earlier cast already uses as a first name."""
    taken = set(first_names() if taken is None else taken)
    out = []
    for name in cast_names:
        out += [w for w in re.findall(r"[a-z]+", name.lower()) if w in taken]
    return list(dict.fromkeys(out))


def pattern(word_list):
    parts = [r"\b" + re.escape(w).replace(r"\ ", r"\s+") + r"\b" for w in word_list]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def hits(text, word_list):
    pat = pattern(word_list)
    if not pat:
        return []
    return list(dict.fromkeys(m.group(0).lower() for m in pat.finditer(text)))


def scan(paths, never_words=None, foreign_words=None, avoid_words=None):
    """A line per file that holds a never-word, another demo's name or a real company from the avoid list. The
    never-words themselves are never printed."""
    never_words = words() if never_words is None else never_words
    foreign_words = foreign() if foreign_words is None else foreign_words
    avoid_words = avoid() if avoid_words is None else avoid_words
    problems = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        n, f, a = hits(text, never_words), hits(text, foreign_words), hits(text, avoid_words)
        if n:
            problems.append(f"{path.name} holds {len(n)} word(s) from the never list")
        if f:
            problems.append(f"{path.name} names another demo's company or person: {', '.join(f)}")
        if a:
            problems.append(f"{path.name} names a real company from the avoid list: {', '.join(a)}")
    return problems
