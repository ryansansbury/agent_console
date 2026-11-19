"""The budget: cost from usage at each vendor's prices, the warning at 80%, a reply capped to what the money pays for,
and a session that never spends past its limit however the calls fall."""
import unittest

from engine.budget import MIN_REPLY, Budget, cost

CLAUDE = {"in": 2.0, "out": 10.0, "cache_write": 1.25, "cache_read": 0.1}
LUNA = {"in": 0.1, "out": 0.5, "cache_write": 1.0, "cache_read": 1.0}


class Cost(unittest.TestCase):
    def test_hand_worked(self):
        usage = {"input": 1000, "cache_write": 2000, "cache_read": 10000, "output": 500}
        # 1000*2 + 2000*2*1.25 + 10000*2*0.1 + 500*10 = 2000 + 5000 + 2000 + 5000
        self.assertEqual(cost(usage, CLAUDE), 14000)
        self.assertEqual(cost({"input": 3, "output": 1}, LUNA), 1)
        self.assertEqual(cost({}, CLAUDE), 0)


class Limits(unittest.TestCase):
    def test_the_warning_comes_once_at_eighty_percent(self):
        b = Budget(0.01, CLAUDE)
        self.assertEqual(b.after({"output": 700}), (7000, None))
        self.assertEqual(b.after({"output": 100}), (1000, "warn"))
        self.assertEqual(b.after({"output": 10}), (100, None))

    def test_until_the_warning_a_reply_leaves_room_for_one_more_call(self):
        b = Budget(0.02, CLAUDE)
        # 20000 left and 2000 of input: a reply of r tokens keeps room for one more smallest call when
        # 2000 + 10r + (2000 + 2r + 1000 * 2) + 256 * 10 <= 20000, so r is at most 953
        self.assertEqual(b.before(1000), (True, 953, False))

    def test_the_room_counts_the_biggest_turn_of_tool_output_so_far(self):
        b = Budget(0.1, CLAUDE)
        b.before(1000)
        b.after({"input": 1000, "output": 200})
        # 2000 tokens of tool output came back: (96000 - 2 * 6400 - 2000 * 2 - 2560) / 12
        self.assertEqual(b.before(3200), (True, 6386, False))
        b.after({"input": 3200, "output": 100})
        b.before(3500)
        self.assertEqual(b.growth, 2000)

    def test_the_call_that_cannot_keep_that_room_carries_the_warning(self):
        b = Budget(0.01, CLAUDE)
        b.after({"output": 100})
        self.assertEqual(b.before(1000), (True, 700, True))
        self.assertTrue(b.warned)
        self.assertEqual(b.after({"output": 10}), (100, None))

    def test_after_the_warning_a_reply_may_use_the_rest(self):
        b = Budget(0.1, CLAUDE)
        self.assertEqual(b.after({"output": 8000}), (80000, "warn"))
        self.assertEqual(b.before(1000), (True, 1800, False))

    def test_it_stops_when_a_useful_reply_is_out_of_reach(self):
        b = Budget(0.01, CLAUDE)
        b.after({"output": 800})
        self.assertEqual(b.before(1000), (False, 0, False))
        self.assertTrue(b.stopped)
        self.assertEqual(b.before(0), (False, 0, False))

    def run_until_stopped(self, reply, growth=400):
        """Calls until the budget stops them, each wanting a reply of reply tokens and bringing back growth tokens of
        tool output. heard is whether a call carried the warning before the stop."""
        b = Budget(0.05, CLAUDE)
        context, calls, heard, pending = 1500, 0, False, False
        while True:
            go, cap, last = b.before(context)
            if not go:
                break
            heard = heard or last or pending
            used = min(cap, reply)
            pending = b.after({"input": context, "output": used})[1] == "warn"
            context += used + growth
            calls += 1
        return b, calls, heard

    def test_spend_never_passes_the_limit_and_the_warning_reaches_the_agent_first(self):
        for reply in (300, 600, 10 ** 6):
            for growth in (0, 400, 1000):
                b, calls, heard = self.run_until_stopped(reply, growth)
                self.assertLessEqual(b.spent, b.limit, (reply, growth))
                self.assertTrue(b.stopped)
                self.assertTrue(heard, (reply, growth))
        b, calls, heard = self.run_until_stopped(600)
        self.assertGreater(calls, 3)
        self.assertGreater(b.spent, b.limit - MIN_REPLY * CLAUDE["out"] - 50000 * 0.2)


if __name__ == "__main__":
    unittest.main()
