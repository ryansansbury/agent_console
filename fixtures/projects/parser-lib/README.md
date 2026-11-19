# dateparse

Turns the dates people type into forms into `datetime.date` values.

```python
from dateparse import parse_date

parse_date("2026-11-09")        # date(2026, 11, 9)
parse_date("Nov 9, 2026")       # date(2026, 11, 9)
parse_date("tomorrow", today=date(2026, 11, 9))   # date(2026, 11, 10)
```

## What it accepts

- ISO dates: `2026-11-09`, `2026-3-9`
- US numeric dates, month first: `11/9/2026`, `03/09/2026`, and two-digit years like `3/9/26`. Two-digit years follow
  the usual convention: 69 to 99 mean 1969 to 1999, and 00 to 68 mean 2000 to 2068.
- Month names, full or short, before or after the day: `November 9, 2026`, `Nov 9 2026`, `9 November 2026`. Short
  names may end in a period (`Sept. 9, 2026`), and September also goes by `Sept`.
- Days with ordinal suffixes: `March 3rd, 2026`, `21st June 2026`.
- An optional weekday in front: `Mon, Nov 9, 2026`.
- `today`, `tomorrow` and `yesterday`, counted from the `today` argument.

Anything else raises `ValueError`, and so does a date that doesn't exist (`Feb 29, 2026`).

## Tests

```
python3 -m unittest
```
