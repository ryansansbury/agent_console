"""Stand-ins for the real world in the unit tests: a runner that starts no program and a web with no network.

The unit tests never run git, a server or an agent's command, so they hand the tools these instead. The owner's
selftest runs the same calls through the real runner and the real fixture server on the owner's machine.
"""


def plain(argv):
    """argv without git's -c pairs, so answers can be keyed on what the command means."""
    out, skip = [], False
    for word in argv:
        if skip:
            skip = False
            continue
        if word == "-c" and out == ["git"]:
            skip = True
            continue
        out.append(word)
    return out


class FakeRunner:
    """Records every call and answers from a table of command prefixes, so no program ever starts."""

    def __init__(self, answers=None, default=(0, "")):
        self.calls = []
        self.answers = dict(answers or {})
        self.default = default

    def __call__(self, argv, cwd, variables, timeout):
        self.calls.append({"argv": list(argv), "cwd": str(cwd), "variables": dict(variables), "timeout": timeout})
        key = " ".join(plain(argv))
        for prefix in sorted(self.answers, key=len, reverse=True):
            if key.startswith(prefix):
                answer = self.answers[prefix]
                return answer(argv, cwd) if callable(answer) else answer
        return self.default

    def commands(self):
        return [" ".join(plain(c["argv"])) for c in self.calls]


class FakeWeb:
    """{url: (status, html)} with no network. Anything else answers 404."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.requests = []

    def __call__(self, url):
        self.requests.append(url)
        return self.pages.get(url, (404, "<html><body><p>Not found.</p></body></html>"))
