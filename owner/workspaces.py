"""Make and remove the throwaway workspaces the recorded agents work in. The owner's machine only.

Each workspace is a fresh folder in the system's temporary space, never inside a repository:

    workspace/    the project, which the agent sees as /workspace
    remote.git/   a bare repository standing in for the remote
    home/         a fake home holding only a .gitconfig for the agent's commits
    bin/          links to python3 and git, so the search path holds nothing of the owner's

The project is copied from fixtures/projects/<job>/, the job's planted files go in (the fake settings file becomes
.env), and a first commit is pushed to the bare remote. Every git command goes through the runner handed in, which is
engine/process.run in owner scripts and a fake in the session's tests, so the session never runs git.
"""
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine.workspace import Workspace  # noqa: E402
from generate import fixtures  # noqa: E402

PREFIX = "agent-console-"
FIXTURE_AUTHOR = ("-c", "user.name=Agent Console fixtures", "-c", "user.email=fixtures@workspace.example")
GIT_FLAGS = ("-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "credential.helper=",
             "-c", "protocol.allow=never", "-c", "protocol.file.allow=always", "-c", "commit.gpgsign=false",
             "-c", "core.fsmonitor=false")
GITCONFIG = ("[user]\n\tname = the agent\n\temail = agent@workspace.example\n[init]\n\tdefaultBranch = main\n"
             "[advice]\n\tdetachedHead = false\n")
CLOSED_PORT = "http://127.0.0.1:9"
MIN_MASKED = 8


class InsideARepo(SystemExit):
    pass


def inside_a_repo(path):
    """The first folder at or above path that holds a .git, or None."""
    p = Path(path).resolve()
    for folder in [p] + list(p.parents):
        if folder.joinpath(".git").exists():
            return folder
    return None


def variables_for(root):
    """The only variables a workspace's programs get: the workspace's own bin and the system's two command folders,
    the fake home, the language and time zone, git kept inside the folder with no system config and no prompts, and
    proxies pointing at a closed port so a stray network call fails at once."""
    root = Path(root)
    out = {
        "PATH": f"{root.joinpath('bin')}:/usr/bin:/bin",
        "HOME": str(root.joinpath("home")),
        "LANG": "en_US.UTF-8",
        "TZ": "America/Los_Angeles",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(root),
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "NO_PROXY": "",
    }
    for name in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        out[name] = CLOSED_PORT
    return out


def masked_values(project, planted):
    """Every value long enough to mask in the planted KEY=VALUE files (generate/fixtures.py says why)."""
    values = []
    for rel in planted:
        values += fixtures.kv_values(project.joinpath(rel).read_text(encoding="utf-8"), MIN_MASKED)
    return values


def git(runner, ws, *args, cwd=None):
    code, out = runner(("git",) + GIT_FLAGS + tuple(args), cwd or ws.project, ws.variables, 60)
    if code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed while making the workspace: {ws.to_virtual(out).strip()}")
    return out


def make(job_id, base=None, runner=None, guard=True, python=None, git_path=None):
    """A fresh workspace for the job, ready for an agent. guard=False is only for the session's tests, which build
    inside .cache/tmp/ with a fake runner."""
    job = fixtures.job(job_id)
    root = Path(base) if base else Path(tempfile.mkdtemp(prefix=PREFIX))
    if guard:
        repo = inside_a_repo(root)
        if repo is not None or str(root.resolve()).startswith(str(HERE)):
            raise InsideARepo(f"Refusing to make a workspace inside a repository ({repo or HERE}).")
    if runner is None:
        from engine import process
        runner = process.run
    project = root.joinpath("workspace")
    shutil.copytree(HERE.joinpath(job["project"]), project, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    for src, dst in job["plant"].items():
        shutil.copyfile(HERE.joinpath(src), project.joinpath(dst))
    home, bin_dir = root.joinpath("home"), root.joinpath("bin")
    home.mkdir()
    home.joinpath(".gitconfig").write_text(GITCONFIG, encoding="utf-8")
    bin_dir.mkdir()
    bin_dir.joinpath("python3").symlink_to(python or sys.executable)
    bin_dir.joinpath("git").symlink_to(git_path or shutil.which("git") or "/usr/bin/git")
    ws = Workspace(root, project, masked_values(project, job["plant"].values()), variables_for(root), job_id)
    git(runner, ws, "init", "-q", "-b", "main")
    git(runner, ws, "add", "-A")
    git(runner, ws, *FIXTURE_AUTHOR, "commit", "-q", "-m", "Starting point")
    git(runner, ws, "init", "-q", "--bare", "-b", "main", "remote.git", cwd=root)
    git(runner, ws, "remote", "add", "origin", "../remote.git")
    git(runner, ws, "push", "-q", "origin", "main")
    ws.initial_commit = git(runner, ws, "rev-parse", "HEAD").strip()
    return ws


def destroy(ws):
    shutil.rmtree(ws.root, ignore_errors=True)


def sweep(older_than_s=3600):
    """Remove workspaces a crash left behind. Only folders with this project's prefix, in the temporary space."""
    gone = 0
    for p in Path(tempfile.gettempdir()).glob(PREFIX + "*"):
        if p.is_dir() and time.time() - p.stat().st_mtime > older_than_s:
            shutil.rmtree(p, ignore_errors=True)
            gone += 1
    return gone
