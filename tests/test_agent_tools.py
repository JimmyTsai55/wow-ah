import json

from wow_ah.agent.tools import spreads_json, trends_json, prices_json, recipes_json
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest=None, history=None):
        self._latest = latest or {}
        self._history = history or []

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return self._history
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


def _snap(item_id, min_price, ts="2026-06-14T12:00:00Z"):
    return PriceSnapshot(item_id=item_id, timestamp=ts, min_price=min_price)


def _recipe():
    return Recipe(
        name="Test Flask", output_item_id=100, output_quantity=1,
        reagents=[Reagent(item_id=1, name="Herb A", quantity=10)],
    )


def test_spreads_json_returns_recipe_profit():
    store = FakeStore(latest={1: _snap(1, 100), 100: _snap(100, 5000)})
    out = json.loads(spreads_json(store, [_recipe()], min_margin=0.0))
    assert out[0]["recipe_name"] == "Test Flask"
    assert out[0]["profit"] == 5000 - (5000 * 5 // 100) - 1000


def test_recipes_json_lists_definitions():
    out = json.loads(recipes_json([_recipe()]))
    assert out[0]["name"] == "Test Flask"
    assert out[0]["reagents"][0]["name"] == "Herb A"


def test_trends_json_empty_when_no_history():
    store = FakeStore(history=[])
    out = json.loads(trends_json(store, [_recipe()], now="2026-06-14T12:00:00Z", days=7))
    assert out == []


def test_prices_json_filters_by_item_name():
    store = FakeStore(history=[_snap(1, 100)])
    out = json.loads(prices_json(store, [_recipe()], now="2026-06-14T12:00:00Z", item="Nonexistent"))
    assert out == []
