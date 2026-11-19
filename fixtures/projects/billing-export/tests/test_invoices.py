import unittest
from datetime import date
from pathlib import Path

from billing.invoices import Invoice, Line, load_invoices

DATA = Path(__file__).resolve().parent.parent.joinpath("data", "invoices.json")


class Invoices(unittest.TestCase):
    def setUp(self):
        self.invoices = load_invoices(DATA)

    def test_loads_every_invoice(self):
        self.assertEqual(len(self.invoices), 11)

    def test_a_line_is_quantity_times_unit(self):
        self.assertEqual(Line("Storage overage (GB)", 3, 1250).cents, 3750)

    def test_subtotal(self):
        self.assertEqual(self.invoices[0].subtotal_cents, 38550)

    def test_total_adds_the_tax(self):
        self.assertEqual(self.invoices[0].tax_cents, 3180)
        self.assertEqual(self.invoices[0].total_cents, 41730)

    def test_tax_rounds_half_up(self):
        half_a_cent = Invoice("INV-T", "ACCT-T", date(2026, 9, 1), (Line("Test", 1, 100),), 50)
        self.assertEqual(half_a_cent.tax_cents, 1)

    def test_tax_exempt_accounts_pay_no_tax(self):
        exempt = [i for i in self.invoices if i.account_id == "ACCT-1002"]
        self.assertEqual([i.tax_cents for i in exempt], [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
