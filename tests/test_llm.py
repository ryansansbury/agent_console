"""The model layer on canned replies, with no network: each vendor's request shape, tool calls in and out, usage in
one shape, the cache breakpoints, thinking blocks kept, bad JSON marked, and retries."""
import json
import unittest

from agents import llm

TOOLS = [{"name": "read_file", "description": "Read a file.", "input_schema": {"type": "object", "properties": {
    "path": {"type": "string"}}, "required": ["path"]}}]
MESSAGES = [
    {"role": "user", "text": "Fix the tests."},
    {"role": "assistant", "text": "Looking.", "calls": [{"id": "c1", "name": "read_file", "args": {"path": "a.py"}}]},
    {"role": "tool", "results": [{"id": "c1", "output": "print(1)", "error": False}], "note": "[console] note"},
]


def transport(*answers):
    seen = []

    def send(url, headers, body, timeout):
        seen.append({"url": url, "headers": headers, "body": json.loads(body)})
        status, data = answers[len(seen) - 1]
        return status, json.dumps(data).encode()
    send.seen = seen
    return send


ANTHROPIC_REPLY = {"model": "claude-sonnet-5-5", "stop_reason": "tool_use", "content": [
    {"type": "thinking", "thinking": "Two files to read.", "signature": "sig"},
    {"type": "text", "text": "Reading both."},
    {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a.py"}},
    {"type": "tool_use", "id": "t2", "name": "read_file", "input": {"path": "b.py"}}],
    "usage": {"input_tokens": 120, "cache_creation_input_tokens": 900, "cache_read_input_tokens": 3000, "output_tokens": 80}}
OPENAI_REPLY = {"model": "gpt-6-luna", "choices": [{"finish_reason": "tool_calls", "message": {
    "content": None, "tool_calls": [
        {"id": "o1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"a.py\"}"}},
        {"id": "o2", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": "}}]}}],
    "usage": {"prompt_tokens": 5000, "completion_tokens": 300, "total_tokens": 5400,
              "prompt_tokens_details": {"cached_tokens": 4096}}}


class Anthropic(unittest.TestCase):
    def test_the_request(self):
        send = transport((200, ANTHROPIC_REPLY))
        llm.AnthropicAPI("k" * 30, "claude-sonnet-5-5", transport=send).turn("Be careful.", MESSAGES, TOOLS, 2000)
        body = send.seen[0]["body"]
        self.assertEqual(body["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(body["tools"][0]["input_schema"]["required"], ["path"])
        user, assistant, results = body["messages"]
        self.assertEqual(assistant["content"][1], {"type": "tool_use", "id": "c1", "name": "read_file",
                                                   "input": {"path": "a.py"}})
        self.assertEqual(results["content"][0]["type"], "tool_result")
        self.assertEqual(results["content"][0]["tool_use_id"], "c1")
        self.assertEqual(results["content"][1]["text"], "[console] note")
        self.assertIn("cache_control", results["content"][-1])
        marked = sum("cache_control" in b for m in body["messages"] for b in m["content"])
        self.assertEqual(marked, 1)
        self.assertEqual(send.seen[0]["headers"]["anthropic-version"], llm.ANTHROPIC_VERSION)

    def test_the_reply(self):
        r = llm.AnthropicAPI("k" * 30, "m", transport=transport((200, ANTHROPIC_REPLY))).turn("s", MESSAGES, TOOLS, 100)
        self.assertEqual([c["id"] for c in r["calls"]], ["t1", "t2"])
        self.assertEqual(r["usage"], {"input": 120, "cache_write": 900, "cache_read": 3000, "output": 80})
        self.assertEqual(r["text"], "Reading both.")
        self.assertEqual(r["raw"][0]["type"], "thinking")
        self.assertEqual(r["thinking_chars"], len("Two files to read."))

    def test_its_own_blocks_go_back_as_they_came(self):
        r = llm.AnthropicAPI("k" * 30, "m", transport=transport((200, ANTHROPIC_REPLY))).turn("s", MESSAGES, TOOLS, 100)
        again = llm.AnthropicAPI.messages([{"role": "assistant", "text": r["text"], "calls": r["calls"], "raw": r["raw"]}])
        self.assertEqual(again[0]["content"][0]["signature"], "sig")

    def test_retries_then_answers(self):
        waits = []
        send = transport((529, {"error": {"type": "overloaded", "message": "busy"}}), (200, ANTHROPIC_REPLY))
        llm.AnthropicAPI("k" * 30, "m", transport=send, sleep=waits.append, notify=lambda s: None).turn("s", MESSAGES,
                                                                                                         TOOLS, 100)
        self.assertEqual(waits, [2])

    def test_a_refused_key_says_how_to_fix_it(self):
        send = transport((401, {"error": {"type": "authentication_error", "message": "bad"}}))
        with self.assertRaises(llm.ModelError) as e:
            llm.AnthropicAPI("k" * 30, "m", transport=send).turn("s", MESSAGES, TOOLS, 100)
        self.assertIn("owner/keys.sh --clipboard anthropic", str(e.exception))


class OpenAI(unittest.TestCase):
    def backend(self, send, **kw):
        return llm.OpenAIChat("k" * 30, "gpt-6-luna", "https://api.openai.com/v1", transport=send,
                              token_param="max_completion_tokens", **kw)

    def test_the_request(self):
        send = transport((200, OPENAI_REPLY))
        self.backend(send).turn("Be careful.", MESSAGES, TOOLS, 2000)
        body = send.seen[0]["body"]
        self.assertEqual(body["messages"][0], {"role": "system", "content": "Be careful."})
        self.assertEqual(body["tools"][0]["function"]["parameters"]["required"], ["path"])
        self.assertEqual(body["max_completion_tokens"], 2000)
        self.assertNotIn("reasoning_effort", body)
        assistant = body["messages"][2]
        self.assertEqual(json.loads(assistant["tool_calls"][0]["function"]["arguments"]), {"path": "a.py"})
        self.assertEqual(body["messages"][3], {"role": "tool", "tool_call_id": "c1", "content": "print(1)"})
        self.assertEqual(body["messages"][4], {"role": "user", "content": "[console] note"})

    def test_the_reply_and_its_usage(self):
        r = self.backend(transport((200, OPENAI_REPLY))).turn("s", MESSAGES, TOOLS, 100)
        self.assertEqual(r["calls"][0]["args"], {"path": "a.py"})
        self.assertIn("bad_args", r["calls"][1])
        self.assertEqual(r["usage"], {"input": 904, "cache_write": 0, "cache_read": 4096, "output": 400})

    def test_reasoning_effort_only_when_set(self):
        send = transport((200, OPENAI_REPLY))
        self.backend(send, reasoning_effort="low").turn("s", MESSAGES, TOOLS, 100)
        self.assertEqual(send.seen[0]["body"]["reasoning_effort"], "low")

    def test_backend_for(self):
        self.assertIsInstance(llm.backend_for({"via": "anthropic", "model": "m"}, "k" * 30), llm.AnthropicAPI)
        entry = {"via": "openai", "model": "m", "base_url": "https://x.example/v1"}
        self.assertIsInstance(llm.backend_for(entry, "k" * 30), llm.OpenAIChat)
        with self.assertRaises(ValueError):
            llm.backend_for({"via": "anthropic", "model": "m"}, "")


if __name__ == "__main__":
    unittest.main()
