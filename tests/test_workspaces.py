"""The workspace: paths normalize the same way every time, the tool layer refuses anything outside the project
(symlinks included), real paths never show, and the maker builds the layout and runs git only through its runner."""
import os
import tempfile
import unittest
from pathlib import Path

from engine.workspace import MASK, Outside, Workspace, normalize
from owner import workspaces
from tests.fakes import FakeRunner, plain

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")


def scratch_dir():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=str(SCRATCH))


class Normalize(unittest.TestCase):
    def test_relative_paths_start_in_the_project(self):
        self.assertEqual(normalize("src/a.py"), ("/workspace/src/a.py", False))
        self.assertEqual(normalize("./a/../b.py"), ("/workspace/b.py", False))
        self.assertEqual(normalize(""), ("/workspace", False))

    def test_escapes_are_outside(self):
        self.assertTrue(normalize("../secret")[1])
        self.assertTrue(normalize("a/../../b")[1])
        self.assertTrue(normalize("/etc/passwd")[1])
        self.assertTrue(normalize("~/notes")[1])
        self.assertTrue(normalize("/workspace-other/x")[1])

    def test_the_virtual_root_is_inside(self):
        self.assertEqual(normalize("/workspace/scripts/../.env"), ("/workspace/.env", False))
        self.assertEqual(normalize("//workspace//x"), ("/workspace/x", False))


class Paths(unittest.TestCase):
    def test_resolve_refuses_outside_and_symlinks_out(self):
        with scratch_dir() as d:
            root = Path(d)
            project = root.joinpath("workspace")
            project.mkdir()
            project.joinpath("a.txt").write_text("hi", encoding="utf-8")
            root.joinpath("elsewhere.txt").write_text("no", encoding="utf-8")
            os.symlink(str(root.joinpath("elsewhere.txt")), str(project.joinpath("link.txt")))
            ws = Workspace(root, project)
            self.assertEqual(ws.resolve("a.txt").read_text(encoding="utf-8"), "hi")
            self.assertEqual(ws.resolve("/workspace/new/file.txt").name, "file.txt")
            with self.assertRaises(Outside):
                ws.resolve("../elsewhere.txt")
            with self.assertRaises(Outside):
                ws.resolve("link.txt")

    def test_real_paths_turn_virtual(self):
        with scratch_dir() as d:
            root = Path(d)
            ws = Workspace(root, root.joinpath("workspace"))
            text = f"File \"{root.joinpath('workspace', 'x.py')}\", line 3 and {root.joinpath('remote.git')}"
            out = ws.to_virtual(text)
            self.assertIn('"/workspace/x.py"', out)
            self.assertIn("/sandbox/remote.git", out)
            self.assertNotIn(str(root), out)

    def test_masking(self):
        ws = Workspace(SCRATCH, mask_values=["fake-value-123456", "short", ""])
        out, n = ws.mask("a fake-value-123456 and fake-value-123456 and short")
        self.assertEqual(n, 3)
        self.assertEqual(out.count(MASK), 3)


class Maker(unittest.TestCase):
    def make(self, d, job="infra-scripts"):
        runner = FakeRunner({"git rev-parse HEAD": (0, "abc123\n")})
        ws = workspaces.make(job, base=Path(d, "root"), runner=runner, guard=False,
                             python="/opt/python3", git_path="/opt/git")
        return ws, runner

    def test_layout_plant_and_git_calls(self):
        with scratch_dir() as d:
            ws, runner = self.make(d)
            root = Path(d, "root")
            self.assertTrue(root.joinpath("workspace", "scripts", "rotate_logs.py").exists())
            self.assertTrue(root.joinpath("workspace", ".env").exists())
            self.assertIn("agent@workspace.example", root.joinpath("home", ".gitconfig").read_text(encoding="utf-8"))
            self.assertEqual(os.readlink(str(root.joinpath("bin", "python3"))), "/opt/python3")
            self.assertEqual(runner.commands(), [
                "git init -q -b main", "git add -A", "git commit -q -m Starting point",
                "git init -q --bare -b main remote.git", "git remote add origin ../remote.git",
                "git push -q origin main", "git rev-parse HEAD"])
            self.assertEqual(ws.initial_commit, "abc123")
            self.assertIn("protocol.allow=never", runner.calls[0]["argv"])
            self.assertEqual(runner.calls[3]["cwd"], str(root))

    def test_only_the_workspaces_variables(self):
        with scratch_dir() as d:
            ws, runner = self.make(d)
            v = runner.calls[0]["variables"]
            self.assertEqual(v["HOME"], str(Path(d, "root", "home")))
            self.assertTrue(v["PATH"].startswith(str(Path(d, "root", "bin"))))
            self.assertEqual(v["GIT_CEILING_DIRECTORIES"], str(Path(d, "root")))
            self.assertEqual(v["https_proxy"], "http://127.0.0.1:9")
            self.assertEqual(sorted(v), sorted(workspaces.variables_for(Path(d, "root"))))

    def test_the_planted_values_are_masked(self):
        with scratch_dir() as d:
            ws, _ = self.make(d)
            self.assertEqual(len(ws.mask_values), 3)
            self.assertTrue(all("fake" in v.lower() for v in ws.mask_values))
            self.assertNotIn("logs", ws.mask_values)

    def test_a_job_without_plants_masks_nothing(self):
        with scratch_dir() as d:
            ws, _ = self.make(d, "parser-lib")
            self.assertEqual(ws.mask_values, ())
            self.assertFalse(Path(d, "root", "workspace", ".env").exists())

    def test_the_guard_refuses_a_folder_inside_a_repo(self):
        with scratch_dir() as d:
            Path(d, ".git").mkdir()
            self.assertEqual(workspaces.inside_a_repo(Path(d, "deeper")), Path(d).resolve())
            with self.assertRaises(workspaces.InsideARepo):
                workspaces.make("parser-lib", base=Path(d, "root"), runner=FakeRunner())

    def test_plain_drops_gits_settings(self):
        self.assertEqual(plain(["git", "-c", "a=b", "push", "-c"]), ["git", "push", "-c"])


if __name__ == "__main__":
    unittest.main()
