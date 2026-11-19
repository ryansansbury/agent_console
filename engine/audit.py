"""The audit log: every event in a chain where each entry carries the hash of the one before it.

An entry holds only text and whole numbers: seq, at, session, actor, action, target, verdict, rule, result (the start
of the output's hash), prev and hash. Its hash is SHA-256 over prev, a newline, and the entry's canonical JSON without
the hash itself (keys sorted, no spaces, UTF-8 as it is, text normalized to NFC, and no floats, which two languages
could print differently). So changing any old entry breaks its own hash, fixing that hash breaks the next entry's link,
and rewriting everything after it still leaves a head that no longer matches the one published elsewhere.

verify() returns the first entry that fails and why. site/audit.js does the same in the visitor's browser with its own
SHA-256, and the parity vectors prove the two agree on every canonical string and hash. One chain covers a recorded
morning, where the four sessions append under one lock in the order things happened.
"""
import hashlib
import json
import threading
import unicodedata

GENESIS = "0" * 64
FIELDS = ("seq", "at", "session", "actor", "action", "target", "verdict", "rule", "result", "prev")


def _clean(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError(f"an audit entry holds only text and whole numbers, not {type(value).__name__}")
    if isinstance(value, str):
        value = unicodedata.normalize("NFC", value)
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("an audit entry can't hold a lone surrogate")
    return value


def canonical(entry):
    body = {k: _clean(v) for k, v in entry.items() if k != "hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(entry):
    return hashlib.sha256((entry["prev"] + "\n" + canonical(entry)).encode("utf-8")).hexdigest()


def digest(text):
    """The first 16 hex digits of a text's SHA-256, for the result field."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16] if text else ""


class Chain:
    def __init__(self, entries=None):
        self.entries = list(entries or [])
        self._lock = threading.Lock()

    def append(self, **fields):
        with self._lock:
            entry = {k: _clean(fields.get(k, "")) for k in FIELDS if k not in ("seq", "prev")}
            entry["seq"] = len(self.entries) + 1
            entry["prev"] = self.entries[-1]["hash"] if self.entries else GENESIS
            entry["hash"] = entry_hash(entry)
            self.entries.append(entry)
            return entry

    def head(self):
        return self.entries[-1]["hash"] if self.entries else GENESIS


def verify(entries, head=None):
    """{"ok", "count", "failed_at", "why"}: the first entry whose number, link or content fails, or the last entry when
    the chain holds together but its head isn't the published one."""
    for i, e in enumerate(entries):
        if e.get("seq") != i + 1:
            return {"ok": False, "count": len(entries), "failed_at": e.get("seq"), "why": "sequence"}
        if e.get("prev") != (entries[i - 1]["hash"] if i else GENESIS):
            return {"ok": False, "count": len(entries), "failed_at": e["seq"], "why": "link"}
        try:
            good = entry_hash(e) == e.get("hash")
        except (TypeError, ValueError):
            good = False
        if not good:
            return {"ok": False, "count": len(entries), "failed_at": e["seq"], "why": "content"}
    if head and entries and entries[-1]["hash"] != head:
        return {"ok": False, "count": len(entries), "failed_at": entries[-1]["seq"], "why": "head"}
    return {"ok": True, "count": len(entries), "failed_at": None, "why": None}
