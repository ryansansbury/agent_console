"""A throwaway workspace as the tools see it: the real folder behind /workspace, and the values no agent may see.

The agent only ever sees /workspace. The tools turn its paths into real ones here, refuse any that land outside the
project once symlinks are resolved, and turn real paths in every output back into /workspace before the agent or the
recording sees them. The folder around the project (the stand-in remote and the fake home) shows as /sandbox. The
values from the files the secrets rule protects are kept here so every output can be masked. owner/workspaces.py makes
these folders and deletes them, and the session's tests build them inside .cache/tmp/.
"""
import os
import posixpath
from pathlib import Path

VIRTUAL = "/workspace"
SANDBOX = "/sandbox"
MASK = "[masked: a value from a secrets file]"


class Outside(ValueError):
    """A path the tool layer refuses, whatever the policy said."""


def normalize(path):
    """(the path as the policy sees it, whether it escapes the project). Purely textual, so a test and a run agree.
    Relative paths start at /workspace, a path starting with ~ is someone's home and so outside, and any other absolute
    path is outside unless it's under /workspace."""
    path = (path or "").strip()
    if path.startswith("~"):
        return path, True
    joined = posixpath.normpath(path if path.startswith("/") else posixpath.join(VIRTUAL, path or "."))
    if joined.startswith("//"):
        joined = "/" + joined.lstrip("/")
    inside = joined == VIRTUAL or joined.startswith(VIRTUAL + "/")
    return joined, not inside


def _forms(path):
    """A real path as macOS may print it, with and without its /private prefix."""
    path = str(path)
    out = {path}
    if path.startswith("/private/"):
        out.add(path[len("/private"):])
    elif path.startswith(("/var/", "/tmp/")):
        out.add("/private" + path)
    return out


class Workspace:
    def __init__(self, root, project=None, mask_values=(), variables=None, job=None):
        self.root = Path(root)
        self.project = Path(project) if project else self.root.joinpath("workspace")
        self.real_root = os.path.realpath(str(self.root))
        self.real_project = os.path.realpath(str(self.project))
        self.mask_values = tuple(sorted({v for v in mask_values if v}, key=len, reverse=True))
        self.variables = dict(variables or {})
        self.job = job
        self.initial_commit = None
        swaps = [(p, VIRTUAL) for p in _forms(self.real_project) | _forms(self.project)]
        swaps += [(p, SANDBOX) for p in _forms(self.real_root) | _forms(self.root)]
        self._swaps = sorted(swaps, key=lambda s: len(s[0]), reverse=True)

    def resolve(self, virtual_path):
        """The real path behind a path the policy allowed, or Outside if it lands outside the project once symlinks
        are followed."""
        vpath, outside = normalize(virtual_path)
        if outside:
            raise Outside(f"{virtual_path} is outside the project")
        rel = vpath[len(VIRTUAL):].lstrip("/")
        real = os.path.realpath(os.path.join(self.real_project, rel))
        if real != self.real_project and not real.startswith(self.real_project + os.sep):
            raise Outside(f"{virtual_path} leads outside the project")
        return Path(real)

    def to_virtual(self, text):
        """text with every real path of this workspace shown as /workspace or /sandbox."""
        for real, shown in self._swaps:
            text = text.replace(real, shown)
        return text

    def mask(self, text):
        """(text with every protected value replaced, how many were replaced)."""
        count = 0
        for value in self.mask_values:
            n = text.count(value)
            if n:
                text = text.replace(value, MASK)
                count += n
        return text, count
