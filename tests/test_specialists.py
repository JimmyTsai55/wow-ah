from wow_ah.agent.specialists import build_recipe_agent, build_trend_agent, build_risk_agent
from wow_ah.schemas.agents import LLMResponse, ToolCall
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest=None):
        self._latest = latest or {}

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _recipe():
    return Recipe(name="Flask", output_item_id=100, output_quantity=1,
                  reagents=[Reagent(item_id=1, name="Herb", quantity=10)])


def test_recipe_agent_uses_given_model_and_has_spread_tool():
    store = FakeStore(latest={1: PriceSnapshot(1, "2026-06-14T12:00:00Z", 100),
                              100: PriceSnapshot(100, "2026-06-14T12:00:00Z", 5000)})
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "get_spreads", {})], finish_reason="tool_calls"),
        LLMResponse(content="配方分析完成", tool_calls=[], finish_reason="stop"),
    ])
    agent = build_recipe_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-4.1-nano")

    answer = agent.run("哪個配方最賺？")

    assert agent.name == "recipe_analyst"
    assert agent.model == "gpt-4.1-nano"
    assert answer == "配方分析完成"
    assert any(m.get("role") == "tool" for m in llm.calls[1]["messages"])


def test_trend_and_risk_agents_build_with_model():
    store = FakeStore()
    llm = FakeLLM([LLMResponse(content="ok", tool_calls=[], finish_reason="stop")])
    trend = build_trend_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-5.4-nano",
                              now="2026-06-14T12:00:00Z")
    assert trend.name == "trend_analyst"
    assert trend.model == "gpt-5.4-nano"

    risk = build_risk_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-4.1-nano",
                            now="2026-06-14T12:00:00Z")
    assert risk.name == "risk_reviewer"
