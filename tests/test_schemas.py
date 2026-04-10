from wow_ah.schemas.prices import CommodityListing, PriceSnapshot, SpreadResult, ItemInfo, TrendResult
from wow_ah.schemas.recipes import Reagent, Recipe


def test_commodity_listing():
    listing = CommodityListing(item_id=210796, unit_price=15000, quantity=200)
    assert listing.item_id == 210796
    assert listing.unit_price == 15000
    assert listing.quantity == 200


def test_price_snapshot_full():
    snap = PriceSnapshot(
        item_id=210796,
        timestamp="2026-04-10T14:00:00Z",
        min_price=14500,
        median_price=15200,
        mean_price=15800,
        total_quantity=5000,
        num_auctions=42,
    )
    assert snap.min_price == 14500
    assert snap.median_price == 15200


def test_price_snapshot_minimal():
    snap = PriceSnapshot(
        item_id=210796,
        timestamp="2026-04-10T14:00:00Z",
        min_price=14500,
    )
    assert snap.median_price is None
    assert snap.mean_price is None
    assert snap.total_quantity is None
    assert snap.num_auctions is None


def test_item_info():
    item = ItemInfo(item_id=210796, name="Mycobloom", quality="Common", item_class="Tradeskill", item_subclass="Herb")
    assert item.name == "Mycobloom"


def test_item_info_minimal():
    item = ItemInfo(item_id=210796, name="Mycobloom")
    assert item.quality is None


def test_spread_result():
    spread = SpreadResult(
        recipe_name="Flask of Alchemical Chaos",
        output_item_id=212283,
        material_cost=150000,
        product_price=200000,
        profit=40000,
        margin_pct=26.67,
    )
    assert spread.profit == 40000
    assert spread.margin_pct == 26.67


def test_trend_result():
    trend = TrendResult(
        item_id=100, current_price=15000,
        ma_24h=14500.0, ma_72h=14200.0, ma_7d=14000.0,
        std_7d=1200.0, percentile_7d=75.0, signal="HOLD",
    )
    assert trend.ma_24h == 14500.0
    assert trend.ma_7d == 14000.0
    assert trend.signal == "HOLD"


def test_reagent():
    reagent = Reagent(item_id=210796, name="Mycobloom", quantity=10)
    assert reagent.quantity == 10


def test_recipe():
    recipe = Recipe(
        name="Flask of Alchemical Chaos",
        output_item_id=212283,
        output_quantity=1,
        reagents=[
            Reagent(item_id=210796, name="Mycobloom", quantity=10),
            Reagent(item_id=210799, name="Luredrop", quantity=5),
        ],
    )
    assert len(recipe.reagents) == 2
    assert recipe.output_quantity == 1
