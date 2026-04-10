from wow_ah.schemas.prices import CommodityListing, PriceSnapshot
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
