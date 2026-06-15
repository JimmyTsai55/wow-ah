from wow_ah.agent.orchestrator import run_advisor, ADVISE_PROMPT
from wow_ah.core.config import Settings
from wow_ah.schemas.agents import LLMResponse, ToolCall


class FakeStore:
    def __init__(self, last):
        self._last = last

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids): return {}
    def get_last_fetch_timestamp(self): return self._last


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _settings():
    return Settings(_env_file=None, openai_default_model="gpt-4.1-nano",
                    wow_ah_orchestrator_model="gpt-5.4-nano")


def test_stale_data_short_circuits_before_llm():
    store = FakeStore(last=None)  # no data
    llm = FakeLLM([])  # must never be called
    out = run_advisor("哪個配方最賺？", llm=llm, store=store, recipes=[],
                      settings=_settings(), now="2026-06-14T12:00:00Z")
    assert "fetch" in out.lower()
    assert llm.calls == []


def test_orchestrator_consults_specialist_and_uses_models():
    store = FakeStore(last="2026-06-14T11:00:00Z")  # fresh
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "consult_recipe_analyst", {"question": "哪個配方最賺"})], finish_reason="tool_calls"),
        LLMResponse(content="建議製造 Flask", tool_calls=[], finish_reason="stop"),
        LLMResponse(content="最終建議：製造 Flask", tool_calls=[], finish_reason="stop"),
    ])
    out = run_advisor("哪個配方最賺？", llm=llm, store=store, recipes=[],
                      settings=_settings(), now="2026-06-14T12:00:00Z")

    assert out == "最終建議：製造 Flask"
    assert llm.calls[0]["model"] == "gpt-5.4-nano"
    assert llm.calls[1]["model"] == "gpt-4.1-nano"


def test_advise_prompt_is_nonempty():
    assert "建議" in ADVISE_PROMPT


def test_stale_timestamp_short_circuits_before_llm():
    store = FakeStore(last="2026-06-13T00:00:00Z")  # ~36h old, exceeds 6h threshold
    llm = FakeLLM([])  # must never be called
    out = run_advisor("哪個配方最賺？", llm=llm, store=store, recipes=[],
                      settings=_settings(), now="2026-06-14T12:00:00Z")
    assert "fetch" in out.lower()
    assert llm.calls == []
