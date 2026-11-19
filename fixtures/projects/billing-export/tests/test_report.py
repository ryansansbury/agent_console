import unittest
from pathlib import Path

from billing.invoices import load_invoices
from billing.report import monthly_report

DATA = Path(__file__).resolve().parent.parent.joinpath("data", "invoices.json")


class MonthlyReport(unittest.TestCase):
    def setUp(self):
        self.rows = monthly_report(load_invoices(DATA))

    def test_one_row_per_account_and_month(self):
        self.assertEqual(len(self.rows), 8)

    def test_sorted_by_account_then_month(self):
        keys = [(r["account_id"], r["month"]) for r in self.rows]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(keys[:2], [("ACCT-1001", "2026-09"), ("ACCT-1001", "2026-10")])

    def test_counts_the_invoices(self):
        self.assertEqual(self.rows[0]["invoices"], 2)

    def test_sums_the_money(self):
        first = self.rows[0]
        self.assertEqual((first["subtotal_cents"], first["tax_cents"], first["total_cents"]), (57550, 4748, 62298))

    def test_months_read_year_then_month(self):
        self.assertEqual({r["month"] for r in self.rows}, {"2026-09", "2026-10"})

    def test_no_invoices_no_rows(self):
        self.assertEqual(monthly_report([]), [])


if __name__ == "__main__":
    unittest.main()
