from typing import Protocol

from wow_ah.schemas.prices import CommodityListing, ItemInfo


class MarketDataProtocol(Protocol):
    """Abstract interface for market data sources."""

    def fetch_commodities(self) -> list[CommodityListing]:
        """Fetch all commodity auctions from the market."""
        ...

    def get_item(self, item_id: int) -> ItemInfo:
        """Get item metadata by ID."""
        ...
