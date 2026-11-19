"""The fixtures with their names filled in.

The vendor pages, the research task and the policy's host list are templates, since the vendors' names come from
config/names.json after their check. {{v1.name}} and {{v1.domain}} take a vendor's name and host, and
{{outside_domain}} takes the address the planted instruction asks for. Until the file lands, the preview uses
plain labels ("Vendor One" at vendor-one.example), which are marked as placeholders and never reach a recording.
"""
import json
import re
from pathlib import Path

from app import never

HERE = Path(__file__).resolve().parent.parent
WEB = HERE.joinpath("fixtures", "web")
JOBS = HERE.joinpath("config", "jobs.json")
TOKEN = re.compile(r"\{\{\s*([a-z0-9_]+)(?:\.([a-z]+))?\s*\}\}")
VENDOR_IDS = ("v1", "v2", "v3")
PLACEHOLDER = {
    "placeholder": True,
    "category": "on-call scheduling tools",
    "vendors": [{"id": "v1", "name": "Vendor One", "domain": "vendor-one.example"},
                {"id": "v2", "name": "Vendor Two", "domain": "vendor-two.example"},
                {"id": "v3", "name": "Vendor Three", "domain": "vendor-three.example"}],
    "outside_domain": "outside.example",
    "avoid": [],
}


class NoNames(SystemExit):
    pass


def names(path=None, placeholder_ok=False):
    """The cast from config/names.json, or the placeholders when allowed and the file hasn't landed."""
    cast = never.names(path)
    if cast is not None:
        return cast
    if placeholder_ok:
        return dict(PLACEHOLDER)
    raise NoNames("config/names.json hasn't landed yet. It's written after the names check.")


def render(text, cast):
    """text with every placeholder filled in. An unknown placeholder is an error, so nothing ships half filled."""
    vendors = {v["id"]: v for v in cast["vendors"]}

    def fill(m):
        key, field = m.group(1), m.group(2)
        if key in vendors and field in ("name", "domain"):
            return vendors[key][field]
        if key == "outside_domain" and field is None:
            return cast["outside_domain"]
        raise ValueError(f"unknown placeholder {m.group(0)}")

    return TOKEN.sub(fill, text)


def page(vendor_id, cast):
    return render(WEB.joinpath(f"{vendor_id}.html").read_text(encoding="utf-8"), cast)


def hosts(cast):
    """{host: vendor id} for the three vendors' pages."""
    return {v["domain"].lower(): v["id"] for v in cast["vendors"]}


def jobs():
    return json.loads(JOBS.read_text(encoding="utf-8"))


def job(job_id):
    for j in jobs()["jobs"]:
        if j["id"] == job_id:
            return j
    raise KeyError(f"no job {job_id} in config/jobs.json")


def task(job_id, cast):
    return render(HERE.joinpath(job(job_id)["task"]).read_text(encoding="utf-8"), cast).strip()


def kv_values(text, min_len=8):
    """The values in a KEY=VALUE file that are long enough to be worth masking. Shorter ones (like "logs") are
    ordinary words that would mask half of every output."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            value = line.partition("=")[2].strip()
            if len(value) >= min_len:
                out.append(value)
    return out


def canaries():
    """Every planted fake value across the jobs, which no agent should ever see."""
    out = []
    for j in jobs()["jobs"]:
        for src in j["plant"]:
            out += kv_values(HERE.joinpath(src).read_text(encoding="utf-8"))
    return sorted(set(out))
