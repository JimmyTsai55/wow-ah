from datetime import datetime

from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.agents import FreshnessResult

MAX_DATA_AGE_HOURS = 6


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_freshness(store: PriceStoreProtocol, now: str) -> FreshnessResult:
    """Deterministic gate: is the newest snapshot recent enough to trust?"""
    last = store.get_last_fetch_timestamp()
    if last is None:
        return FreshnessResult(
            is_fresh=False,
            last_fetch=None,
            age_hours=None,
            message="資料庫沒有任何價格資料，請先執行 `wow-ah fetch`。",
        )

    age_hours = (_parse(now) - _parse(last)).total_seconds() / 3600
    if age_hours > MAX_DATA_AGE_HOURS:
        return FreshnessResult(
            is_fresh=False,
            last_fetch=last,
            age_hours=age_hours,
            message=(
                f"資料已過期：最後一次 fetch 在 {age_hours:.0f} 小時前"
                f"（門檻 {MAX_DATA_AGE_HOURS} 小時）。請先執行 `wow-ah fetch` 再分析。"
            ),
        )

    return FreshnessResult(
        is_fresh=True,
        last_fetch=last,
        age_hours=age_hours,
        message=f"資料新鮮（{age_hours:.0f} 小時前更新）。",
    )
