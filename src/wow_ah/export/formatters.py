from tabulate import tabulate

from wow_ah.schemas.prices import SpreadResult, TrendResult


def format_copper(copper: int) -> str:
    """Format copper value as WoW gold/silver/copper string."""
    gold = copper // 10000
    silver = (copper % 10000) // 100
    remainder = copper % 100
    return f"{gold}g {silver}s {remainder}c"


def format_spreads_table(spreads: list[SpreadResult]) -> str:
    """Format spread results as a CLI table."""
    rows = []
    for s in spreads:
        rows.append([
            s.recipe_name,
            format_copper(s.material_cost),
            format_copper(s.product_price),
            format_copper(s.profit),
            f"{s.margin_pct:.1f}%",
        ])
    return tabulate(
        rows,
        headers=["Recipe", "Material Cost", "Product Price", "Profit", "Margin"],
        tablefmt="simple",
    )


def format_trends_table(trends: list[TrendResult], item_names: dict[int, str]) -> str:
    """Format trend results as a CLI table."""
    rows = []
    for t in trends:
        name = item_names.get(t.item_id, str(t.item_id))
        rows.append([
            name,
            format_copper(t.current_price),
            format_copper(int(t.ma_24h)),
            format_copper(int(t.ma_7d)),
            format_copper(int(t.std_7d)),
            f"{t.percentile_7d:.0f}%",
            t.signal,
        ])
    return tabulate(
        rows,
        headers=["Item", "Current", "MA-24h", "MA-7d", "Std-7d", "Pct", "Signal"],
        tablefmt="simple",
    )
