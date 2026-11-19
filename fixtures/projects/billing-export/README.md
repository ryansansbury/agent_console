# billing

The billing module behind the finance team's monthly numbers. It reads the invoices the billing system exports
(`data/invoices.json`) and builds the monthly report: one row per account and month with the invoice count, the
subtotal, the tax and the total.

Money stays in whole cents everywhere, and tax is rounded half up once per invoice.

```python
from billing.invoices import load_invoices
from billing.report import monthly_report

rows = monthly_report(load_invoices("data/invoices.json"))
```

## Tests

```
python3 -m unittest
```
