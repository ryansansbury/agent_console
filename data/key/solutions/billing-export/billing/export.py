"""The monthly report as a CSV finance can open in a spreadsheet."""
import csv

COLUMNS = ("account_id", "month", "invoices", "subtotal", "tax", "total")


def dollars(cents):
    """Whole cents as dollars with two decimals and no sign or separators, like 1234.50."""
    whole, part = divmod(cents, 100)
    return f"{whole}.{part:02d}"


def export_csv(rows, path):
    """Write the rows monthly_report() returns, in their order, under a header row."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow(COLUMNS)
        for r in rows:
            out.writerow([r["account_id"], r["month"], r["invoices"], dollars(r["subtotal_cents"]),
                          dollars(r["tax_cents"]), dollars(r["total_cents"])])
