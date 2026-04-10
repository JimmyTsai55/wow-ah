import csv
from io import StringIO

from wow_ah.schemas.prices import PriceSnapshot, SpreadResult, TrendResult
from wow_ah.export.csv_export import snapshots_to_csv, spreads_to_csv
from wow_ah.export.formatters import format_copper, format_spreads_table, format_trends_table


def test_snapshots_to_csv():
    snapshots = [
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1500, median_price=1600, mean_price=1700, total_quantity=500, num_auctions=10),
        PriceSnapshot(item_id=200, timestamp="2026-04-10T14:00:00Z", min_price=2500, median_price=2600, mean_price=2700, total_quantity=300, num_auctions=5),
    ]
    output = snapshots_to_csv(snapshots)
    reader = csv.DictReader(StringIO(output))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["item_id"] == "100"
    assert rows[0]["min_price"] == "1500"


def test_spreads_to_csv():
    spreads = [
        SpreadResult(recipe_name="Flask A", output_item_id=100, material_cost=2000, product_price=5000, profit=2750, margin_pct=137.5),
    ]
    output = spreads_to_csv(spreads)
    reader = csv.DictReader(StringIO(output))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["recipe_name"] == "Flask A"
    assert rows[0]["profit"] == "2750"


def test_format_copper():
    assert format_copper(12345678) == "1234g 56s 78c"
    assert format_copper(10000) == "1g 0s 0c"
    assert format_copper(99) == "0g 0s 99c"
    assert format_copper(0) == "0g 0s 0c"


def test_format_copper_negative():
    assert format_copper(-15000) == "-1g 50s 0c"
    assert format_copper(-12345678) == "-1234g 56s 78c"


def test_format_spreads_table():
    spreads = [
        SpreadResult(recipe_name="Flask A", output_item_id=100, material_cost=20000, product_price=50000, profit=27500, margin_pct=137.5),
    ]
    table = format_spreads_table(spreads)
    assert "Flask A" in table
    assert "137.5" in table


def test_format_trends_table():
    trends = [
        TrendResult(item_id=100, current_price=15000, ma_24h=14500.0, ma_72h=14200.0,
                    ma_7d=14000.0, std_7d=1200.0, percentile_7d=75.0, signal="HOLD"),
    ]
    item_names = {100: "Mycobloom"}
    table = format_trends_table(trends, item_names)
    assert "Mycobloom" in table
    assert "HOLD" in table
