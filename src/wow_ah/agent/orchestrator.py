from wow_ah.agent.base import Agent, Tool
from wow_ah.agent.freshness import check_freshness
from wow_ah.agent.specialists import (
    build_recipe_agent,
    build_risk_agent,
    build_trend_agent,
)
from wow_ah.core.config import Settings
from wow_ah.protocols.llm import LLMProtocol
from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.recipes import Recipe

_ORCHESTRATOR_PROMPT = (
    "你是 WoW 拍賣場套利顧問的主控者。依使用者問題，呼叫適合的專家工具："
    "consult_recipe_analyst（配方利潤）、consult_trend_analyst（買賣時機）、"
    "consult_risk_reviewer（檢查建議是否可靠）。先取得分析，再請風險審查員把關，"
    "最後以繁體中文彙整成清楚、可執行的建議。記住：暴雪 API 無法自動下單，"
    "你的建議僅供使用者手動操作參考。"
)

ADVISE_PROMPT = (
    "請主動分析目前拍賣場：找出最值得製造販售的配方，以及現在適合買進或賣出的物品，"
    "經風險審查後，產出一份依優先順序排列的繁體中文交易建議報告，並附上理由。"
)

_CONSULT_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "要交給該專家的問題"}},
    "required": ["question"],
}


def _consult_tool(name: str, description: str, specialist: Agent) -> Tool:
    return Tool(
        name=name,
        description=description,
        parameters=_CONSULT_SCHEMA,
        func=lambda question: specialist.run(question),
    )


def build_orchestrator(
    *, llm: LLMProtocol, store: PriceStoreProtocol, recipes: list[Recipe], settings: Settings, now: str
) -> Agent:
    recipe_agent = build_recipe_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for(
            "recipe")
    )
    trend_agent = build_trend_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for("trend"), now=now
    )
    risk_agent = build_risk_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for("risk"), now=now
    )

    tools = [
        _consult_tool("consult_recipe_analyst",
                      "請配方利潤分析師分析配方淨利。", recipe_agent),
        _consult_tool("consult_trend_analyst", "請價格趨勢分析師分析買賣時機。", trend_agent),
        _consult_tool("consult_risk_reviewer", "請風險審查員檢查建議是否可靠。", risk_agent),
    ]
    return Agent(
        name="orchestrator",
        model=settings.model_for("orchestrator"),
        system_prompt=_ORCHESTRATOR_PROMPT,
        tools=tools,
        llm=llm,
    )


def run_advisor(
    prompt: str,
    *,
    llm: LLMProtocol,
    store: PriceStoreProtocol,
    recipes: list[Recipe],
    settings: Settings,
    now: str,
) -> str:
    """Run the freshness gate, then the orchestrated multi-agent flow."""
    freshness = check_freshness(store, now)
    if not freshness.is_fresh:
        return freshness.message

    orchestrator = build_orchestrator(
        llm=llm, store=store, recipes=recipes, settings=settings, now=now
    )
    return orchestrator.run(prompt)
