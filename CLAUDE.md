# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`wow-ah` is a Python 3.12+ CLI tool that analyzes World of Warcraft (Retail / The War Within) auction house data fetched from the Blizzard Game Data API. It supports two arbitrage strategies — recipe material-vs-product spread analysis, and temporal price-signal detection (BUY / SELL / HOLD) based on moving averages, standard deviation, and percentile rank.

The project follows Clean Architecture; the design rationale lives in [docs/superpowers/specs/2026-04-10-wow-ah-arbitrage-bot-design.md](docs/superpowers/specs/2026-04-10-wow-ah-arbitrage-bot-design.md).

## Commands

Package management uses `uv` (a `uv.lock` is committed). The Typer entry point `wow-ah` is registered as a project script.

```bash
uv sync                            # install deps (including dev group)
uv run wow-ah fetch                # fetch commodities and save snapshots (throttled to once/hour)
uv run wow-ah prices               # list latest prices for watchlist items
uv run wow-ah spreads              # show recipe profit margins (sorted desc)
uv run wow-ah trends               # show MA/std/percentile-based BUY/SELL signals
uv run wow-ah export               # dump price history to data/exports/prices.csv
uv run wow-ah recipes list         # list loaded recipes
uv run wow-ah ask "<問題>"          # 多 agent 問答（需 OPENAI_API_KEY）
uv run wow-ah advise               # 主動產生交易建議報告
uv run wow-ah mcp                  # 啟動 MCP server 暴露分析工具

uv run pytest                      # full test suite (config in pyproject.toml; src on path)
uv run pytest tests/test_spread_service.py::test_name   # single test
uv run pytest --cov=wow_ah         # coverage (pytest-cov is in dev deps)
```

A `.env` file with `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` / `BLIZZARD_REGION` (default `us`) is required for any command that calls the live API (i.e. `fetch`). Other commands only read the local SQLite DB at `data/wow_ah.db` (overridable via `DB_PATH`). `OPENAI_API_KEY` is additionally required for `ask` / `advise`; each agent's model can be overridden via `WOW_AH_ORCHESTRATOR_MODEL` / `WOW_AH_RECIPE_MODEL` / `WOW_AH_TREND_MODEL` / `WOW_AH_RISK_MODEL` (default `gpt-4.1-nano`, or set globally via `OPENAI_DEFAULT_MODEL`).

## Architecture

Dependency direction is enforced by layer. A layer may depend only on the layers listed in "Can depend on"; reverse imports break the design and are caught in code review.

| Layer | Path | Responsibility | Can depend on |
|---|---|---|---|
| Agent | [src/wow_ah/agent/](src/wow_ah/agent/) | OpenAI 多 agent 協作（orchestrator + 配方/趨勢/風險專家）、確定性新鮮度關卡、CLI/MCP 工具 | services, adapters, recipes, schemas, core, protocols, openai/mcp SDK |
| CLI | [src/wow_ah/cli.py](src/wow_ah/cli.py) | Typer command wiring; assembles store + market + recipes and calls services | services, adapters, recipes, export, schemas |
| Services | [src/wow_ah/services/](src/wow_ah/services/) | All business logic (fetch / spread / temporal) | protocols, schemas |
| Protocols | [src/wow_ah/protocols/](src/wow_ah/protocols/) | `MarketDataProtocol`, `PriceStoreProtocol` — only abstraction layer | schemas only |
| Adapters | [src/wow_ah/adapters/](src/wow_ah/adapters/) | `BlizzardAdapter` (HTTPS + OAuth), `SQLiteAdapter` (storage) | core, schemas, exceptions, external SDKs |
| Core | [src/wow_ah/core/](src/wow_ah/core/) | `pydantic-settings` config, OAuth2 `TokenManager` with caching | external SDKs, exceptions |
| Schemas | [src/wow_ah/schemas/](src/wow_ah/schemas/) | Plain `@dataclass` DTOs — **no logic, no other internal imports** | nothing |
| Export | [src/wow_ah/export/](src/wow_ah/export/) | CSV writers, tabulate-based table formatters | schemas |
| Exceptions | [src/wow_ah/exceptions/](src/wow_ah/exceptions/) | `AppException` base + `APIError` / `DataError`; centralized message constants | nothing |

