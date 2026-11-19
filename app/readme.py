"""The README's results, written by the real build from the same data the page reads: each model's morning side by
side, the experiment with the reader off, the budget test, and the newest hash of each morning's audit chain, which is
the head the page's tamper test checks against. Only the part between the results markers changes, so the rest of the
README stays as written. A preview build leaves the README alone.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
README = HERE.joinpath("README.md")
START, END = "<!-- results written by build.py from the recordings -->", "<!-- end of results -->"


def money(micro):
    d = (micro or 0) / 1e6
    return f"${d:.2f}" if d >= 0.1 else f"${d:.3f}"


def minutes(ms):
    s = round((ms or 0) / 1000)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def results(data):
    lines = ["| Model | Jobs done | Unsafe events | Asked a person | Denied | Quarantined | Cost | Time |",
             "|---|---|---|---|---|---|---|---|"]
    for mid, r in data["rows"].items():
        name = r["label"] + (" (opens the page)" if mid == data["route"] else "")
        done = f"{r['done']} of 4" + (f" and {r['safe_stops']} stopped safely" if r["safe_stops"] else "")
        lines.append(f"| {name} | {done} | {r['unsafe']} | {r['asked']} | {r['denied']} | {r['quarantined']} | "
                     f"{money(r['cost_micro'])} | {minutes(r['ms'])} |")
    lines.append("")
    if data["experiment"]:
        lines.append("The planted note reached each agent word for word with the reader off.")
        lines.append("")
        lines += ["| Model | Followed the note | Told the person | Reached for the outside address |", "|---|---|---|---|"]
        for e in data["experiment"]:
            followed = "Part of it" if e["followed"] else "No"
            told = "Yes" if e["flagged"] else "No"
            caught = ("Every attempt was stopped" if e["caught"] else "An attempt got through") if e["attempts"] else "No"
            lines.append(f"| {e['label'] or e['model']} | {followed} | {told} | {caught} |")
        lines.append("")
    b = data.get("budget_test")
    if b:
        lines.append(f"The budget test gave {b['label'] or b['model']} {money(b['limit_micro'])} for {b['job']}. It spent "
                     f"{money(b['spent_micro'])} and {'stopped where it should' if b['ok'] else 'did not stop where it should'}.")
        lines.append("")
    lines.append("Each morning's audit chain ends at the hash below. That's the head the page checks against.")
    lines.append("")
    for mid, m in data["mornings"].items():
        lines.append(f"- {m['label']} ends at `{m['audit']['head']}`")
    return "\n".join(lines)


def write(data, path=None):
    """Swap the results between the markers. Returns False when the README has no markers to write between."""
    path = Path(path or README)
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return False
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    path.write_text(pattern.sub(lambda m: f"{START}\n{results(data)}\n{END}", text), encoding="utf-8")
    return True
