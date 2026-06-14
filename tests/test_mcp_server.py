import asyncio
import json

from wow_ah.agent.mcp_server import build_server
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest):
        self._latest = latest

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


def _recipe():
    return Recipe(name="Flask", output_item_id=100, output_quantity=1,
                  reagents=[Reagent(item_id=1, name="Herb", quantity=10)])


def test_build_server_returns_named_fastmcp():
    server = build_server(store=FakeStore({}), recipes=[_recipe()], now="2026-06-14T12:00:00Z")
    assert server.name == "wow-ah"


def test_shared_tool_logic_used_by_mcp():
    """Invoke get_spreads through the MCP server to verify tool wiring in build_server."""
    store = FakeStore({1: PriceSnapshot(1, "2026-06-14T12:00:00Z", 100),
                       100: PriceSnapshot(100, "2026-06-14T12:00:00Z", 5000)})
    server = build_server(store=store, recipes=[_recipe()], now="2026-06-14T12:00:00Z")

    # call_tool is async and returns (list[ContentBlock], dict); ContentBlock has a .text attr
    raw = asyncio.run(server.call_tool("get_spreads", {}))

    # Robustly extract the JSON text regardless of whether raw is a tuple or a list
    content_blocks = raw[0] if isinstance(raw, (tuple, list)) else [raw]
    text = next(
        (block.text for block in content_blocks if hasattr(block, "text")),
        None,
    )
    assert text is not None, f"No text block found in call_tool result: {raw!r}"

    out = json.loads(text)
    assert out[0]["recipe_name"] == "Flask"
