"""The budget: what a session may spend on model calls, checked before every call and counted after it.

Money is kept in whole micro-dollars, so the audit log and the page never round a float. Prices come from
config/models.json in dollars per million tokens, which is the same number as micro-dollars per token, with each
vendor's multipliers for cache writes and cache reads.

before(estimated_input_tokens) says whether the next call may go out, how long its reply may be, and whether this call
carries the warning. It stops the session when the estimated input and the smallest useful reply would pass the limit.
Until the warning has gone out, it caps each reply so the money left still pays for one more smallest call after it.
That call's input is this one's plus the reply plus a turn of tool output, counted as the biggest turn the session has
had so far and at least GROWTH_FLOOR tokens. When even the smallest reply can't keep that room, this call carries the
warning and may use the rest, so the agent hears it while it can still answer. Only a turn of tool output bigger than
that allowance can bring the stop first. After the warning, a reply is capped at what the remaining money can pay for,
so a single reply can't overshoot.

after(usage) adds the call's cost from the vendor's own usage report and says "warn" the first time spending passes
warn_at of the limit, when no warning has gone out yet. In a session that has room for many calls that comes first,
and in a short one the last-reply warning does.
"""
import math

MIN_REPLY = 256
GROWTH_FLOOR = 1000


def cost(usage, price):
    """Micro-dollars for one call: uncached input, cache writes and reads at their multipliers, and output (with any
    reasoning, which bills as output). Rounded up, so the count never runs under the bill."""
    micro = (usage.get("input", 0) * price["in"]
             + usage.get("cache_write", 0) * price["in"] * price["cache_write"]
             + usage.get("cache_read", 0) * price["in"] * price["cache_read"]
             + usage.get("output", 0) * price["out"])
    return math.ceil(micro - 1e-9)


class Budget:
    def __init__(self, limit_usd, price, warn_at=0.8, reply_cap=8192):
        self.limit = round(limit_usd * 1_000_000)
        self.price, self.warn_at, self.reply_cap = price, warn_at, reply_cap
        self.spent, self.warned, self.stopped = 0, False, False
        self.last_tokens, self.growth = None, GROWTH_FLOOR

    def before(self, estimated_input):
        """(may the call go out, the longest reply the money allows, True when this call carries the warning)."""
        if self.stopped:
            return False, 0, False
        if self.last_tokens is not None:
            self.growth = max(self.growth, estimated_input - self.last_tokens)
        remaining = self.limit - self.spent
        in_cost = math.ceil(estimated_input * self.price["in"])
        smallest = MIN_REPLY * self.price["out"]
        affordable = math.floor((remaining - in_cost) / self.price["out"]) if remaining > in_cost else 0
        if affordable < MIN_REPLY:
            self.stopped = True
            return False, 0, False
        if self.warned:
            return True, min(self.reply_cap, affordable), False
        # A reply of r tokens leaves room for one more smallest call when
        # in_cost + r*out + (in_cost + r*in + growth*in) + smallest <= remaining.
        allowance = math.ceil(self.growth * self.price["in"])
        room = math.floor((remaining - 2 * in_cost - allowance - smallest) / (self.price["out"] + self.price["in"]))
        if room < MIN_REPLY:
            self.warned = True
            return True, min(self.reply_cap, affordable), True
        return True, min(self.reply_cap, room), False

    def after(self, usage):
        """(the call's cost, "warn" the first time spending passes warn_at with no warning given yet, or None)."""
        c = cost(usage, self.price)
        self.spent += c
        self.last_tokens = sum(usage.get(k, 0) for k in ("input", "cache_write", "cache_read", "output"))
        if not self.warned and self.spent >= self.warn_at * self.limit:
            self.warned = True
            return c, "warn"
        return c, None

    def share(self):
        return self.spent / self.limit if self.limit else 1.0
