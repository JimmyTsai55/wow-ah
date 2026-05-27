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


def load_all_recipes(data_dir: str | None = None) -> list[Recipe]:
    """Load and merge recipes from all JSON files in the data directory."""
    if data_dir is None:
        data_dir = str(Path(__file__).parent / "data")

    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise DataError(
            DataErrorMessages.RECIPE_FILE_INVALID.format(
                error=f"Recipe data directory not found: {data_dir}"
            )
        )

    json_files = sorted(data_path.glob("*.json"))
    if not json_files:
        raise DataError(
            DataErrorMessages.RECIPE_FILE_INVALID.format(
                error=f"No recipe files found in: {data_dir}"
            )
        )

    all_recipes: list[Recipe] = []
    for json_file in json_files:
        all_recipes.extend(load_recipes(str(json_file)))
    return all_recipes


def get_watchlist_item_ids(recipes: list[Recipe]) -> set[int]:
    """Derive the set of item IDs to track from recipe definitions."""
    ids: set[int] = set()
    for recipe in recipes:
        ids.add(recipe.output_item_id)
        for reagent in recipe.reagents:
            ids.add(reagent.item_id)
    return ids
