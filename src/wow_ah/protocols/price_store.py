from typing import Protocol

from wow_ah.schemas.prices import PriceSnapshot


class PriceStoreProtocol(Protocol):
    """Abstract interface for price data storage."""

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        """Persist a batch of price snapshots."""
        ...

    def get_price_history(
        self, item_id: int, start: str, end: str
    ) -> list[PriceSnapshot]:
        """Get price history for an item within a time range (ISO 8601)."""
        ...

    def get_latest_prices(self, item_ids: list[int]) -> dict[int, PriceSnapshot]:
        """Get the most recent snapshot for each item ID."""
        ...

    def get_last_fetch_timestamp(self) -> str | None:
        """Get timestamp of the most recent fetch, or None if no data."""
        ...
