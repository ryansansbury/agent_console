"""Invoices from the billing system's export, with their money in whole cents so nothing rounds twice."""
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_cents: int

    @property
    def cents(self):
        return self.quantity * self.unit_cents


@dataclass(frozen=True)
class Invoice:
    id: str
    account_id: str
    issued: date
    lines: tuple
    tax_rate_bp: int  # basis points, so 825 means 8.25%

    @property
    def subtotal_cents(self):
        return sum(line.cents for line in self.lines)

    @property
    def tax_cents(self):
        """Tax on the whole invoice, rounded half up to the cent."""
        return (self.subtotal_cents * self.tax_rate_bp + 5000) // 10000

    @property
    def total_cents(self):
        return self.subtotal_cents + self.tax_cents


def load_invoices(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Invoice(
            id=item["id"],
            account_id=item["account_id"],
            issued=date.fromisoformat(item["issued"]),
            lines=tuple(Line(ln["description"], ln["quantity"], ln["unit_cents"]) for ln in item["lines"]),
            tax_rate_bp=item["tax_rate_bp"],
        )
        for item in data["invoices"]
    ]
