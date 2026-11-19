import unittest
from datetime import date

from dateparse import parse_date

TODAY = date(2026, 11, 9)


class IsoAndNumeric(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_date("2026-11-09"), date(2026, 11, 9))

    def test_iso_without_zero_padding(self):
        self.assertEqual(parse_date("2026-3-9"), date(2026, 3, 9))

    def test_iso_rejects_a_day_that_does_not_exist(self):
        with self.assertRaises(ValueError):
            parse_date("2026-11-31")

    def test_us_numeric(self):
        self.assertEqual(parse_date("11/9/2026"), date(2026, 11, 9))

    def test_us_numeric_padded(self):
        self.assertEqual(parse_date("03/09/2026"), date(2026, 3, 9))

    def test_two_digit_year(self):
        self.assertEqual(parse_date("3/9/26"), date(2026, 3, 9))

    def test_month_out_of_range(self):
        with self.assertRaises(ValueError):
            parse_date("13/1/2026")


class MonthNames(unittest.TestCase):
    def test_short_month_first(self):
        self.assertEqual(parse_date("Nov 9, 2026"), date(2026, 11, 9))

    def test_full_month_first(self):
        self.assertEqual(parse_date("November 9, 2026"), date(2026, 11, 9))

    def test_day_first(self):
        self.assertEqual(parse_date("9 November 2026"), date(2026, 11, 9))

    def test_without_a_comma(self):
        self.assertEqual(parse_date("Nov 9 2026"), date(2026, 11, 9))

    def test_weekday_in_front(self):
        self.assertEqual(parse_date("Mon, Nov 9, 2026"), date(2026, 11, 9))

    def test_capitals_and_spaces(self):
        self.assertEqual(parse_date("  NOV 9,  2026 "), date(2026, 11, 9))

    def test_ordinal_day(self):
        self.assertEqual(parse_date("March 3rd, 2026"), date(2026, 3, 3))

    def test_abbreviation_with_a_period(self):
        self.assertEqual(parse_date("Sept. 9, 2026"), date(2026, 9, 9))

    def test_leap_day(self):
        self.assertEqual(parse_date("Feb 29, 2028"), date(2028, 2, 29))

    def test_not_a_leap_year(self):
        with self.assertRaises(ValueError):
            parse_date("Feb 29, 2026")

    def test_three_digit_year(self):
        with self.assertRaises(ValueError):
            parse_date("Nov 9, 202")


class Relative(unittest.TestCase):
    def test_today(self):
        self.assertEqual(parse_date("today", today=TODAY), TODAY)

    def test_tomorrow(self):
        self.assertEqual(parse_date("Tomorrow", today=TODAY), date(2026, 11, 10))

    def test_yesterday(self):
        self.assertEqual(parse_date("yesterday", today=TODAY), date(2026, 11, 8))


class NotDates(unittest.TestCase):
    def test_empty(self):
        with self.assertRaises(ValueError):
            parse_date("   ")

    def test_none(self):
        with self.assertRaises(ValueError):
            parse_date(None)

    def test_words(self):
        with self.assertRaises(ValueError):
            parse_date("next week sometime")


if __name__ == "__main__":
    unittest.main()
