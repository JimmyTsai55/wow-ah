from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.schemas.prices import PriceSnapshot


def test_init_creates_tables(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    import sqlite3
    conn = sqlite3.connect(tmp_db)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "price_snapshots" in tables
    assert "items" in tables
    assert "recipes" in tables
    assert "recipe_reagents" in tables


def test_save_and_get_latest(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    snapshots = [
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1000, median_price=1200, mean_price=1300, total_quantity=500, num_auctions=10),
        PriceSnapshot(item_id=200, timestamp="2026-04-10T14:00:00Z", min_price=2000, median_price=2500, mean_price=2600, total_quantity=300, num_auctions=5),
    ]
    adapter.save_snapshots(snapshots)

    latest = adapter.get_latest_prices([100, 200])
    assert 100 in latest
    assert 200 in latest
    assert latest[100].min_price == 1000
    assert latest[200].min_price == 2000


def test_get_price_history(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T10:00:00Z", min_price=900),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T11:00:00Z", min_price=1000),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T12:00:00Z", min_price=1100),
    ])

    history = adapter.get_price_history(100, "2026-04-10T10:00:00Z", "2026-04-10T12:00:00Z")
    assert len(history) == 3
    assert history[0].min_price == 900
    assert history[2].min_price == 1100


def test_get_price_history_filters_by_range(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T10:00:00Z", min_price=900),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T11:00:00Z", min_price=1000),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1100),
    ])

    history = adapter.get_price_history(100, "2026-04-10T10:00:00Z", "2026-04-10T12:00:00Z")
    assert len(history) == 2


def test_get_last_fetch_timestamp_empty(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    assert adapter.get_last_fetch_timestamp() is None


def test_get_last_fetch_timestamp(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1000),
    ])
    assert adapter.get_last_fetch_timestamp() == "2026-04-10T14:00:00Z"


def test_get_latest_prices_missing_item(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    latest = adapter.get_latest_prices([999])
    assert 999 not in latest
