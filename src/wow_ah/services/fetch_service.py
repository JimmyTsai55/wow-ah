from collections import defaultdict
from datetime import datetime, timezone

from wow_ah.protocols.market_data import MarketDataProtocol
from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import CommodityListing, PriceSnapshot


def _weighted_median(listings: list[CommodityListing]) -> int:
    """Compute weighted median price without expanding to per-unit list."""
    sorted_listings = sorted(listings, key=lambda l: l.unit_price)
    total_qty = sum(l.quantity for l in sorted_listings)
    target = total_qty / 2
    cumulative = 0
    for l in sorted_listings:
        cumulative += l.quantity
        if cumulative >= target:
            return l.unit_price
    return sorted_listings[-1].unit_price  # shouldn't reach here


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
        median_price = _weighted_median(item_listings)

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

    def fetch(self, skip_if_same_hour: bool = True) -> int:
        """Fetch, filter, aggregate, and store. Returns number of snapshots saved."""
        if skip_if_same_hour:
            last_ts = self._price_store.get_last_fetch_timestamp()
            if last_ts:
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                if last_dt.strftime("%Y-%m-%dT%H") == now_dt.strftime("%Y-%m-%dT%H"):
                    return 0

        all_listings = self._market_data.fetch_commodities()
        filtered = [l for l in all_listings if l.item_id in self._watchlist]

        if not filtered:
            return 0

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshots = aggregate_listings(filtered, timestamp)
        self._price_store.save_snapshots(snapshots)
        return len(snapshots)
