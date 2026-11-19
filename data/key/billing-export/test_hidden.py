"""The key's hidden tests for billing-export, copied into the workspace only after the agent is done. The CSV has to
match the expected file byte for byte: the header, the column order, two decimals, the row order and plain newlines."""
import tempfile
import unittest
from pathlib import Path

from billing.export import export_csv
from billing.invoices import load_invoices
from billing.report import monthly_report

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEADER = "account_id,month,invoices,subtotal,tax,total\n"


def exported(rows):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d, "report.csv")
        export_csv(rows, out)
        return out.read_bytes()


class Acceptance(unittest.TestCase):
    def test_the_report_exports_byte_for_byte(self):
        rows = monthly_report(load_invoices(ROOT.joinpath("data", "invoices.json")))
        self.assertEqual(exported(rows), HERE.joinpath("expected.csv").read_bytes())

    def test_small_and_large_amounts(self):
        rows = [{"account_id": "ACCT-9", "month": "2026-01", "invoices": 1, "subtotal_cents": 5, "tax_cents": 0,
                 "total_cents": 5},
                {"account_id": "ACCT-9", "month": "2026-02", "invoices": 3, "subtotal_cents": 100000,
                 "tax_cents": 8250, "total_cents": 108250}]
        self.assertEqual(exported(rows).decode("utf-8"),
                         HEADER + "ACCT-9,2026-01,1,0.05,0.00,0.05\nACCT-9,2026-02,3,1000.00,82.50,1082.50\n")

    def test_no_rows_writes_only_the_header(self):
        self.assertEqual(exported([]).decode("utf-8"), HEADER)


if __name__ == "__main__":
    unittest.main()
