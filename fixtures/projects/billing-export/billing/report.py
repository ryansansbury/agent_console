"""The monthly report: one row per account and month, the way finance reads it."""
from collections import defaultdict


def monthly_report(invoices):
    """Rows sorted by account and then month, each with the invoice count and the money in cents."""
    groups = defaultdict(list)
    for inv in invoices:
        groups[(inv.account_id, inv.issued.strftime("%Y-%m"))].append(inv)
    rows = []
    for (account_id, month), invs in sorted(groups.items()):
        rows.append({
            "account_id": account_id,
            "month": month,
            "invoices": len(invs),
            "subtotal_cents": sum(i.subtotal_cents for i in invs),
            "tax_cents": sum(i.tax_cents for i in invs),
            "total_cents": sum(i.total_cents for i in invs),
        })
    return rows
