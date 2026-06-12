import pytest

from wow_ah.exceptions.base import DataError
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent
from wow_ah.services.spread_service import SpreadService

AH_FEE_PCT = 5


class FakeStore:
    def __init__(self, prices: dict[int, PriceSnapshot]):
        self._prices = prices

    def save_snapshots(self, snapshots):
        pass

    def get_price_history(self, item_id, start, end):
        return []

    def get_latest_prices(self, item_ids):
        return {iid: self._prices[iid] for iid in item_ids if iid in self._prices}

    def get_last_fetch_timestamp(self):
        return None


def _snap(item_id: int, min_price: int) -> PriceSnapshot:
    return PriceSnapshot(item_id=item_id, timestamp="2026-04-10T14:00:00Z", min_price=min_price)


def test_spread_profitable():
    store = FakeStore({
        1: _snap(1, 100),   # reagent A: 100 copper
        2: _snap(2, 200),   # reagent B: 200 copper
        100: _snap(100, 5000),  # product: 5000 copper
    })
    recipes = [
        Recipe(
            name="Test Flask",
            output_item_id=100,
            output_quantity=1,
            reagents=[
                Reagent(item_id=1, name="Herb A", quantity=10),
                Reagent(item_id=2, name="Herb B", quantity=5),
            ],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)

    assert len(results) == 1
    r = results[0]
    assert r.recipe_name == "Test Flask"
    assert r.material_cost == 10 * 100 + 5 * 200  # 2000
    assert r.product_price == 5000
    expected_profit = 5000 - (5000 * AH_FEE_PCT // 100) - 2000  # 5000 - 250 - 2000 = 2750
    assert r.profit == expected_profit
    assert r.margin_pct == expected_profit / 2000 * 100


def test_spread_loss():
    store = FakeStore({
        1: _snap(1, 1000),
        100: _snap(100, 500),
    })
    recipes = [
        Recipe(
            name="Bad Flask",
            output_item_id=100,
            output_quantity=1,
            reagents=[Reagent(item_id=1, name="Herb A", quantity=10)],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)

    assert len(results) == 1
    assert results[0].profit < 0


def test_spread_missing_price_skips_recipe():
    store = FakeStore({
        1: _snap(1, 100),
        # item 2 is missing from AH
    })
    recipes = [
        Recipe(
            name="Missing Reagent",
            output_item_id=100,
            output_quantity=1,
            reagents=[
                Reagent(item_id=1, name="Herb A", quantity=10),
                Reagent(item_id=2, name="Herb B", quantity=5),
            ],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)
    assert len(results) == 0


def test_spread_zero_material_cost_raises_data_error():
    store = FakeStore({
        1: _snap(1, 0),  # reagent has zero price (stale or bad data)
        100: _snap(100, 5000),
    })
    recipes = [
        Recipe(
            name="Zero Cost Bug",
            output_item_id=100,
            output_quantity=1,
            reagents=[Reagent(item_id=1, name="Free Herb", quantity=10)],
        )
    ]
    service = SpreadService(price_store=store)
    with pytest.raises(DataError):
        service.analyze(recipes)


def test_spread_logs_warning_when_skipping_missing_price(caplog):
    import logging
    store = FakeStore({1: _snap(1, 100), 100: _snap(100, 5000)})  # item 2 missing
    recipes = [
        Recipe(
            name="Skipped Recipe",
            output_item_id=100,
            output_quantity=1,
            reagents=[
                Reagent(item_id=1, name="Herb A", quantity=10),
                Reagent(item_id=2, name="Herb B", quantity=5),
            ],
        )
    ]
    service = SpreadService(price_store=store)
    with caplog.at_level(logging.WARNING, logger="wow_ah.services.spread_service"):
        results = service.analyze(recipes)
    assert results == []
    assert any("Skipped Recipe" in r.message for r in caplog.records)


def test_spread_sorted_by_margin():
    store = FakeStore({
        1: _snap(1, 100),
        2: _snap(2, 100),
        100: _snap(100, 5000),
        200: _snap(200, 2000),
    })
    recipes = [
        Recipe(name="Low Margin", output_item_id=200, output_quantity=1,
               reagents=[Reagent(item_id=1, name="H", quantity=10)]),
        Recipe(name="High Margin", output_item_id=100, output_quantity=1,
               reagents=[Reagent(item_id=2, name="H", quantity=10)]),
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)
    assert results[0].recipe_name == "High Margin"
    assert results[1].recipe_name == "Low Margin"
