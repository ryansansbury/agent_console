import tempfile
import unittest
from pathlib import Path

from billing.export import export_csv


class Export(unittest.TestCase):
    def test_header_and_a_row(self):
        rows = [{"account_id": "ACCT-1", "month": "2026-09", "invoices": 2, "subtotal_cents": 57550,
                 "tax_cents": 4748, "total_cents": 62298}]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "report.csv")
            export_csv(rows, out)
            self.assertEqual(out.read_text(encoding="utf-8"),
                             "account_id,month,invoices,subtotal,tax,total\nACCT-1,2026-09,2,575.50,47.48,622.98\n")


if __name__ == "__main__":
    unittest.main()
