from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import SpreadResult
from wow_ah.schemas.recipes import Recipe

AH_FEE_RATE = 0.05


class SpreadService:
    """Analyzes material-vs-product price spreads for recipes."""

    def __init__(self, price_store: PriceStoreProtocol) -> None:
        self._store = price_store

    def analyze(self, recipes: list[Recipe]) -> list[SpreadResult]:
        """Compute profit margins for all recipes. Returns sorted by margin descending."""
        # Collect all item IDs we need prices for
        all_ids: set[int] = set()
        for recipe in recipes:
            all_ids.add(recipe.output_item_id)
            for reagent in recipe.reagents:
                all_ids.add(reagent.item_id)

        prices = self._store.get_latest_prices(list(all_ids))

        results = []
        for recipe in recipes:
            # Skip if any price is missing
            if recipe.output_item_id not in prices:
                continue
            if any(r.item_id not in prices for r in recipe.reagents):
                continue

            material_cost = sum(
                prices[r.item_id].min_price * r.quantity for r in recipe.reagents
            )
            product_price = prices[recipe.output_item_id].min_price * recipe.output_quantity
            ah_fee = int(product_price * AH_FEE_RATE)
            profit = product_price - ah_fee - material_cost
            margin_pct = (profit / material_cost * 100) if material_cost > 0 else 0.0

            results.append(
                SpreadResult(
                    recipe_name=recipe.name,
                    output_item_id=recipe.output_item_id,
                    material_cost=material_cost,
                    product_price=product_price,
                    profit=profit,
                    margin_pct=margin_pct,
                )
            )

        results.sort(key=lambda r: r.margin_pct, reverse=True)
        return results
