from wow_ah.agent.freshness import check_freshness, MAX_DATA_AGE_HOURS


class _Store:
    def __init__(self, last):
        self._last = last

    def get_last_fetch_timestamp(self):
        return self._last

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids): return {}


def test_no_data_is_not_fresh():
    result = check_freshness(_Store(None), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is False
    assert result.last_fetch is None
    assert "fetch" in result.message.lower()


def test_recent_data_is_fresh():
    result = check_freshness(_Store("2026-06-14T11:00:00Z"), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is True
    assert result.age_hours == 1.0


def test_stale_data_is_not_fresh():
    old = "2026-06-14T00:00:00Z"  # 12h before noon, > MAX_DATA_AGE_HOURS
    result = check_freshness(_Store(old), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is False
    assert result.age_hours == 12.0
    assert str(MAX_DATA_AGE_HOURS) in result.message
