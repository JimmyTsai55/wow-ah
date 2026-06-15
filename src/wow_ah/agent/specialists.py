from wow_ah.agent.base import Agent, Tool
from wow_ah.agent.tools import prices_json, recipes_json, spreads_json, trends_json
from wow_ah.protocols.llm import LLMProtocol
from wow_ah.schemas.recipes import Recipe

_RECIPE_PROMPT = (
    "你是「配方利潤分析師」。用 get_spreads 取得各配方扣除拍賣場手續費後的淨利，"
    "必要時用 list_recipes 了解配方組成。以繁體中文點出最值得製造販售的配方與理由，"
    "金額以 copper 為單位。只依工具回傳的資料回答，不要編造價格。"
)
_TREND_PROMPT = (
    "你是「價格趨勢分析師」。用 get_trends 取得各物品的 BUY/SELL/HOLD 訊號，"
    "必要時用 get_prices 查最新價。以繁體中文說明現在適合買進或賣出哪些物品與理由。"
    "只依工具回傳的資料回答，不要編造價格。"
)
_RISK_PROMPT = (
    "你是「風險審查員」。針對其他分析師提出的交易建議，用 get_prices 檢查相關物品的"
    "資料筆數是否足夠、價格是否異常。以繁體中文指出建議中不可靠或證據不足之處；"
    "若無明顯風險，明確說明通過審查。"
)

_SPREADS_SCHEMA = {
    "type": "object",
    "properties": {"min_margin": {"type": "number", "description": "最低利潤率%，預設0"}},
}
_TRENDS_SCHEMA = {
    "type": "object",
    "properties": {"days": {"type": "integer", "description": "分析的歷史天數，預設7"}},
}
_PRICES_SCHEMA = {
    "type": "object",
    "properties": {
        "item": {"type": "string", "description": "以名稱子字串過濾，可省略"},
        "hours": {"type": "integer", "description": "回溯小時數，預設24"},
    },
}
_RECIPES_SCHEMA = {"type": "object", "properties": {}}


def _spreads_tool(store, recipes: list[Recipe]) -> Tool:
    return Tool(
        name="get_spreads",
        description="取得各配方扣手續費後的淨利列表（依利潤率排序）。",
        parameters=_SPREADS_SCHEMA,
        func=lambda min_margin=0.0: spreads_json(store, recipes, min_margin),
    )


def _recipes_tool(recipes: list[Recipe]) -> Tool:
    return Tool(
        name="list_recipes",
        description="列出所有已載入的配方定義與其材料。",
        parameters=_RECIPES_SCHEMA,
        func=lambda: recipes_json(recipes),
    )


def _trends_tool(store, recipes: list[Recipe], now: str) -> Tool:
    return Tool(
        name="get_trends",
        description="取得各物品的 BUY/SELL/HOLD 價格訊號。",
        parameters=_TRENDS_SCHEMA,
        func=lambda days=7: trends_json(store, recipes, now, days),
    )


def _prices_tool(store, recipes: list[Recipe], now: str) -> Tool:
    return Tool(
        name="get_prices",
        description="取得各追蹤物品的最新價格與資料筆數。",
        parameters=_PRICES_SCHEMA,
        func=lambda item=None, hours=24: prices_json(store, recipes, now, item, hours),
    )


def build_recipe_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str) -> Agent:
    return Agent(
        name="recipe_analyst",
        model=model,
        system_prompt=_RECIPE_PROMPT,
        tools=[_spreads_tool(store, recipes), _recipes_tool(recipes)],
        llm=llm,
    )


def build_trend_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str, now: str) -> Agent:
    return Agent(
        name="trend_analyst",
        model=model,
        system_prompt=_TREND_PROMPT,
        tools=[_trends_tool(store, recipes, now), _prices_tool(store, recipes, now)],
        llm=llm,
    )


def build_risk_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str, now: str) -> Agent:
    return Agent(
        name="risk_reviewer",
        model=model,
        system_prompt=_RISK_PROMPT,
        tools=[_prices_tool(store, recipes, now)],
        llm=llm,
    )
