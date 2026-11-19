"""Who answers when the policy asks a person.

During recording a script answers, from config/approvals.json, by the rule that asked: approve, decline, or leave the
call waiting, which ends the session there. Every answer is recorded with the actor "script" and labeled that way on
the page, since no person watched the run. The push is the one ask left waiting, so the visitor answers it on the page.
"""
import time

ANSWERS = ("approve", "decline", "wait")


class ScriptedApprover:
    actor = "script"

    def __init__(self, config, sleep=time.sleep):
        self.answers = dict(config.get("answers", {}))
        self.default = config.get("default", "decline")
        self.delay = config.get("delay_s", 0)
        self.sleep = sleep

    def __call__(self, facts, decision):
        answer = self.answers.get(decision["rule"], self.default)
        if answer not in ANSWERS:
            answer = "decline"
        if answer != "wait" and self.delay:
            self.sleep(self.delay)
        return answer
