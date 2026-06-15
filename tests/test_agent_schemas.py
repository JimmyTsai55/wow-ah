from wow_ah.schemas.agents import ToolCall, LLMResponse, FreshnessResult


def test_tool_call_holds_parsed_arguments():
    tc = ToolCall(id="call_1", name="get_spreads", arguments={"min_margin": 5.0})
    assert tc.arguments["min_margin"] == 5.0


def test_llm_response_defaults_to_no_tool_calls():
    resp = LLMResponse(content="hi")
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.content == "hi"


def test_freshness_result_fields():
    fr = FreshnessResult(is_fresh=False, last_fetch=None, age_hours=None, message="stale")
    assert fr.is_fresh is False
    assert fr.message == "stale"
