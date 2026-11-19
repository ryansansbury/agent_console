"""The shell builds and reads every word from WORDS.md, the never list, the other demos' names and the avoid list stay
out of everything that ships, and the vendors' names stand alone."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import build
from app import never, page, words

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")


def scratch_dir():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=str(SCRATCH))


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The preview goes to a scratch copy of site/, so the tests never overwrite a real build there.
        cls.tmp = scratch_dir()
        cls.site = Path(cls.tmp.name, "site")
        shutil.copytree(HERE.joinpath("site"), cls.site)
        real, build.SITE = build.SITE, cls.site
        try:
            cls.code = build.main(["--preview"])
        finally:
            build.SITE = real
        cls.html = cls.site.joinpath("index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_page_builds_from_words(self):
        self.assertEqual(self.code, 0)
        w = words.load()
        self.assertIn(f"<title>{w['page.title']}</title>", self.html)
        self.assertIn(w["page.footer"], self.html)
        self.assertIn(w["page.preview"], self.html)

    def test_no_inline_style_or_script_and_nothing_loaded_from_another_site(self):
        self.assertNotIn(" style=", self.html)
        self.assertNotRegex(self.html, r"<script>[^<]|<script[^>]*>[^<]+</script>")
        # The canonical link names the live address and loads nothing, so it's the one link allowed to.
        loads = re.sub(r"<link rel='canonical' href='[^']+'>", "", self.html)
        self.assertEqual(len(re.findall(r"<link rel='canonical'", self.html)), 1)
        self.assertNotRegex(loads, r"<(?:script|img|link|iframe|audio|video|source)[^>]+(?:src|href)=['\"](?:https?:)?[/][/]")
        self.assertEqual(re.findall(r"<script src='([^']+)'", self.html), ["data.js", "policy.js", "audit.js", "app.js"])

    def test_every_view_has_its_frame(self):
        for view in page.VIEWS:
            self.assertIn(f"id='v-{view}'", self.html)
        self.assertEqual(self.html.count("class='cfeat'"), 5)

    def test_the_page_script_reaches_nothing_on_the_network(self):
        script = HERE.joinpath("site", "app.js").read_text(encoding="utf-8")
        for needle in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "http:", "https:"):
            self.assertNotIn(needle, script)

    def test_a_missing_word_fails_loudly(self):
        with self.assertRaises(words.MissingWord):
            words.Words({}, {})["page.title"]


class Lists(unittest.TestCase):
    def test_the_foreign_list_catches_another_demos_name(self):
        with scratch_dir() as d:
            f = Path(d, "x.txt")
            f.write_text("A note about zzqx and its alerts.", encoding="utf-8")
            self.assertTrue(any("another demo" in p for p in never.scan([f], (), ("zzqx",), ())))
            self.assertEqual(never.scan([f], (), ("qqzv",), ()), [])

    def test_the_avoid_list_comes_from_the_names_file(self):
        with scratch_dir() as d:
            f = Path(d, "names.json")
            f.write_text(json.dumps({"avoid": ["Zzqx Cloud", " "]}), encoding="utf-8")
            self.assertEqual(never.avoid(f), ("zzqx cloud",))
            page_text = Path(d, "page.txt")
            page_text.write_text("Compared with Zzqx  Cloud on price.", encoding="utf-8")
            self.assertTrue(any("avoid list" in p for p in never.scan([page_text], (), (), never.avoid(f))))
        self.assertEqual(never.avoid(HERE.joinpath(".cache", "tmp", "no-such-file.json")), ())

    def test_the_avoid_list_has_its_own_file_that_never_ships(self):
        with scratch_dir() as d:
            f = Path(d, "avoid.txt")
            f.write_text("# real companies\nZzqx Cloud\n\n  Qqzv  \n", encoding="utf-8")
            self.assertEqual(never.avoid(f), ("zzqx cloud", "qqzv"))
        cast = never.names()
        if cast is not None:
            self.assertNotIn("avoid", cast, "the avoid list names real companies, so it lives in config/avoid.txt")

    def test_whole_words_only(self):
        self.assertEqual(never.hits("a category of cats", ["cat"]), [])
        self.assertEqual(never.hits("the cat sat", ["cat"]), ["cat"])

    def test_first_names_check_names_and_never_prose(self):
        if not HERE.joinpath("config", "foreign_first_names.txt").exists():
            self.skipTest("the public copy leaves out the other demos' names")
        self.assertTrue(never.first_names(), "config/foreign_first_names.txt is empty")
        self.assertEqual(never.taken_words(["Alpha Vendor", "Beta Works"], taken={"beta"}), ["beta"])
        self.assertEqual(never.taken_words(["Alpha Vendor"], taken={"beta"}), [])


class Cast(unittest.TestCase):
    def test_the_vendors_are_cleared_and_stand_alone(self):
        cast = never.names()
        if cast is None:
            self.skipTest("config/names.json hasn't landed yet (it's written after the names check)")
        self.assertTrue(cast.get("category"))
        vendors = cast["vendors"]
        self.assertEqual([v["id"] for v in vendors], ["v1", "v2", "v3"])
        host = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.example$")
        domains = [v["domain"] for v in vendors] + [cast["outside_domain"]]
        for d in domains:
            self.assertRegex(d, host)
        self.assertEqual(len(set(domains)), 4, "two vendors, or a vendor and the outside address, share a domain")
        names = [v["name"].strip() for v in vendors]
        self.assertTrue(all(names))
        self.assertEqual(len({n.lower() for n in names}), 3, "two vendors share a name")
        text = " | ".join(names + domains)
        self.assertEqual(never.hits(text, never.words()), [])
        self.assertEqual(never.hits(text, never.foreign()), [])
        self.assertEqual(never.hits(text, never.avoid()), [])
        self.assertEqual(never.taken_words(names), [], "a vendor's name uses a first name an earlier cast has")
        self.assertIsInstance(cast.get("avoid", []), list)


if __name__ == "__main__":
    unittest.main()
