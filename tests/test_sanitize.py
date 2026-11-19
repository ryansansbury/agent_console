"""The sanitizer on made-up machine values: every kind of leak is replaced in the recording and caught by the scan, and
the console's own virtual paths and .example addresses pass."""
import unittest

from owner.sanitize import Sanitizer, scan_text

VALUES = {"home": "/Users/someone", "user": "someone", "host": "someones-mac.local", "host_short": "someones-mac",
          "temp": "/var/folders/ab/cdef/T", "temp_real": "/private/var/folders/ab/cdef/T",
          "build": "/Users/someone/code/agent_console", "python": "/opt/homebrew/opt/python/Frameworks/x",
          "base_python": "/opt/homebrew/opt/python/Frameworks/x"}
LISTS = {"another demo's name": ["zzqx"]}


def found(text, canaries=("fake-canary-value-123",)):
    return scan_text(text, values=VALUES, canaries=list(canaries), word_lists=LISTS)


class Replace(unittest.TestCase):
    def test_each_machine_value_is_replaced(self):
        s = Sanitizer(VALUES)
        text = ("/Users/someone/code/agent_console/build.py and /Users/someone/.zshrc on someones-mac.local "
                "by someone in /private/var/folders/ab/cdef/T/agent-console-1/workspace and "
                "/opt/homebrew/opt/python/Frameworks/x/lib/python3.13/unittest/case.py")
        out = s.text(text)
        self.assertEqual(out, "<build>/build.py and ~/.zshrc on host by owner in /tmp/agent-console-1/workspace and "
                              "python3/lib/python3.13/unittest/case.py")
        self.assertEqual(found(out), [])

    def test_pythons_real_folder_in_a_traceback_is_replaced(self):
        # Run 1's dev round: a key test that failed on import printed Python's own frames by their real path.
        values = dict(VALUES, base_real="/opt/homebrew/Cellar/python@3.15/3.15.0_1/Frameworks/Python.framework/"
                                        "Versions/3.15")
        line = f'File "{values["base_real"]}/lib/python3.15/unittest/loader.py", line 137, in loadTestsFromName'
        raw = scan_text(line, values=values, canaries=[], word_lists=LISTS)
        self.assertIn("this machine's base real path", raw)
        self.assertIn("a package manager's folder", raw)
        out = Sanitizer(values).text(line)
        self.assertEqual(out, 'File "python3/lib/python3.15/unittest/loader.py", line 137, in loadTestsFromName')
        self.assertEqual(scan_text(out, values=values, canaries=[], word_lists=LISTS), [])

    def test_nested_values_and_keys(self):
        s = Sanitizer(VALUES)
        out = s.value({"someone": ["at /Users/someone", {"k": "someones-mac"}], "n": 3})
        self.assertEqual(out, {"owner": ["at ~", {"k": "host"}], "n": 3})


class Scan(unittest.TestCase):
    def test_every_kind_is_caught(self):
        cases = {
            "this machine's home path": "cd /Users/someone",
            "this machine's user name": "hello someone",
            "this machine's host name": "on someones-mac today",
            "a local home folder": "/home/alex/notes",
            "the temporary space": "/private/var/folders/zz/",
            "a package manager's folder": "/opt/homebrew/bin/git",
            "a .local host name": "printer.local",
            "an IP address": "from 10.0.0.12",
            "an email address outside .example": "write to pat@mail.com",
            "a key-shaped string": "-".join(("sk", "ant", "abcdefghijklmnopqrstuv")),  # built here so no file holds one
            "an authorization header": "Bearer abcdefghijklmnop",
            "a Keychain name": "agent-console-openai",
            "a planted fake value": "it says fake-canary-value-123",
            "another demo's name": "the zzqx team",
        }
        for kind, text in cases.items():
            self.assertIn(kind, found(text), text)

    def test_the_consoles_own_shapes_pass(self):
        clean = ("/workspace/scripts/x.py /sandbox/home/.gitconfig 127.0.0.1:8123 agent@workspace.example "
                 "https://beta.example/pricing [masked: a value from a secrets file] python3 -m unittest")
        self.assertEqual(found(clean), [])


if __name__ == "__main__":
    unittest.main()
