from datetime import datetime, timezone

import pytest

from wow_ah.exceptions.base import DataError
from wow_ah.schemas.prices import CommodityListing, FetchResult, PriceSnapshot
from wow_ah.services.fetch_service import FetchService, aggregate_listings


class FakeMarketData:
    def __init__(self, listings: list[CommodityListing]):
        self._listings = listings

    def fetch_commodities(self) -> list[CommodityListing]:
        return self._listings

    def get_item(self, item_id: int):
        return None


class FakeStore:
    def __init__(self):
        self.saved: list[PriceSnapshot] = []
        self._last_ts: str | None = None

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        self.saved.extend(snapshots)

    def get_price_history(self, item_id, start, end):
        return []

    def get_latest_prices(self, item_ids):
        return {}

    def get_last_fetch_timestamp(self) -> str | None:
        return self._last_ts


def test_aggregate_listings_single_item():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=100, unit_price=2000, quantity=5),
        CommodityListing(item_id=100, unit_price=1500, quantity=3),
    ]
    result = aggregate_listings(listings, "2026-04-10T14:00:00Z")
    assert len(result) == 1
    snap = result[0]
    assert snap.item_id == 100
    assert snap.min_price == 1000
    assert snap.total_quantity == 18
    assert snap.num_auctions == 3
    # weighted mean = (1000*10 + 2000*5 + 1500*3) / 18 = 24500/18 = 1361
    assert snap.mean_price == 1361


def test_aggregate_listings_multiple_items():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=200, unit_price=5000, quantity=20),
    ]
    result = aggregate_listings(listings, "2026-04-10T14:00:00Z")
    assert len(result) == 2
    ids = {s.item_id for s in result}
    assert ids == {100, 200}


def test_fetch_service_invalid_last_timestamp_raises_data_error():
    market = FakeMarketData([])
    store = FakeStore()
    store._last_ts = "not-a-timestamp"
    service = FetchService(market_data=market, price_store=store, watchlist={100})
    with pytest.raises(DataError):
        service.fetch()


def test_fetch_service_filters_watchlist():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=200, unit_price=2000, quantity=5),
        CommodityListing(item_id=999, unit_price=500, quantity=100),
    ]
    market = FakeMarketData(listings)
    store = FakeStore()
    service = FetchService(market_data=market, price_store=store, watchlist={100, 200})

    service.fetch()

    saved_ids = {s.item_id for s in store.saved}
    assert saved_ids == {100, 200}
    assert 999 not in saved_ids


def test_aggregate_listings_zero_total_quantity_raises():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=0),
    ]
    with pytest.raises(DataError):
        aggregate_listings(listings, "2026-04-10T14:00:00Z")


def test_fetch_returns_fetch_result_when_saved():
    listings = [CommodityListing(item_id=100, unit_price=1000, quantity=10)]
    market = FakeMarketData(listings)
    store = FakeStore()
    service = FetchService(market_data=market, price_store=store, watchlist={100})
    result = service.fetch()
    assert isinstance(result, FetchResult)
    assert result.saved == 1
    assert result.skipped_throttle is False


def test_fetch_returns_throttled_result_when_recent():
    market = FakeMarketData([])
    store = FakeStore()
    store._last_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    service = FetchService(market_data=market, price_store=store, watchlist={100})
    result = service.fetch()
    assert result.skipped_throttle is True
    assert result.saved == 0


def test_fetch_returns_empty_result_when_no_watchlist_match():
    listings = [CommodityListing(item_id=999, unit_price=1000, quantity=10)]
    market = FakeMarketData(listings)
    store = FakeStore()
    service = FetchService(market_data=market, price_store=store, watchlist={100})
    result = service.fetch()
    assert result.skipped_throttle is False
    assert result.saved == 0
