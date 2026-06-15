from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.agent.tools import prices_json, recipes_json, spreads_json, trends_json
from wow_ah.core.config import get_settings
from wow_ah.recipes.loader import load_all_recipes
from wow_ah.schemas.recipes import Recipe


def build_server(*, store, recipes: list[Recipe], now: str) -> FastMCP:
    """Build a FastMCP server exposing the read-only analysis tools."""
    mcp = FastMCP("wow-ah")

    @mcp.tool()
    def get_spreads(min_margin: float = 0.0) -> str:
        """各配方扣手續費後的淨利列表（JSON）。"""
        return spreads_json(store, recipes, min_margin)

    @mcp.tool()
    def get_trends(days: int = 7) -> str:
        """各物品的 BUY/SELL/HOLD 價格訊號（JSON）。"""
        return trends_json(store, recipes, now, days)

    @mcp.tool()
    def get_prices(item: str | None = None, hours: int = 24) -> str:
        """各追蹤物品的最新價格（JSON）。"""
        return prices_json(store, recipes, now, item, hours)

    @mcp.tool()
    def list_recipes() -> str:
        """所有已載入的配方定義（JSON）。"""
        return recipes_json(recipes)

    return mcp


def run_server() -> None:
    settings = get_settings()
    store = SQLiteAdapter(settings.db_path)
    recipes = load_all_recipes()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_server(store=store, recipes=recipes, now=now).run()
