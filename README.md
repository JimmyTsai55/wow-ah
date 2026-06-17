# wow-ah

**English** | [繁體中文](README.zh-TW.md)

**WoW Auction House arbitrage analysis tool** — a Python 3.12 CLI that pulls World of Warcraft (Retail / *The War Within*) auction-house data from the Blizzard Game Data API and finds profitable trades, with an optional **OpenAI multi-agent advisor** that turns the raw analysis into prioritized, plain-language recommendations.

> ⚠️ The Blizzard Game Data API is **read-only** — there is no API to buy or list auctions. This tool **analyzes and advises**; you place trades manually in-game.

---

## What it does

Two arbitrage strategies, plus an AI layer on top:

1. **Recipe spread analysis** — compares crafting material cost vs. product sale price (after the 5% AH fee) and ranks recipes by profit margin.
2. **Temporal price signals** — tracks price history and emits **BUY / SELL / HOLD** signals from moving averages, standard deviation, and percentile rank.
3. **Multi-agent advisor** *(optional, needs an OpenAI key)* — an orchestrator delegates to specialist agents (recipe / trend / risk) and synthesizes a Traditional-Chinese recommendation report. Also available as an **MCP server**.

All analysis is **read-only against a local SQLite database**. Money is integer copper end-to-end; timestamps are ISO 8601 UTC.

---

## Architecture

Clean Architecture — dependencies point inward, enforced by layer:

| Layer | Path | Responsibility |
|---|---|---|
| Agent | `src/wow_ah/agent/` | OpenAI multi-agent orchestration + deterministic freshness gate + CLI/MCP tools |
| CLI | `src/wow_ah/cli.py` | Typer command wiring |
| Services | `src/wow_ah/services/` | Business logic (fetch / spread / temporal) |
| Protocols | `src/wow_ah/protocols/` | `MarketDataProtocol`, `PriceStoreProtocol`, `LLMProtocol` |
| Adapters | `src/wow_ah/adapters/` | `BlizzardAdapter` (HTTPS + OAuth2), `SQLiteAdapter` |
| Core | `src/wow_ah/core/` | Settings, OAuth2 token manager |
| Schemas | `src/wow_ah/schemas/` | Plain `@dataclass` DTOs (no logic) |

Tests inject fakes through the protocols — the suite never hits the network (Blizzard or OpenAI).

---

## Install

Requires **Python ≥ 3.12**.

### With uv (recommended — `uv.lock` is committed)

```bash
uv sync                 # install runtime + dev deps
uv run wow-ah --help
```

### With conda / pip

```bash
conda create -n wow-ah python=3.12 -y
conda run -n wow-ah python -m pip install -e ".[dev]"
# or: python -m pip install -r requirements-dev.txt
```

> **conda PATH note:** bare `conda run -n wow-ah pytest|pip|wow-ah` may resolve to a system Python on your `PATH`. Use `conda run -n wow-ah python -m pytest` / `python -m pip`, or `conda activate wow-ah` first.

---

## Configuration

Create a `.env` (see `.env.example`):

```bash
# Blizzard Game Data API (required for `fetch`)
BLIZZARD_CLIENT_ID=your_client_id
BLIZZARD_CLIENT_SECRET=your_client_secret
BLIZZARD_REGION=us            # us | eu | kr | tw | cn

# OpenAI (required for `ask` / `advise`)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=              # optional (proxy / compatible endpoint)
OPENAI_DEFAULT_MODEL=gpt-4.1-nano

# Per-agent model overrides (optional; fall back to OPENAI_DEFAULT_MODEL)
WOW_AH_ORCHESTRATOR_MODEL=
WOW_AH_RECIPE_MODEL=
WOW_AH_TREND_MODEL=
WOW_AH_RISK_MODEL=
```

- `fetch` needs the Blizzard credentials. All other commands only read the local SQLite DB at `data/wow_ah.db` (override with `DB_PATH`).
- Each agent's model is resolved independently — set a specific `WOW_AH_*_MODEL` to override, otherwise `OPENAI_DEFAULT_MODEL` is used. The default `gpt-4.1-nano` is the cheapest; if your OpenAI project lacks access, set `OPENAI_DEFAULT_MODEL=gpt-4o-mini`.

