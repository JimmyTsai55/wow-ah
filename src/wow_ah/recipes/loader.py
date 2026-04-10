import json
from pathlib import Path

from wow_ah.exceptions.base import DataError
from wow_ah.exceptions.messages import DataErrorMessages
from wow_ah.schemas.recipes import Reagent, Recipe


def load_recipes(file_path: str) -> list[Recipe]:
    """Load recipes from a JSON file."""
    path = Path(file_path)
    if not path.exists():
        raise DataError(
            DataErrorMessages.RECIPE_FILE_INVALID.format(error=f"File not found: {file_path}")
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise DataError(
            DataErrorMessages.RECIPE_FILE_INVALID.format(error=str(e))
        ) from e

    recipes = []
    for entry in data.get("recipes", []):
        reagents = [
            Reagent(
                item_id=r["item_id"],
                name=r["name"],
                quantity=r["quantity"],
            )
            for r in entry.get("reagents", [])
        ]
        recipes.append(
            Recipe(
                name=entry["name"],
                output_item_id=entry["output_item_id"],
                output_quantity=entry.get("output_quantity", 1),
                reagents=reagents,
            )
        )
    return recipes


def get_watchlist_item_ids(recipes: list[Recipe]) -> set[int]:
    """Derive the set of item IDs to track from recipe definitions."""
    ids: set[int] = set()
    for recipe in recipes:
        ids.add(recipe.output_item_id)
        for reagent in recipe.reagents:
            ids.add(reagent.item_id)
    return ids
