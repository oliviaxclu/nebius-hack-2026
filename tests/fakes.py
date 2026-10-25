"""Stand-ins for the Token Factory client so the whole stack is testable without a key."""
import json
from types import SimpleNamespace as NS


def call(i, name, args):
    return NS(id=f"c{i}", function=NS(name=name, arguments=json.dumps(args)))


def tool_msg(*calls):
    return NS(content="", tool_calls=list(calls))


def text_msg(text):
    return NS(content=text, tool_calls=None)


class ScriptedClient:
    """OpenAI-client lookalike: returns scripted messages in order; records every request for inspection."""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.chat = NS(completions=self)

    def create(self, **kw):
        self.requests.append(kw)
        item = self.script.pop(0) if self.script else text_msg("(script exhausted)")
        msg = item(kw["messages"]) if callable(item) else item
        return NS(choices=[NS(message=msg)])


class ScriptedLLM:
    """Direct LLM replacement for agent-only tests (no redaction/audit)."""

    def __init__(self, script):
        self.script, self.seen = list(script), []

    def chat(self, messages, tools=None, purpose="chat"):
        self.seen.append(messages)
        item = self.script.pop(0)
        return item(messages) if callable(item) else item
