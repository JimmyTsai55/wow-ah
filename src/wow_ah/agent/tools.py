import json
from datetime import datetime, timedelta

from wow_ah.recipes.loader import get_watchlist_item_ids
from wow_ah.schemas.recipes import Recipe
from wow_ah.services.spread_service import SpreadService
from wow_ah.services.temporal_service import TemporalService

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _item_names(recipes: list[Recipe]) -> dict[int, str]:
    names: dict[int, str] = {}
    for recipe in recipes:
        names[recipe.output_item_id] = recipe.name
        for reagent in recipe.reagents:
            names[reagent.item_id] = reagent.name
    return names


def spreads_json(store, recipes: list[Recipe], min_margin: float = 0.0) -> str:
    """Recipe profit spreads (after AH fee), sorted by margin descending."""
    results = SpreadService(price_store=store).analyze(recipes)
    payload = [
        {
            "recipe_name": r.recipe_name,
            "output_item_id": r.output_item_id,
            "material_cost": r.material_cost,
            "product_price": r.product_price,
            "profit": r.profit,
            "margin_pct": round(r.margin_pct, 2),
        }
        for r in results
        if r.margin_pct >= min_margin
    ]
    return json.dumps(payload, ensure_ascii=False)


def trends_json(store, recipes: list[Recipe], now: str, days: int = 7) -> str:
    """BUY/SELL/HOLD signals per tracked item over `days` of history."""
    watchlist = list(get_watchlist_item_ids(recipes))
    names = _item_names(recipes)
    results = TemporalService(price_store=store).analyze(
        item_ids=watchlist, now=now, history_hours=days * 24
    )
    payload = [
        {
            "item_id": r.item_id,
            "item_name": names.get(r.item_id, str(r.item_id)),
            "current_price": r.current_price,
            "ma_7d": round(r.ma_7d, 2),
            "percentile_7d": round(r.percentile_7d, 2),
            "signal": r.signal,
        }
        for r in results
    ]
    return json.dumps(payload, ensure_ascii=False)


def prices_json(
    store, recipes: list[Recipe], now: str, item: str | None = None, hours: int = 24
) -> str:
    """Latest known price for each tracked item within the last `hours`."""
    watchlist = sorted(get_watchlist_item_ids(recipes))
    names = _item_names(recipes)
    now_dt = datetime.strptime(now, _TS_FMT)
    start = (now_dt - timedelta(hours=hours)).strftime(_TS_FMT)

    payload = []
    for item_id in watchlist:
        name = names.get(item_id, str(item_id))
        if item and item.lower() not in name.lower():
            continue
        history = store.get_price_history(item_id, start, now)
        if not history:
            continue
        latest = history[-1]
        payload.append(
            {
                "item_id": item_id,
                "item_name": name,
                "min_price": latest.min_price,
                "snapshots": len(history),
            }
        )
    return json.dumps(payload, ensure_ascii=False)


def recipes_json(recipes: list[Recipe]) -> str:
    """All loaded recipe definitions."""
    payload = [
        {
            "name": r.name,
            "output_item_id": r.output_item_id,
            "output_quantity": r.output_quantity,
            "reagents": [
                {"item_id": g.item_id, "name": g.name, "quantity": g.quantity}
                for g in r.reagents
            ],
        }
        for r in recipes
    ]
    return json.dumps(payload, ensure_ascii=False)
