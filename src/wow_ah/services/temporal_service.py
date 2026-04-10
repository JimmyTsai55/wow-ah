import statistics
from datetime import datetime, timedelta, timezone

from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import PriceSnapshot, TrendResult

MIN_DATA_POINTS = 24  # need at least 24h of data
STD_MULTIPLIER = 1.5
BUY_PERCENTILE = 10
SELL_PERCENTILE = 90


def _ma(prices: list[int], count: int) -> float:
    """Moving average of the last `count` values."""
    subset = prices[-count:] if len(prices) >= count else prices
    return statistics.mean(subset)


class TemporalService:
    """Analyzes price trends and generates buy/sell signals."""

    def __init__(self, price_store: PriceStoreProtocol) -> None:
        self._store = price_store

    def analyze(
        self,
        item_ids: list[int],
        now: str,
        history_hours: int = 168,  # 7 days default
    ) -> list[TrendResult]:
        """Analyze price trends for the given items."""
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        start_dt = now_dt - timedelta(hours=history_hours)
        start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        results = []
        for item_id in item_ids:
            history = self._store.get_price_history(item_id, start, now)
            if len(history) < MIN_DATA_POINTS:
                continue

            prices = [s.min_price for s in history]
            current = prices[-1]

            ma_24h = _ma(prices, 24)
            ma_72h = _ma(prices, 72)
            ma_7d = statistics.mean(prices)  # full window = 7 days
            std_7d = statistics.pstdev(prices)

            # Percentile: % of historical prices <= current price
            below = sum(1 for p in prices if p <= current)
            percentile_7d = below / len(prices) * 100

            signal = self._compute_signal(current, ma_7d, std_7d, percentile_7d)

            results.append(
                TrendResult(
                    item_id=item_id,
                    current_price=current,
                    ma_24h=ma_24h,
                    ma_72h=ma_72h,
                    ma_7d=ma_7d,
                    std_7d=std_7d,
                    percentile_7d=percentile_7d,
                    signal=signal,
                )
            )

        return results

    def _compute_signal(
        self, current: int, ma_7d: float, std_7d: float, percentile_7d: float
    ) -> str:
        if std_7d == 0:
            return "HOLD"
        if current < ma_7d - STD_MULTIPLIER * std_7d or percentile_7d < BUY_PERCENTILE:
            return "BUY"
        if current > ma_7d + STD_MULTIPLIER * std_7d or percentile_7d > SELL_PERCENTILE:
            return "SELL"
        return "HOLD"
