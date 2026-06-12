import statistics
from datetime import datetime, timedelta, timezone

import pytest

from wow_ah.exceptions.base import DataError
from wow_ah.schemas.prices import PriceSnapshot, TrendResult
from wow_ah.services.temporal_service import TemporalService


def _snaps_from(item_id: int, prices: list[int], end_dt: datetime) -> list[PriceSnapshot]:
    """Generate hourly snapshots ending at end_dt, one per price value."""
    start_dt = end_dt - timedelta(hours=len(prices) - 1)
    return [
        PriceSnapshot(
            item_id=item_id,
            timestamp=(start_dt + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            min_price=p,
        )
        for i, p in enumerate(prices)
    ]


class FakeStore:
    def __init__(self, history: dict[int, list[PriceSnapshot]]):
        self._history = history

    def save_snapshots(self, snapshots):
        pass

    def get_price_history(self, item_id, start, end):
        return [s for s in self._history.get(item_id, []) if start <= s.timestamp <= end]

    def get_latest_prices(self, item_ids):
        result = {}
        for iid in item_ids:
            snaps = self._history.get(iid, [])
            if snaps:
                result[iid] = snaps[-1]
        return result

    def get_last_fetch_timestamp(self):
        return None


def test_trend_result_fields():
    """TrendResult has all required multi-MA fields."""
    r = TrendResult(item_id=1, current_price=100, ma_24h=95.0, ma_72h=90.0,
                    ma_7d=88.0, std_7d=5.0, percentile_7d=75.0, signal="HOLD")
    assert r.ma_24h == 95.0
    assert r.ma_7d == 88.0


def test_trend_buy_signal_low_price():
    # 168 hours of data (7 days), last price drops well below mean - 1.5*std
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [30]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert len(results) == 1
    assert results[0].signal == "BUY"


def test_trend_sell_signal_high_price():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [300]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert results[0].signal == "SELL"


def test_trend_no_signal():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [100]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert results[0].signal == "HOLD"


def test_trend_percentile():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = list(range(1, 169))  # 1..168, increasing hourly over 7 days
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    # Current price is 168, the highest — percentile should be 100%
    assert results[0].percentile_7d == 100.0


def test_trend_invalid_now_raises_data_error():
    store = FakeStore({})
    service = TemporalService(price_store=store)
    with pytest.raises(DataError):
        service.analyze(item_ids=[100], now="garbage-timestamp")


def test_trend_insufficient_data():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    snaps = _snaps_from(100, [100, 101], end)  # only 2 data points
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert len(results) == 0


def test_trend_logs_warning_when_insufficient_history(caplog):
    import logging
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    snaps = _snaps_from(100, [100, 101], end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)
    with caplog.at_level(logging.WARNING, logger="wow_ah.services.temporal_service"):
        service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert any("100" in r.message for r in caplog.records)
