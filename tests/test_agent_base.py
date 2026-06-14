import pytest

from wow_ah.agent.base import Agent, Tool
from wow_ah.exceptions.base import APIError
from wow_ah.schemas.agents import LLMResponse, ToolCall


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _echo_tool(received):
    def _run(text: str) -> str:
        received.append(text)
        return f"got:{text}"

    return Tool(
        name="echo",
        description="echo text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        func=_run,
    )


def test_agent_executes_tool_then_returns_final_text():
    received = []
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "echo", {"text": "hi"})], finish_reason="tool_calls"),
        LLMResponse(content="done", tool_calls=[], finish_reason="stop"),
    ])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[_echo_tool(received)], llm=llm)

    answer = agent.run("question")

    assert answer == "done"
    assert received == ["hi"]
    assert llm.calls[0]["model"] == "gpt-4.1-nano"
    assert any(m.get("role") == "tool" and m.get("content") == "got:hi" for m in llm.calls[1]["messages"])


def test_agent_returns_immediately_when_no_tool_calls():
    llm = FakeLLM([LLMResponse(content="straight answer", tool_calls=[], finish_reason="stop")])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[], llm=llm)
    assert agent.run("q") == "straight answer"


def test_agent_raises_on_unknown_tool():
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "missing", {})], finish_reason="tool_calls"),
    ])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[], llm=llm)
    with pytest.raises(APIError):
        agent.run("q")


def test_agent_raises_when_max_rounds_exceeded():
    tool_loop = [
        LLMResponse(content=None, tool_calls=[ToolCall(f"c{i}", "echo", {"text": "x"})], finish_reason="tool_calls")
        for i in range(20)
    ]
    llm = FakeLLM(tool_loop)
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[_echo_tool([])], llm=llm)
    with pytest.raises(APIError):
        agent.run("q")
