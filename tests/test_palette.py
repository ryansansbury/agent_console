"""The palette passes WCAG contrast: 4.5 to 1 for every text color on the background it sits on (the pills, the links,
the muted text, the night console's words and the terminal's lines included), and 3 to 1 for every mark against what's
behind it, the light page's marks on white and each tile's icon on its own tile in the night console. Each verdict also
has its own icon on the trace, so color is never the only signal. The colors are read from site/app.css itself."""
import re
import unittest
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent.joinpath("site", "app.css").read_text(encoding="utf-8")

def block(selector):
    """The custom properties a rule sets, as {name: hex}."""
    start = CSS.index(selector + " {")
    body = CSS[start:CSS.index("}", start)]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", body))


VARS = block(":root")
# Dark mode (11/20): the dark rule's values over the light ones, for the day surfaces that turn dark.
DARK = dict(VARS, **block("body.dark"))
WHITE = "#ffffff"


def color(name):
    return VARS[name[2:]] if name.startswith("--") else name


def luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(color(a)), luminance(color(b))), reverse=True)
    return (la + 0.05) / (lb + 0.05)


KPI, POP, THEAD = "#0d1219", "#111722", "#0d1219"
TEXT = [("--ink", WHITE), ("--ink2", WHITE), ("--muted", WHITE), ("--muted", "--soft"), ("--muted", "--bg"), ("--cyan", WHITE),
        ("--done", "--done-bg"), ("--ask", "--ask-bg"), ("--deny", "--deny-bg"), ("--cyan-ink", "--cyan-bg"),
        ("--budget-ink", "--budget-bg"), ("--ask", WHITE), ("--deny", WHITE), ("--cyan-ink", WHITE),
        ("#3f4650", "#eef0f2"), ("#3f4650", "#eef0f3"), ("#7f1d1d", "--deny-bg"), ("--cyan-ink", "#ecfeff"), ("#ffffff", "--ink"),
        # the night console: its words, the lanes' pills, the counts, the tooltip and the inspector's dark lines
        ("--night-ink", "--night"), ("--night-ink2", "--night"), ("--night-muted", "--night"), ("--night-muted", KPI),
        ("--night-muted", POP), ("--night-ink2", POP), ("--n-quarantine-ink", "--night"), ("--n-done-ink", "--n-done-bg"),
        ("--n-ask-ink", "--n-ask-bg"), ("--n-deny-ink", "--n-deny-bg"), ("--n-ask", KPI), ("--n-deny", KPI),
        ("--n-quarantine", KPI), ("--n-done", KPI), ("--night-ink", KPI), ("#e6edf3", "--night"), ("#c4ccd6", "--night"),
        # the terminal
        ("#d8dde3", "--night"), ("#9aa3ad", THEAD), ("#8f99a3", "--night"), ("#b8c0c9", "--night"), ("#fbbf24", "--night"),
        ("#f87171", "--night"), ("#67e8f9", "--night"), ("#fde68a", "#1f1a0e")]
MARKS = ["--allow", "--ask2", "--deny2", "--cyan2", "--done", "--ink2"]
# Each tile's icon on its own tile: the plain one, the tinted verdicts, and the two solid ones.
TILES = [("--n-allow", "--night-tile"), ("--n-ask", "--n-ask-bg"), ("--n-deny", "--n-deny-bg"),
         ("--n-quarantine", "--n-quarantine-bg"), ("--n-done", "--n-done-bg"), ("--n-budget", "--n-budget-bg"),
         ("#241703", "--n-ask"), ("#ffffff", "#ef4444")]


class Palette(unittest.TestCase):
    def test_every_text_pair_reads(self):
        low = [(a, b, round(contrast(a, b), 2)) for a, b in TEXT if contrast(a, b) < 4.5]
        self.assertEqual(low, [])

    def test_every_mark_stands_out_from_the_page(self):
        low = [(m, round(contrast(m, WHITE), 2)) for m in MARKS if contrast(m, WHITE) < 3]
        self.assertEqual(low, [])

    def test_every_tile_icon_stands_out_from_its_tile(self):
        low = [(a, b, round(contrast(a, b), 2)) for a, b in TILES if contrast(a, b) < 3]
        self.assertEqual(low, [])

    def test_the_hand_worked_formula(self):
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(contrast("#777777", "#ffffff"), 4.48, places=2)


if __name__ == "__main__":
    unittest.main()


class DarkPalette(unittest.TestCase):
    """In dark mode every day text color reads at 4.5 to 1 on the dark surface that replaces its light one, and every
    mark stands out at 3 to 1. The night console doesn't change, so its pairs above hold in both."""
    PAIRS = [("--ink", "--card"), ("--ink2", "--card"), ("--muted", "--card"), ("--muted", "--soft"), ("--muted", "--bg"),
             ("--ink", "--bg"), ("--cyan", "--card"), ("--done", "--done-bg"), ("--ask", "--ask-bg"), ("--deny", "--deny-bg"),
             ("--cyan-ink", "--cyan-bg"), ("--budget-ink", "--budget-bg"), ("--ask", "--card"), ("--deny", "--card"),
             ("--cyan-ink", "--card"), ("--ink2", "--raise"), ("#fca5a5", "--deny-bg"), ("#0b0f15", "#e8edf3")]

    def ratio(self, a, b):
        def lum(c):
            c = DARK[c[2:]] if c.startswith("--") else c
            rgb = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
            return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def test_every_dark_text_pair_reads(self):
        low = [(a, b, round(self.ratio(a, b), 2)) for a, b in self.PAIRS if self.ratio(a, b) < 4.5]
        self.assertEqual(low, [])

    def test_every_dark_mark_stands_out(self):
        low = [(m, round(self.ratio(m, "--card"), 2)) for m in ("--allow", "--ask2", "--deny2", "--cyan2", "--done", "--ink2")
               if self.ratio(m, "--card") < 3]
        self.assertEqual(low, [])

    def test_the_switch_is_in_the_page_and_light_is_the_default(self):
        page = Path(__file__).resolve().parent.parent.joinpath("site", "index.html").read_text(encoding="utf-8")
        self.assertIn("id='theme'", page)
        self.assertIn("aria-pressed='false'", page.split("id='theme'", 1)[1][:200])
        self.assertNotIn("class='dark", page)

