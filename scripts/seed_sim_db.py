"""Seed a SYNTHETIC price database for experimenting with the multi-agent advisor.

This writes a SEPARATE database (default data/wow_ah_sim.db) so the real
data/wow_ah.db is never touched. The synthetic data is engineered to exercise
every agent:

  - 7 days of hourly history per item -> trend analysis has enough points
  - the newest snapshot is the current UTC hour -> the freshness gate passes
  - a mix of BUY / SELL / HOLD signals across items
  - a mix of profitable and loss-making recipes for the spread analysis

It is NOT real market data. Use only to experiment with how the agents decide.

Usage:
    python scripts/seed_sim_db.py [db_path]
    DB_PATH=data/wow_ah_sim.db wow-ah advise
"""

import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.recipes.loader import get_watchlist_item_ids, load_all_recipes
from wow_ah.schemas.prices import PriceSnapshot

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/wow_ah_sim.db"
HOURS = 24 * 7  # 168 hourly points = 7 days
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Force the final (current) price into one of these zones to produce a signal.
# With ~6% noise, ma-1.5*std ~ base*0.92 and ma+1.5*std ~ base*1.08, so:
END_MULT = {"BUY": 0.80, "HOLD": 1.00, "SELL": 1.20}
SIGNALS = ["HOLD", "BUY", "SELL"]

# Rotate recipe output base = material_cost * factor to mix profit and loss.
FACTORS = [1.35, 1.10, 0.78, 1.22, 0.92, 1.45, 0.85, 1.15, 0.70, 1.30, 1.05, 0.88, 1.50]

rng = random.Random(42)  # deterministic / reproducible


def main() -> None:
    recipes = load_all_recipes()

    reagent_ids = sorted({g.item_id for r in recipes for g in r.reagents})
    reagent_base = {
        iid: 60_000 + (iid % 7) * 25_000 + i * 4_000  # ~6g .. ~25g in copper
        for i, iid in enumerate(reagent_ids)
    }

    def material_cost(recipe) -> int:
        return sum(reagent_base.get(g.item_id, 80_000) * g.quantity for g in recipe.reagents)

    output_base = {}
    for i, r in enumerate(recipes):
        per_unit = material_cost(r) * FACTORS[i % len(FACTORS)] / max(1, r.output_quantity)
        output_base[r.output_item_id] = max(10_000, int(per_unit))

    item_base = {**reagent_base, **output_base}
    # sanity: every tracked item has a base price
    assert set(item_base) >= get_watchlist_item_ids(recipes)

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    snapshots: list[PriceSnapshot] = []
    for idx, iid in enumerate(sorted(item_base)):
        base = item_base[iid]
        signal = SIGNALS[idx % len(SIGNALS)]
        for h in range(HOURS):
            ts = (now - timedelta(hours=HOURS - 1 - h)).strftime(TS_FMT)
            if h == HOURS - 1:
                price = int(base * END_MULT[signal])  # force the current-hour signal
            else:
                wobble = 1 + rng.uniform(-0.06, 0.06) + 0.03 * math.sin(h / 12)
                price = int(base * wobble)
            price = max(1, price)
            snapshots.append(
                PriceSnapshot(
                    item_id=iid,
                    timestamp=ts,
                    min_price=price,
                    median_price=int(price * 1.02),
                    mean_price=int(price * 1.03),
                    total_quantity=rng.randint(50, 500),
                    num_auctions=rng.randint(5, 80),
                )
            )

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    store = SQLiteAdapter(DB_PATH)
    store.save_snapshots(snapshots)
    print(f"Wrote {len(snapshots)} synthetic snapshots for {len(item_base)} items to {DB_PATH}")
    print(f"Latest timestamp: {store.get_last_fetch_timestamp()}")
    print(f"Run agents on it with:  DB_PATH={DB_PATH} OPENAI_DEFAULT_MODEL=gpt-4o-mini wow-ah advise")


if __name__ == "__main__":
    main()
