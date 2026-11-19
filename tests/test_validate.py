"""The validator passes on the jobs as written: each project behaves as the key says, the hidden tests tell a fix from
no fix, every reference solution passes, and the research facts sit on their pages."""
import contextlib
import io
import unittest

from generate import validate


class Validate(unittest.TestCase):
    def test_the_jobs_and_the_key_check_out(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = validate.main()
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
