"""The code section on How it works: the project's real source, copied into the page on every build.

An allowlist picks the folders. The planning files, the references, the recordings, the vectors and the private tools
never go in, and the never-word scan reads the code with the rest of the page. The files go to site/code.js as data
apart from the page's script, and the page loads that file only when How it works opens. Adapted from the Call
Companion's code view.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FOLDERS = ("engine", "agents", "evals", "owner", "app", "generate", "prompts", "config", "tests", "fixtures")
TOP = ("build.py", "WORDS.md", "site/policy.js", "site/audit.js", "site/app.js", "site/app.css")
SUFFIXES = (".py", ".js", ".css", ".md", ".sh", ".json", ".html", ".settings")
SKIP = ("owner/out/", "tests/vectors/", "evals/frozen.json", "config/foreign_", "config/avoid.txt", "fixtures/plant/",
        "tests/test_get_names.py", "tests/test_go_live.py")
FEATURED = ("engine/policy.py", "engine/reader.py", "engine/audit.py", "engine/tools.py", "engine/budget.py")
DEFAULT = "engine/policy.py"


def collect(root=HERE):
    """{path: text} for every file the code section shows."""
    root = Path(root)
    paths = [root.joinpath(t) for t in TOP]
    for folder in FOLDERS:
        if root.joinpath(folder).exists():
            paths += sorted(root.joinpath(folder).rglob("*"))
    files = {}
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in rel and not rel.startswith(SKIP):
            files[rel] = p.read_text(encoding="utf-8")
    return files


def write(files, path=None):
    path = Path(path or HERE.joinpath("site", "code.js"))
    path.write_text("window.ACCODE = " + json.dumps({"files": files, "default": DEFAULT},
                                                     ensure_ascii=False, separators=(",", ":")) + ";\n",
                    encoding="utf-8")
    return path.stat().st_size
