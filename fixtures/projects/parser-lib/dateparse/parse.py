"""Parse the dates people type into forms.

parse_date("2026-11-09") and parse_date("Nov 9, 2026") both return date(2026, 11, 9). Relative words like "today" and
"tomorrow" count from the date passed as today, or from the real date when none is passed. README.md lists every
format it accepts.
"""
import re
from datetime import date, timedelta

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
WEEKDAYS = {"mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday", "thu", "thur", "thurs", "thursday",
            "fri", "friday", "sat", "saturday", "sun", "sunday"}
RELATIVE = {"today": 0, "tomorrow": 1, "yesterday": -1}

ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
NUMERIC = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$")


def parse_date(text, today=None):
    """The date in text, or ValueError if it isn't one this parser knows."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("no date given")
    s = " ".join(text.strip().lower().replace(",", " ").split())
    if s in RELATIVE:
        return (today or date.today()) + timedelta(days=RELATIVE[s])
    m = ISO.match(s)
    if m:
        return _make(int(m.group(1)), int(m.group(2)), int(m.group(3)), text)
    m = NUMERIC.match(s)
    if m:
        return _make(int(m.group(3)), int(m.group(1)), int(m.group(2)), text)
    words = s.split()
    if words and words[0].rstrip(".") in WEEKDAYS:
        words = words[1:]
    if len(words) == 3:
        if words[0] in MONTHS:
            return _make(_year(words[2], text), MONTHS[words[0]], _day(words[1], text), text)
        if words[1] in MONTHS:
            return _make(_year(words[2], text), MONTHS[words[1]], _day(words[0], text), text)
    raise ValueError(f"not a date this parser knows: {text!r}")


def _day(word, text):
    if not word.isdigit():
        raise ValueError(f"not a day of the month in {text!r}")
    return int(word)


def _year(word, text):
    if not (word.isdigit() and len(word) == 4):
        raise ValueError(f"not a four-digit year in {text!r}")
    return int(word)


def _make(year, month, day, text):
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError(f"no such date: {text!r}") from None