Services are tested by passing in `FakeMarketData` / `FakeStore` classes that satisfy the protocols structurally (see [tests/test_fetch_service.py](tests/test_fetch_service.py)) — there are no `unittest.mock` calls in the suite and no test should hit the network.

### Domain conventions

- **Money is integer copper end-to-end.** Conversion to `Ng Xs Yc` happens only at display time via `format_copper` in [src/wow_ah/export/formatters.py](src/wow_ah/export/formatters.py). Never store or compute with floats for prices.
- **Timestamps are ISO 8601 UTC strings** (`%Y-%m-%dT%H:%M:%SZ`) at storage and protocol boundaries. Services convert to/from `datetime` internally and always use `timezone.utc`.
- **`FetchService.fetch()` is throttled** by hour: if the most recent snapshot timestamp falls in the current UTC hour, it writes nothing and returns a `FetchResult` with `skipped_throttle=True` (distinguishing throttling from a fetch that simply matched no watchlist items). Pass `skip_if_same_hour=False` to override.
- **The watchlist is derived from recipes**, not configured separately. `get_watchlist_item_ids(recipes)` in [src/wow_ah/recipes/loader.py](src/wow_ah/recipes/loader.py) collects every `output_item_id` and reagent `item_id`; adding a recipe is the way to start tracking a new item.
- **Recipe JSON files are auto-merged.** `load_all_recipes()` globs `*.json` from [src/wow_ah/recipes/data/](src/wow_ah/recipes/data/) (currently `alchemy.json`, `cooking.json`) and concatenates them. New recipe categories should be a new JSON file in that directory, not edits to existing ones.
- **AH fee** is the single integer constant `AH_FEE_PCT = 5` (percent) in [src/wow_ah/services/spread_service.py](src/wow_ah/services/spread_service.py); the calculation uses integer math (`price * AH_FEE_PCT // 100`) to preserve the integer-copper invariant.
- **Temporal signal thresholds** (`MIN_DATA_POINTS=24`, `STD_MULTIPLIER=1.5`, `BUY_PERCENTILE=10`, `SELL_PERCENTILE=90`) live as module constants at the top of [src/wow_ah/services/temporal_service.py](src/wow_ah/services/temporal_service.py); tune them there.

### Error handling

Exceptions raise an `AppException` subclass (`APIError`, `DataError`) with a message produced from a class-level constant in [src/wow_ah/exceptions/messages.py](src/wow_ah/exceptions/messages.py). When adding new error sites, add the template to the relevant `*ErrorMessages` class and `.format(...)` it at the raise site — do not inline literal strings.

Conventions by layer:

- **CLI commands are wrapped with the `_handle_errors` decorator** in [src/wow_ah/cli.py](src/wow_ah/cli.py), which catches `AppException`, prints `Error: <message>` to stderr, and exits 1. Apply it (below `@app.command()`) to every new command.
- **Adapters never let `sqlite3.Error` escape** — `SQLiteAdapter` wraps every DB operation and re-raises as `DataError` with the `STORAGE_ERROR` template.
- **Services distinguish skip from fail**: expected gaps (recipe missing a price, item with too little history) are skipped with a module-level `logger.warning(...)` and processing continues; data that violates an invariant (zero total quantity, unparseable timestamp, zero material cost) raises `DataError`. The CLI configures `logging.basicConfig(level=WARNING)` so these warnings reach the user.

## Notes on existing data

`data/wow_ah.db` is a real, gitignored SQLite database accumulated from live `fetch` runs. The schema in [src/wow_ah/adapters/sqlite_adapter.py](src/wow_ah/adapters/sqlite_adapter.py) defines `recipes` and `recipe_reagents` tables, but recipes are currently sourced from the JSON files — those DB tables are reserved for future use and may be empty in practice. Verify before writing code that reads from them.
