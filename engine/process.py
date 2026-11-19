"""Start a program for real: the one place the tools and the workspace maker run one.

run(argv, cwd, variables, timeout) runs argv with no shell in between, from cwd, with only the variables handed in
(nothing is inherited from the owner's own shell), no input, and a time limit. The program and anything it started are
killed together when the limit passes. It returns the exit code and the output, with errors folded in.

Only owner scripts import this module. The session's tests hand the tools a fake runner instead, so the session never
starts git or any program an agent asked for.
"""
import os
import signal
import subprocess


def run(argv, cwd, variables, timeout):
    try:
        proc = subprocess.Popen(list(argv), cwd=str(cwd), env=dict(variables), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    except FileNotFoundError:
        return 127, f"{argv[0]}: command not found\n"
    except PermissionError:
        return 126, f"{argv[0]}: permission denied\n"
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
        return 124, out.decode("utf-8", errors="replace") + f"\n[stopped after {timeout} seconds]\n"
