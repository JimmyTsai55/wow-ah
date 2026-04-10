import statistics
from collections import defaultdict
from datetime import datetime, timezone

from wow_ah.protocols.market_data import MarketDataProtocol
from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import CommodityListing, PriceSnapshot


def aggregate_listings(
    listings: list[CommodityListing], timestamp: str
) -> list[PriceSnapshot]:
    """Aggregate raw auction listings into one PriceSnapshot per item."""
    by_item: dict[int, list[CommodityListing]] = defaultdict(list)
    for listing in listings:
        by_item[listing.item_id].append(listing)

    snapshots = []
    for item_id, item_listings in by_item.items():
        total_qty = sum(l.quantity for l in item_listings)
        min_price = min(l.unit_price for l in item_listings)
        mean_price = sum(l.unit_price * l.quantity for l in item_listings) // total_qty

        # Weighted median: expand to per-unit prices, take median
        expanded = []
        for l in item_listings:
            expanded.extend([l.unit_price] * l.quantity)
        median_price = int(statistics.median(expanded))

        snapshots.append(
            PriceSnapshot(
                item_id=item_id,
                timestamp=timestamp,
                min_price=min_price,
                median_price=median_price,
                mean_price=mean_price,
                total_quantity=total_qty,
                num_auctions=len(item_listings),
            )
        )
    return snapshots


class FetchService:
    """Orchestrates fetching market data, filtering, and storing."""

    def __init__(
        self,
        market_data: MarketDataProtocol,
        price_store: PriceStoreProtocol,
        watchlist: set[int],
    ) -> None:
        self._market_data = market_data
        self._price_store = price_store
        self._watchlist = watchlist

    def fetch(self) -> int:
        """Fetch, filter, aggregate, and store. Returns number of snapshots saved."""
        all_listings = self._market_data.fetch_commodities()
        filtered = [l for l in all_listings if l.item_id in self._watchlist]

        if not filtered:
            return 0

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshots = aggregate_listings(filtered, timestamp)
        self._price_store.save_snapshots(snapshots)
        return len(snapshots)
