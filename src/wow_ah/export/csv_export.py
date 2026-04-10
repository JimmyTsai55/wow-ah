import csv
from io import StringIO

from wow_ah.schemas.prices import PriceSnapshot, SpreadResult


def snapshots_to_csv(snapshots: list[PriceSnapshot]) -> str:
    """Convert price snapshots to CSV string."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["item_id", "timestamp", "min_price", "median_price", "mean_price", "total_quantity", "num_auctions"],
    )
    writer.writeheader()
    for s in snapshots:
        writer.writerow({
            "item_id": s.item_id,
            "timestamp": s.timestamp,
            "min_price": s.min_price,
            "median_price": s.median_price,
            "mean_price": s.mean_price,
            "total_quantity": s.total_quantity,
            "num_auctions": s.num_auctions,
        })
    return output.getvalue()


def spreads_to_csv(spreads: list[SpreadResult]) -> str:
    """Convert spread results to CSV string."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["recipe_name", "output_item_id", "material_cost", "product_price", "profit", "margin_pct"],
    )
    writer.writeheader()
    for s in spreads:
        writer.writerow({
            "recipe_name": s.recipe_name,
            "output_item_id": s.output_item_id,
            "material_cost": s.material_cost,
            "product_price": s.product_price,
            "profit": s.profit,
            "margin_pct": s.margin_pct,
        })
    return output.getvalue()
