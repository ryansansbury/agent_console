"""The sanitizer: every recording has this machine's paths, host name and user name replaced before anything is written,
and a scan proves none are left.

The recorder runs every text through Sanitizer.value() as it records, so the session files and the audit chain only
ever hold the clean form, and the chain is hashed over what gets written. The machine's own values (the home folder,
the user name, the host name, the temporary space, Python's install folders and this build folder) are read when the
run starts and never written into any file. The tools already show the agent /workspace for its project and /sandbox
for the folder around it, so most of the work is done before a model sees anything.

scan() runs at the end of every owner run, in the build and in the export. It looks for the machine's values, the
general shapes of local paths and .local host names, IP addresses other than 127.0.0.1, email addresses outside
.example, key-shaped strings and authorization headers, the Keychain names, the never list, the other demos' names,
the real companies in the avoid list, and the planted fake values, which no agent should ever have seen.
"""
import getpass
import os
import re
import socket
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from app import never  # noqa: E402
from generate import fixtures  # noqa: E402

SHAPES = [
    ("a local home folder", re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z0-9._-]+")),
    ("the temporary space", re.compile(r"/private/var/folders/|/var/folders/[A-Za-z0-9_]{2}/")),
    ("a package manager's folder", re.compile(r"/opt/homebrew/|/usr/local/Cellar/")),
    ("a .local host name", re.compile(r"\b[A-Za-z0-9-]+\.local\b")),
    ("an IP address", re.compile(r"\b(?!127\.0\.0\.1\b)(?!0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("an email address outside .example", re.compile(r"\b[\w.+-]+@(?![\w-]+(?:\.[\w-]+)*\.example\b)[\w-]+(?:\.[\w-]+)+\b")),
    ("a key-shaped string", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}|\bgh[po]_[A-Za-z0-9]{20,}")),
    ("an authorization header", re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}|x-api-key", re.I)),
    ("a Keychain name", re.compile(r"\bagent-console-(?:anthropic|openai|google)\b")),
]


def machine_values():
    """{what: value} for this machine, read now and never written down."""
    values = {"home": str(Path.home()), "user": getpass.getuser(), "host": socket.gethostname(),
              "temp": tempfile.gettempdir(), "build": str(HERE), "python": sys.prefix,
              "base_python": sys.base_prefix}
    values["temp_real"] = os.path.realpath(values["temp"])
    values["host_short"] = values["host"].split(".")[0]
    # A traceback names Python's own files by their real path (Homebrew's Cellar, say), not the prefix Python reports.
    values["python_real"] = os.path.realpath(sys.prefix)
    values["base_real"] = os.path.realpath(sys.base_prefix)
    return {k: v for k, v in values.items() if v and len(v) > 2}


class Sanitizer:
    def __init__(self, values=None):
        v = machine_values() if values is None else values
        swaps = []
        for name, shown in (("build", "<build>"), ("python", "python3"), ("base_python", "python3"),
                            ("python_real", "python3"), ("base_real", "python3"),
                            ("temp_real", "/tmp"), ("temp", "/tmp"), ("home", "~")):
            if v.get(name):
                swaps.append((v[name].rstrip("/"), shown))
        self.paths = sorted(swaps, key=lambda s: len(s[0]), reverse=True)
        self.words = [(re.compile(r"\b" + re.escape(v[k]) + r"\b", re.I), shown)
                      for k, shown in (("host", "host"), ("host_short", "host"), ("user", "owner")) if v.get(k)]
        self.values = v

    def text(self, s):
        for real, shown in self.paths:
            s = s.replace(real, shown)
        for pattern, shown in self.words:
            s = pattern.sub(shown, s)
        return s

    def value(self, obj):
        """obj with every string in it sanitized, keys included."""
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, dict):
            return {self.text(k) if isinstance(k, str) else k: self.value(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.value(v) for v in obj]
        return obj


def scan_text(text, values=None, canaries=None, word_lists=None):
    """The kinds of leak found in text, without printing the values themselves."""
    v = machine_values() if values is None else values
    found = []
    for k in ("home", "build", "temp", "temp_real", "python", "base_python", "python_real", "base_real"):
        if v.get(k) and v[k] in text:
            found.append(f"this machine's {k.replace('_', ' ')} path")
    for k in ("user", "host", "host_short"):
        if v.get(k) and re.search(r"\b" + re.escape(v[k]) + r"\b", text, re.I):
            found.append(f"this machine's {k.replace('_short', '').replace('user', 'user name').replace('host', 'host name')}")
    for what, pattern in SHAPES:
        if pattern.search(text):
            found.append(what)
    canaries = fixtures.canaries() if canaries is None else canaries
    if any(c in text for c in canaries):
        found.append("a planted fake value")
    if word_lists is None:
        word_lists = {"the never list": never.words(), "another demo's name": never.foreign(),
                      "a real company from the avoid list": never.avoid()}
    for what, words in word_lists.items():
        if never.hits(text, words):
            found.append(what)
    return list(dict.fromkeys(found))


def scan(paths, **kw):
    """One line per file that holds a leak."""
    problems = []
    for path in paths:
        path = Path(path)
        found = scan_text(path.read_text(encoding="utf-8", errors="ignore"), **kw)
        if found:
            problems.append(f"{path.relative_to(HERE) if HERE in path.parents else path.name}: {', '.join(found)}")
    return problems


def recordings():
    """Every recorded file the page or the repo can show."""
    out = []
    for folder in (HERE.joinpath("data", "runs"), HERE.joinpath("data", "dev")):
        if folder.exists():
            out += sorted(p for p in folder.rglob("*.json") if p.is_file())
    return out
