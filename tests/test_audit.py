"""The audit chain: it verifies as written, a changed entry fails at itself, a fixed hash fails at the next link, a
rewritten tail fails at the published head, and four sessions can append at once."""
import copy
import threading
import unittest

from engine import audit


def chain(n=6):
    c = audit.Chain()
    for i in range(n):
        c.append(at=f"2026-11-10T10:0{i}:00-08:00", session="infra-scripts", actor="agent", action="read",
                 target=f"file {i}", verdict="allow", rule="files", result=audit.digest(f"out {i}"))
    return c


class Chain(unittest.TestCase):
    def test_a_fresh_chain_verifies(self):
        c = chain()
        self.assertEqual(audit.verify(c.entries, c.head()), {"ok": True, "count": 6, "failed_at": None, "why": None})
        self.assertEqual(c.entries[0]["prev"], audit.GENESIS)

    def test_a_changed_entry_fails_at_itself(self):
        entries = copy.deepcopy(chain().entries)
        entries[2]["verdict"] = "deny"
        self.assertEqual(audit.verify(entries)["failed_at"], 3)
        self.assertEqual(audit.verify(entries)["why"], "content")

    def test_fixing_its_hash_breaks_the_next_link(self):
        entries = copy.deepcopy(chain().entries)
        entries[2]["verdict"] = "deny"
        entries[2]["hash"] = audit.entry_hash(entries[2])
        self.assertEqual((audit.verify(entries)["failed_at"], audit.verify(entries)["why"]), (4, "link"))

    def test_rewriting_everything_after_fails_only_at_the_published_head(self):
        c = chain()
        head = c.head()
        entries = copy.deepcopy(c.entries)
        entries[2]["verdict"] = "deny"
        for i in range(2, len(entries)):
            entries[i]["prev"] = entries[i - 1]["hash"]
            entries[i]["hash"] = audit.entry_hash(entries[i])
        self.assertTrue(audit.verify(entries)["ok"])
        self.assertEqual(audit.verify(entries, head)["why"], "head")

    def test_a_missing_entry_breaks_the_numbers(self):
        entries = chain().entries
        self.assertEqual(audit.verify(entries[:2] + entries[3:])["why"], "sequence")

    def test_only_text_and_whole_numbers(self):
        c = audit.Chain()
        with self.assertRaises(TypeError):
            c.append(at="x", target=1.5)
        with self.assertRaises(TypeError):
            c.append(at="x", target=True)

    def test_composed_and_decomposed_text_hash_the_same(self):
        a = audit.Chain().append(target="café")
        b = audit.Chain().append(target="café")
        self.assertEqual(a["hash"], b["hash"])

    def test_four_sessions_append_at_once(self):
        c = audit.Chain()

        def work(name):
            for i in range(50):
                c.append(session=name, action="shell", target=str(i))

        threads = [threading.Thread(target=work, args=(f"s{n}",)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([e["seq"] for e in c.entries], list(range(1, 201)))
        self.assertTrue(audit.verify(c.entries)["ok"])


if __name__ == "__main__":
    unittest.main()
