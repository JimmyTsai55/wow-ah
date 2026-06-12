import logging

from wow_ah.exceptions.base import DataError
from wow_ah.exceptions.messages import DataErrorMessages
from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import SpreadResult
from wow_ah.schemas.recipes import Recipe

AH_FEE_PCT = 5  # 5% AH fee, integer percent — money stays integer copper

logger = logging.getLogger(__name__)


class SpreadService:
    """Analyzes material-vs-product price spreads for recipes."""

    def __init__(self, price_store: PriceStoreProtocol) -> None:
        self._store = price_store

    def analyze(self, recipes: list[Recipe]) -> list[SpreadResult]:
        """Compute profit margins for all recipes. Returns sorted by margin descending."""
        all_ids: set[int] = set()
        for recipe in recipes:
            all_ids.add(recipe.output_item_id)
            for reagent in recipe.reagents:
                all_ids.add(reagent.item_id)

        prices = self._store.get_latest_prices(list(all_ids))

        results = []
        for recipe in recipes:
            if recipe.output_item_id not in prices:
                logger.warning(
                    "Skipping recipe %s: no price for output item %d",
                    recipe.name, recipe.output_item_id,
                )
                continue
            missing_reagents = [r.item_id for r in recipe.reagents if r.item_id not in prices]
            if missing_reagents:
                logger.warning(
                    "Skipping recipe %s: missing price(s) for reagent(s) %s",
                    recipe.name, missing_reagents,
                )
                continue

            material_cost = sum(
                prices[r.item_id].min_price * r.quantity for r in recipe.reagents
            )
            if material_cost == 0:
                raise DataError(
                    DataErrorMessages.ZERO_MATERIAL_COST.format(recipe_name=recipe.name)
                )
            product_price = prices[recipe.output_item_id].min_price * recipe.output_quantity
            ah_fee = product_price * AH_FEE_PCT // 100
            profit = product_price - ah_fee - material_cost
            margin_pct = profit / material_cost * 100

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
