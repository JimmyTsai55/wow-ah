import json
import pytest

from wow_ah.agent.llm import OpenAIChatAdapter
from wow_ah.exceptions.base import APIError


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message, finish_reason):
        self.message = message
        self.finish_reason = finish_reason


class _FakeCompletion:
    def __init__(self, choices):
        self.choices = choices


class _FakeCompletions:
    def __init__(self, completion=None, error=None):
        self._completion = completion
        self._error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return self._completion


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def test_adapter_normalizes_tool_calls():
    tc = _FakeToolCall("call_1", "get_spreads", json.dumps({"min_margin": 5.0}))
    completion = _FakeCompletion([_FakeChoice(_FakeMessage(None, [tc]), "tool_calls")])
    client = _FakeClient(_FakeCompletions(completion=completion))
    adapter = OpenAIChatAdapter(client=client)

    resp = adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)

    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_spreads"
    assert resp.tool_calls[0].arguments == {"min_margin": 5.0}


def test_adapter_handles_plain_content():
    completion = _FakeCompletion([_FakeChoice(_FakeMessage("answer", None), "stop")])
    client = _FakeClient(_FakeCompletions(completion=completion))
    adapter = OpenAIChatAdapter(client=client)

    resp = adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)

    assert resp.content == "answer"
    assert resp.tool_calls == []


def test_adapter_wraps_openai_errors():
    from openai import OpenAIError
    client = _FakeClient(_FakeCompletions(error=OpenAIError("boom")))
    adapter = OpenAIChatAdapter(client=client)

    with pytest.raises(APIError):
        adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)