---

## Usage

```bash
# Data
wow-ah fetch                        # fetch commodity prices (throttled to once/hour)
wow-ah prices                       # latest prices for tracked items
wow-ah export                       # dump price history to data/exports/prices.csv

# Analysis
wow-ah spreads                      # recipe profit margins (sorted; default hides losses)
wow-ah spreads --min-margin=-100    # include loss-making recipes
wow-ah trends                       # BUY / SELL / HOLD signals (needs ≥24h of history)
wow-ah recipes list                 # list loaded recipes

# AI multi-agent advisor (needs OPENAI_API_KEY)
wow-ah ask "現在哪個煉金配方最賺？"      # natural-language Q&A
wow-ah advise                       # proactive trading recommendation report
wow-ah mcp                          # start an MCP server exposing the analysis tools
```

The **watchlist is derived from recipes** — adding a recipe is how you start tracking new items. Recipe definitions live as JSON in `src/wow_ah/recipes/data/` (`alchemy.json`, `cooking.json`); add a new profession by dropping in a new `*.json` file.

---

## The multi-agent advisor

`ask` and `advise` run an **orchestrator** that treats each specialist as a callable tool:

```
question
  → [data-freshness gate]   (deterministic, no LLM — blocks if data > 6h old)
  → orchestrator            → recipe analyst   (get_spreads / list_recipes)
                            → trend analyst    (get_trends / get_prices)
                            → risk reviewer    (sanity-checks the conclusions)
  → orchestrator synthesizes a Traditional-Chinese report
```

- **Read-only:** tools never call the Blizzard API and never place trades; `fetch` stays manual.
- **Per-agent models:** mix cheap and capable models per role via the `WOW_AH_*_MODEL` env vars.
- The LLM does **not** compute prices — the deterministic services do. The agents select, rank, justify, and summarize.

### MCP server

`wow-ah mcp` exposes `get_spreads`, `get_trends`, `get_prices`, and `list_recipes` over the Model Context Protocol (FastMCP), so any MCP client (Claude Desktop, Claude Code, etc.) can call the same read-only tools.

---

## Experimenting with synthetic data

Real data is sparse until you accumulate ≥24h of hourly fetches, and crafted output items often have no commodity price. To exercise the agents end-to-end immediately, seed a **separate** synthetic database:

```bash
python scripts/seed_sim_db.py                                   # writes data/wow_ah_sim.db
DB_PATH=data/wow_ah_sim.db OPENAI_DEFAULT_MODEL=gpt-4o-mini wow-ah advise
```

The seed script generates 7 days of hourly history with a mix of profitable/loss recipes and BUY/SELL/HOLD signals (deterministic). Tune the `FACTORS` / `END_MULT` constants to change the scenario. See [`docs/agent-experiment-guide.md`](docs/agent-experiment-guide.md) for what each agent can analyze and ready-made experiment commands.

> The sample DB's timestamps are fixed at seed time — after ~6h the freshness gate treats it as stale; re-run the seed script to refresh.

---

## Development

```bash
uv run pytest                       # full suite
uv run pytest --cov=wow_ah          # with coverage
# conda: conda run -n wow-ah python -m pytest -q
```

- Services are tested with `FakeStore` / `FakeMarketData` / `FakeLLM` that satisfy the protocols structurally — no `unittest.mock`, no network.
- Error handling is centralized: raise an `AppException` subclass (`APIError` / `DataError`) with a message from a constant in `src/wow_ah/exceptions/messages.py`.

Design docs and implementation plans live under [`docs/superpowers/`](docs/superpowers/).

---

## Domain conventions

- **Money is integer copper** end-to-end; conversion to `Ng Xs Yc` happens only at display time.
- **AH fee** is a flat 5%, computed with integer math.
- **`fetch` is throttled** to once per UTC hour.
- **Trend analysis needs ≥24 data points**; the freshness gate rejects data older than 6h before running the advisor.
