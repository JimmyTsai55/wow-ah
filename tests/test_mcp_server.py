import json

from wow_ah.agent.mcp_server import build_server
from wow_ah.agent.tools import spreads_json
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
    store = FakeStore({1: PriceSnapshot(1, "2026-06-14T12:00:00Z", 100),
                       100: PriceSnapshot(100, "2026-06-14T12:00:00Z", 5000)})
    out = json.loads(spreads_json(store, [_recipe()], 0.0))
    assert out[0]["recipe_name"] == "Flask"
