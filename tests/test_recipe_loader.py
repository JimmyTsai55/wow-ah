import json

import pytest

from wow_ah.recipes.loader import load_recipes, load_all_recipes, get_watchlist_item_ids
from wow_ah.exceptions.base import DataError


def test_load_recipes(tmp_path):
    recipe_file = tmp_path / "recipes.json"
    recipe_file.write_text(json.dumps({
        "recipes": [
            {
                "name": "Flask of Alchemical Chaos",
                "output_item_id": 212283,
                "output_quantity": 1,
                "reagents": [
                    {"item_id": 210796, "name": "Mycobloom", "quantity": 10},
                    {"item_id": 210799, "name": "Luredrop", "quantity": 5},
                ]
            }
        ]
    }))

    recipes = load_recipes(str(recipe_file))
    assert len(recipes) == 1
    assert recipes[0].name == "Flask of Alchemical Chaos"
    assert recipes[0].output_item_id == 212283
    assert len(recipes[0].reagents) == 2
    assert recipes[0].reagents[0].item_id == 210796


def test_load_recipes_empty(tmp_path):
    recipe_file = tmp_path / "recipes.json"
    recipe_file.write_text(json.dumps({"recipes": []}))
    recipes = load_recipes(str(recipe_file))
    assert recipes == []


def test_load_recipes_file_not_found():
    with pytest.raises(DataError):
        load_recipes("/nonexistent/path.json")


def test_load_recipes_invalid_json(tmp_path):
    recipe_file = tmp_path / "recipes.json"
    recipe_file.write_text("not json")
    with pytest.raises(DataError):
        load_recipes(str(recipe_file))


def test_get_watchlist_item_ids(tmp_path):
    recipe_file = tmp_path / "recipes.json"
    recipe_file.write_text(json.dumps({
        "recipes": [
            {
                "name": "Flask A",
                "output_item_id": 100,
                "output_quantity": 1,
                "reagents": [
                    {"item_id": 1, "name": "Herb A", "quantity": 5},
                    {"item_id": 2, "name": "Herb B", "quantity": 3},
                ]
            },
            {
                "name": "Flask B",
                "output_item_id": 200,
                "output_quantity": 1,
                "reagents": [
                    {"item_id": 2, "name": "Herb B", "quantity": 10},
                    {"item_id": 3, "name": "Ore C", "quantity": 2},
                ]
            }
        ]
    }))

    recipes = load_recipes(str(recipe_file))
    ids = get_watchlist_item_ids(recipes)
    assert ids == {1, 2, 3, 100, 200}


def _write_recipe_file(path, recipes_data):
    path.write_text(json.dumps({"recipes": recipes_data}))


def test_load_all_recipes_merges_files(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_recipe_file(data_dir / "alchemy.json", [
        {"name": "Flask A", "output_item_id": 100, "output_quantity": 1,
         "reagents": [{"item_id": 1, "name": "Herb", "quantity": 5}]}
    ])
    _write_recipe_file(data_dir / "cooking.json", [
        {"name": "Food B", "output_item_id": 200, "output_quantity": 1,
         "reagents": [{"item_id": 2, "name": "Meat", "quantity": 3}]}
    ])

    recipes = load_all_recipes(str(data_dir))
    assert len(recipes) == 2
    names = {r.name for r in recipes}
    assert names == {"Flask A", "Food B"}


def test_load_all_recipes_empty_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with pytest.raises(DataError):
        load_all_recipes(str(data_dir))


def test_load_all_recipes_invalid_dir():
    with pytest.raises(DataError):
        load_all_recipes("/nonexistent/dir")


def test_watchlist_spans_professions(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_recipe_file(data_dir / "alchemy.json", [
        {"name": "Flask", "output_item_id": 100, "output_quantity": 1,
         "reagents": [{"item_id": 1, "name": "Herb", "quantity": 5}]}
    ])
    _write_recipe_file(data_dir / "cooking.json", [
        {"name": "Food", "output_item_id": 200, "output_quantity": 1,
         "reagents": [{"item_id": 2, "name": "Meat", "quantity": 3}]}
    ])

    recipes = load_all_recipes(str(data_dir))
    ids = get_watchlist_item_ids(recipes)
    assert ids == {1, 2, 100, 200}
