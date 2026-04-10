from dataclasses import dataclass


@dataclass
class CommodityListing:
    """Single auction listing from Blizzard API."""
    item_id: int
    unit_price: int  # copper
    quantity: int


@dataclass
class PriceSnapshot:
    """Aggregated price snapshot per item per fetch."""
    item_id: int
    timestamp: str  # ISO 8601
    min_price: int  # copper
    median_price: int | None = None
    mean_price: int | None = None
    total_quantity: int | None = None
    num_auctions: int | None = None


@dataclass
class ItemInfo:
    """Item metadata cached from Blizzard Item API."""
    item_id: int
    name: str
    quality: str | None = None
    item_class: str | None = None
    item_subclass: str | None = None


@dataclass
class SpreadResult:
    """Profit analysis result for a single recipe."""
    recipe_name: str
    output_item_id: int
    material_cost: int  # copper
    product_price: int  # copper
    profit: int  # copper (after 5% AH fee)
    margin_pct: float  # percentage


@dataclass
class TrendResult:
    """Temporal analysis result for a single item."""
    item_id: int
    current_price: int
    ma_24h: float
    ma_72h: float
    ma_7d: float
    std_7d: float
    percentile_7d: float  # current price percentile in 7-day history
    signal: str  # "BUY", "SELL", or "HOLD"
