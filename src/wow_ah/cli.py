import functools
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from wow_ah.adapters.blizzard_adapter import BlizzardAdapter
from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.core.auth import TokenManager
from wow_ah.core.config import get_settings
from wow_ah.exceptions.base import AppException
from wow_ah.export.csv_export import snapshots_to_csv
from wow_ah.export.formatters import format_copper, format_spreads_table, format_trends_table
from wow_ah.recipes.loader import get_watchlist_item_ids, load_all_recipes
from wow_ah.schemas.recipes import Recipe
from wow_ah.services.fetch_service import FetchService
from wow_ah.services.spread_service import SpreadService
from wow_ah.services.temporal_service import TemporalService

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

app = typer.Typer(help="WoW Auction House arbitrage analysis tool")
recipes_app = typer.Typer(help="Manage recipe definitions")
app.add_typer(recipes_app, name="recipes")


def _handle_errors(func):
    """Wrap a CLI command so AppException becomes a clean stderr message + exit 1."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppException as e:
            typer.echo(f"Error: {e.message}", err=True)
            raise typer.Exit(code=1)
    return wrapper


def _get_store() -> SQLiteAdapter:
    settings = get_settings()
    return SQLiteAdapter(settings.db_path)


def _get_recipes() -> list[Recipe]:
    return load_all_recipes()


def _get_item_names(recipes: list[Recipe]) -> dict[int, str]:
    """Build item_id -> name mapping from recipe definitions."""
    names: dict[int, str] = {}
    for recipe in recipes:
        names[recipe.output_item_id] = recipe.name
        for reagent in recipe.reagents:
            names[reagent.item_id] = reagent.name
    return names


def _get_market() -> BlizzardAdapter:
    settings = get_settings()
    token_mgr = TokenManager(settings.blizzard_client_id, settings.blizzard_client_secret)
    return BlizzardAdapter(token_mgr, settings.blizzard_region)


@app.command()
@_handle_errors
def fetch():
    """Fetch commodity prices from Blizzard API and store to database."""
    store = _get_store()
    market = _get_market()
    recipes = _get_recipes()
    watchlist = get_watchlist_item_ids(recipes)

    service = FetchService(market_data=market, price_store=store, watchlist=watchlist)
    result = service.fetch()

    if result.skipped_throttle:
        typer.echo("Throttled: already fetched this hour. Skipped.")
    elif result.saved == 0:
        typer.echo("No matching items in this fetch.")
    else:
        typer.echo(f"Saved {result.saved} price snapshots.")


@app.command()
@_handle_errors
def prices(
    item: str = typer.Option(None, help="Filter by item name (substring match)"),
    hours: int = typer.Option(24, help="Hours of history to show"),
):
    """Show recent prices for tracked items."""
    store = _get_store()
    recipes = _get_recipes()
    watchlist = get_watchlist_item_ids(recipes)
    item_names = _get_item_names(recipes)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    for item_id in sorted(watchlist):
        name = item_names.get(item_id, str(item_id))
        if item and item.lower() not in name.lower():
            continue
        history = store.get_price_history(item_id, start, end)
        if not history:
            continue
        latest = history[-1]
        typer.echo(f"  {name} [{item_id}] {format_copper(latest.min_price)} (min)  |  {len(history)} snapshots in {hours}h")


@app.command()
@_handle_errors
def spreads(
    min_margin: float = typer.Option(0.0, help="Minimum margin % to show"),
):
    """Show recipe profit margins sorted by profitability."""
    store = _get_store()
    recipes = _get_recipes()
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)

    filtered = [r for r in results if r.margin_pct >= min_margin]
    if not filtered:
        typer.echo("No recipes with sufficient margin found.")
        return

    typer.echo(format_spreads_table(filtered))


@app.command()
@_handle_errors
def trends(
    item: str = typer.Option(None, help="Filter by item name"),
    days: int = typer.Option(7, help="Days of history for analysis"),
):
    """Show price trends with buy/sell signals."""
    store = _get_store()
    recipes = _get_recipes()
    watchlist = get_watchlist_item_ids(recipes)
    item_names = _get_item_names(recipes)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    service = TemporalService(price_store=store)
    results = service.analyze(item_ids=list(watchlist), now=now, history_hours=days * 24)

    if item:
        results = [r for r in results if item.lower() in item_names.get(r.item_id, "").lower()]

    if not results:
        typer.echo("Insufficient data for trend analysis. Accumulate more snapshots.")
        return

    typer.echo(format_trends_table(results, item_names))


@app.command()
@_handle_errors
def export(
    days: int = typer.Option(30, help="Days of history to export"),
    output: str = typer.Option("data/exports/prices.csv", help="Output file path"),
):
    """Export price history to CSV."""
    store = _get_store()
    recipes = _get_recipes()
    watchlist = get_watchlist_item_ids(recipes)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    all_snapshots = []
    for item_id in sorted(watchlist):
        all_snapshots.extend(store.get_price_history(item_id, start, end))

    if not all_snapshots:
        typer.echo("No data to export.")
        return

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(snapshots_to_csv(all_snapshots))
    typer.echo(f"Exported {len(all_snapshots)} snapshots to {output}")


@recipes_app.command("list")
@_handle_errors
def recipes_list():
    """List loaded recipes."""
    recipes = _get_recipes()
    for recipe in recipes:
        reagent_str = ", ".join(f"{r.name} x{r.quantity}" for r in recipe.reagents)
        typer.echo(f"  {recipe.name} -> [{recipe.output_item_id}]")
        typer.echo(f"    Reagents: {reagent_str}")
