# WoW AH Arbitrage Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that fetches WoW Auction House prices via Blizzard API, analyzes alchemy recipe profit margins, and detects temporal price anomalies for arbitrage opportunities.

**Architecture:** Clean Architecture with dependency inversion. Services depend on Protocols (abstractions), Adapters implement those Protocols. CLI is a thin layer routing to Services. SQLite stores price snapshots; cron drives hourly fetches.

**Tech Stack:** Python 3.14, uv, httpx, typer, pydantic-settings, tabulate, sqlite3 (stdlib), pytest

**Spec:** `docs/superpowers/specs/2026-04-10-wow-ah-arbitrage-bot-design.md`

---

## File Structure

```
wow/
  pyproject.toml                          # uv project, CLI entry point, dependencies
  .env.example                            # Template for API credentials
  .gitignore                              # Ignore data/, .env, __pycache__
  src/wow_ah/
    __init__.py                           # Package marker
    cli.py                                # Typer app, all CLI commands
    core/
      __init__.py
      config.py                           # Settings via pydantic-settings (.env)
      auth.py                             # OAuth2 token fetch + cache
    schemas/
      __init__.py
      prices.py                           # CommodityListing, PriceSnapshot, SpreadResult, ItemInfo, TrendResult
      recipes.py                          # Reagent, Recipe
    exceptions/
      __init__.py
      base.py                             # AppException
      messages.py                         # Error message constants
    protocols/
      __init__.py
      market_data.py                      # MarketDataProtocol
      price_store.py                      # PriceStoreProtocol
    adapters/
      __init__.py
      blizzard_adapter.py                 # Implements MarketDataProtocol
      sqlite_adapter.py                   # Implements PriceStoreProtocol
    services/
      __init__.py
      fetch_service.py                    # Orchestrates API -> filter -> store
      spread_service.py                   # Recipe profit analysis
      temporal_service.py                 # Moving averages, signals
    recipes/
      __init__.py
      loader.py                           # Load + validate alchemy.json
      data/
        alchemy.json                      # Manual recipe definitions
    export/
      __init__.py
      csv_export.py                       # CSV export
      formatters.py                       # CLI table formatting
  tests/
    __init__.py
    conftest.py                           # Shared fixtures
    test_schemas.py                       # Schema construction tests
    test_recipe_loader.py                 # JSON loading tests
    test_sqlite_adapter.py                # DB CRUD tests
    test_blizzard_adapter.py              # API response parsing tests
    test_fetch_service.py                 # Fetch orchestration tests
    test_spread_service.py                # Profit calculation tests
    test_temporal_service.py              # MA / signal tests
    test_csv_export.py                    # CSV output tests
    fixtures/
      sample_commodities.json             # Blizzard API response fixture
  data/                                   # Runtime data (gitignored)
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/wow_ah/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/jimmytsai/Documents/code/wow
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "wow-ah"
version = "0.1.0"
description = "WoW Auction House arbitrage analysis tool"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28",
    "typer>=0.15",
    "pydantic-settings>=2.7",
    "tabulate>=0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
]

[project.scripts]
wow-ah = "wow_ah.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wow_ah"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 3: Create .gitignore**

```
data/
.env
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.pytest_cache/
```

- [ ] **Step 4: Create .env.example**

```
BLIZZARD_CLIENT_ID=your_client_id_here
BLIZZARD_CLIENT_SECRET=your_client_secret_here
BLIZZARD_REGION=us
```

- [ ] **Step 5: Create directory structure**

```bash
mkdir -p src/wow_ah/{core,schemas,exceptions,protocols,adapters,services,recipes/data,export}
mkdir -p tests/fixtures
mkdir -p data/exports
touch src/wow_ah/__init__.py
touch src/wow_ah/core/__init__.py
touch src/wow_ah/schemas/__init__.py
touch src/wow_ah/exceptions/__init__.py
touch src/wow_ah/protocols/__init__.py
touch src/wow_ah/adapters/__init__.py
touch src/wow_ah/services/__init__.py
touch src/wow_ah/recipes/__init__.py
touch src/wow_ah/export/__init__.py
touch tests/__init__.py
```

- [ ] **Step 6: Install project with uv**

```bash
uv sync --dev
```
Expected: Dependencies installed, virtual environment created.

- [ ] **Step 7: Verify pytest runs**

```bash
uv run pytest --version
```
Expected: pytest version printed, no errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/__init__.py
git commit -m "chore: scaffold project structure with uv and dependencies"
```

---

### Task 2: Schemas

**Files:**
- Create: `src/wow_ah/schemas/prices.py`
- Create: `src/wow_ah/schemas/recipes.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_schemas.py`:

```python
from wow_ah.schemas.prices import CommodityListing, PriceSnapshot, SpreadResult, ItemInfo
from wow_ah.schemas.recipes import Reagent, Recipe


def test_commodity_listing():
    listing = CommodityListing(item_id=210796, unit_price=15000, quantity=200)
    assert listing.item_id == 210796
    assert listing.unit_price == 15000
    assert listing.quantity == 200


def test_price_snapshot_full():
    snap = PriceSnapshot(
        item_id=210796,
        timestamp="2026-04-10T14:00:00Z",
        min_price=14500,
        median_price=15200,
        mean_price=15800,
        total_quantity=5000,
        num_auctions=42,
    )
    assert snap.min_price == 14500
    assert snap.median_price == 15200


def test_price_snapshot_minimal():
    snap = PriceSnapshot(
        item_id=210796,
        timestamp="2026-04-10T14:00:00Z",
        min_price=14500,
    )
    assert snap.median_price is None
    assert snap.mean_price is None
    assert snap.total_quantity is None
    assert snap.num_auctions is None


def test_item_info():
    item = ItemInfo(item_id=210796, name="Mycobloom", quality="Common", item_class="Tradeskill", item_subclass="Herb")
    assert item.name == "Mycobloom"


def test_item_info_minimal():
    item = ItemInfo(item_id=210796, name="Mycobloom")
    assert item.quality is None


def test_spread_result():
    spread = SpreadResult(
        recipe_name="Flask of Alchemical Chaos",
        output_item_id=212283,
        material_cost=150000,
        product_price=200000,
        profit=40000,
        margin_pct=26.67,
    )
    assert spread.profit == 40000
    assert spread.margin_pct == 26.67


def test_reagent():
    reagent = Reagent(item_id=210796, name="Mycobloom", quantity=10)
    assert reagent.quantity == 10


def test_recipe():
    recipe = Recipe(
        name="Flask of Alchemical Chaos",
        output_item_id=212283,
        output_quantity=1,
        reagents=[
            Reagent(item_id=210796, name="Mycobloom", quantity=10),
            Reagent(item_id=210799, name="Luredrop", quantity=5),
        ],
    )
    assert len(recipe.reagents) == 2
    assert recipe.output_quantity == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_schemas.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement schemas/prices.py**

Create `src/wow_ah/schemas/prices.py`:

```python
from dataclasses import dataclass


@dataclass
class CommodityListing:
    """Single auction listing from Blizzard API."""
    item_id: int
    unit_price: int  # copper
    quantity: int


@dataclass
class PriceSnapshot:
    """Aggregated price snapshot per item per fetch."""
    item_id: int
    timestamp: str  # ISO 8601
    min_price: int  # copper
    median_price: int | None = None
    mean_price: int | None = None
    total_quantity: int | None = None
    num_auctions: int | None = None


@dataclass
class ItemInfo:
    """Item metadata cached from Blizzard Item API."""
    item_id: int
    name: str
    quality: str | None = None
    item_class: str | None = None
    item_subclass: str | None = None


@dataclass
class SpreadResult:
    """Profit analysis result for a single recipe."""
    recipe_name: str
    output_item_id: int
    material_cost: int  # copper
    product_price: int  # copper
    profit: int  # copper (after 5% AH fee)
    margin_pct: float  # percentage


@dataclass
class TrendResult:
    """Temporal analysis result for a single item."""
    item_id: int
    current_price: int
    ma_24h: float
    ma_72h: float
    ma_7d: float
    std_7d: float
    percentile_7d: float  # current price percentile in 7-day history
    signal: str  # "BUY", "SELL", or "HOLD"
```

- [ ] **Step 4: Implement schemas/recipes.py**

Create `src/wow_ah/schemas/recipes.py`:

```python
from dataclasses import dataclass, field


@dataclass
class Reagent:
    item_id: int
    name: str
    quantity: int


@dataclass
class Recipe:
    name: str
    output_item_id: int
    output_quantity: int
    reagents: list[Reagent] = field(default_factory=list)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_schemas.py -v
```
Expected: All 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/schemas/ tests/test_schemas.py
git commit -m "feat: add data model schemas (prices, recipes)"
```

---

### Task 3: Exceptions

**Files:**
- Create: `src/wow_ah/exceptions/base.py`
- Create: `src/wow_ah/exceptions/messages.py`

- [ ] **Step 1: Create exceptions/base.py**

```python
class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class APIError(AppException):
    """Blizzard API related errors."""


class DataError(AppException):
    """Data access / insufficient data errors."""
```

- [ ] **Step 2: Create exceptions/messages.py**

```python
class APIErrorMessages:
    AUTH_FAILED = "Blizzard OAuth2 authentication failed: {error}"
    FETCH_FAILED = "Commodity data fetch failed: HTTP {status_code}"
    RATE_LIMITED = "API rate limited, please try again later"


class DataErrorMessages:
    NO_SNAPSHOTS = "No price snapshots found for {item_name}. Run 'wow-ah fetch' first."
    INSUFFICIENT_HISTORY = (
        "{item_name} has only {actual}h of history, need at least {required}h"
    )
    RECIPE_NOT_FOUND = "Recipe not found: {recipe_name}"
    RECIPE_FILE_INVALID = "Recipe file is invalid: {error}"
```

- [ ] **Step 3: Commit**

```bash
git add src/wow_ah/exceptions/
git commit -m "feat: add exception classes and error message constants"
```

---

### Task 4: Protocols

**Files:**
- Create: `src/wow_ah/protocols/market_data.py`
- Create: `src/wow_ah/protocols/price_store.py`

- [ ] **Step 1: Create protocols/market_data.py**

```python
from typing import Protocol

from wow_ah.schemas.prices import CommodityListing, ItemInfo


class MarketDataProtocol(Protocol):
    """Abstract interface for market data sources."""

    def fetch_commodities(self) -> list[CommodityListing]:
        """Fetch all commodity auctions from the market."""
        ...

    def get_item(self, item_id: int) -> ItemInfo:
        """Get item metadata by ID."""
        ...
```

- [ ] **Step 2: Create protocols/price_store.py**

```python
from typing import Protocol

from wow_ah.schemas.prices import PriceSnapshot


class PriceStoreProtocol(Protocol):
    """Abstract interface for price data storage."""

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        """Persist a batch of price snapshots."""
        ...

    def get_price_history(
        self, item_id: int, start: str, end: str
    ) -> list[PriceSnapshot]:
        """Get price history for an item within a time range (ISO 8601)."""
        ...

    def get_latest_prices(self, item_ids: list[int]) -> dict[int, PriceSnapshot]:
        """Get the most recent snapshot for each item ID."""
        ...

    def get_last_fetch_timestamp(self) -> str | None:
        """Get timestamp of the most recent fetch, or None if no data."""
        ...
```

- [ ] **Step 3: Commit**

```bash
git add src/wow_ah/protocols/
git commit -m "feat: add MarketDataProtocol and PriceStoreProtocol"
```

---

### Task 5: Core Config

**Files:**
- Create: `src/wow_ah/core/config.py`

- [ ] **Step 1: Create core/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    blizzard_client_id: str = ""
    blizzard_client_secret: str = ""
    blizzard_region: str = "us"
    db_path: str = "data/wow_ah.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Commit**

```bash
git add src/wow_ah/core/config.py
git commit -m "feat: add pydantic-settings config with .env support"
```

---

### Task 6: SQLite Adapter

**Files:**
- Create: `src/wow_ah/adapters/sqlite_adapter.py`
- Test: `tests/test_sqlite_adapter.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import sqlite3
import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database path."""
    return str(tmp_path / "test.db")
```

Create `tests/test_sqlite_adapter.py`:

```python
from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.schemas.prices import PriceSnapshot


def test_init_creates_tables(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    import sqlite3
    conn = sqlite3.connect(tmp_db)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "price_snapshots" in tables
    assert "items" in tables
    assert "recipes" in tables
    assert "recipe_reagents" in tables


def test_save_and_get_latest(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    snapshots = [
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1000, median_price=1200, mean_price=1300, total_quantity=500, num_auctions=10),
        PriceSnapshot(item_id=200, timestamp="2026-04-10T14:00:00Z", min_price=2000, median_price=2500, mean_price=2600, total_quantity=300, num_auctions=5),
    ]
    adapter.save_snapshots(snapshots)

    latest = adapter.get_latest_prices([100, 200])
    assert 100 in latest
    assert 200 in latest
    assert latest[100].min_price == 1000
    assert latest[200].min_price == 2000


def test_get_price_history(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T10:00:00Z", min_price=900),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T11:00:00Z", min_price=1000),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T12:00:00Z", min_price=1100),
    ])

    history = adapter.get_price_history(100, "2026-04-10T10:00:00Z", "2026-04-10T12:00:00Z")
    assert len(history) == 3
    assert history[0].min_price == 900
    assert history[2].min_price == 1100


def test_get_price_history_filters_by_range(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T10:00:00Z", min_price=900),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T11:00:00Z", min_price=1000),
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1100),
    ])

    history = adapter.get_price_history(100, "2026-04-10T10:00:00Z", "2026-04-10T12:00:00Z")
    assert len(history) == 2


def test_get_last_fetch_timestamp_empty(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    assert adapter.get_last_fetch_timestamp() is None


def test_get_last_fetch_timestamp(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    adapter.save_snapshots([
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1000),
    ])
    assert adapter.get_last_fetch_timestamp() == "2026-04-10T14:00:00Z"


def test_get_latest_prices_missing_item(tmp_db):
    adapter = SQLiteAdapter(tmp_db)
    latest = adapter.get_latest_prices([999])
    assert 999 not in latest
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_sqlite_adapter.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement sqlite_adapter.py**

Create `src/wow_ah/adapters/sqlite_adapter.py`:

```python
import sqlite3

from wow_ah.schemas.prices import PriceSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    min_price INTEGER NOT NULL,
    median_price INTEGER,
    mean_price INTEGER,
    total_quantity INTEGER,
    num_auctions INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snapshots_item_ts ON price_snapshots(item_id, timestamp);

CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    quality TEXT,
    item_class TEXT,
    item_subclass TEXT,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS recipes (
    recipe_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    profession TEXT NOT NULL DEFAULT 'Alchemy',
    output_item_id INTEGER NOT NULL,
    output_quantity INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recipe_reagents (
    recipe_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, item_id)
);
"""


class SQLiteAdapter:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.close()

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        conn = self._connect()
        conn.executemany(
            """INSERT INTO price_snapshots
               (item_id, timestamp, min_price, median_price, mean_price, total_quantity, num_auctions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (s.item_id, s.timestamp, s.min_price, s.median_price, s.mean_price, s.total_quantity, s.num_auctions)
                for s in snapshots
            ],
        )
        conn.commit()
        conn.close()

    def get_price_history(
        self, item_id: int, start: str, end: str
    ) -> list[PriceSnapshot]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT item_id, timestamp, min_price, median_price, mean_price, total_quantity, num_auctions
               FROM price_snapshots
               WHERE item_id = ? AND timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp""",
            (item_id, start, end),
        ).fetchall()
        conn.close()
        return [
            PriceSnapshot(
                item_id=r["item_id"],
                timestamp=r["timestamp"],
                min_price=r["min_price"],
                median_price=r["median_price"],
                mean_price=r["mean_price"],
                total_quantity=r["total_quantity"],
                num_auctions=r["num_auctions"],
            )
            for r in rows
        ]

    def get_latest_prices(self, item_ids: list[int]) -> dict[int, PriceSnapshot]:
        if not item_ids:
            return {}
        conn = self._connect()
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"""SELECT p.item_id, p.timestamp, p.min_price, p.median_price,
                       p.mean_price, p.total_quantity, p.num_auctions
                FROM price_snapshots p
                INNER JOIN (
                    SELECT item_id, MAX(timestamp) as max_ts
                    FROM price_snapshots
                    WHERE item_id IN ({placeholders})
                    GROUP BY item_id
                ) latest ON p.item_id = latest.item_id AND p.timestamp = latest.max_ts""",
            item_ids,
        ).fetchall()
        conn.close()
        return {
            r["item_id"]: PriceSnapshot(
                item_id=r["item_id"],
                timestamp=r["timestamp"],
                min_price=r["min_price"],
                median_price=r["median_price"],
                mean_price=r["mean_price"],
                total_quantity=r["total_quantity"],
                num_auctions=r["num_auctions"],
            )
            for r in rows
        }

    def get_last_fetch_timestamp(self) -> str | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT MAX(timestamp) as ts FROM price_snapshots"
        ).fetchone()
        conn.close()
        return row["ts"] if row and row["ts"] else None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_sqlite_adapter.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/adapters/sqlite_adapter.py tests/conftest.py tests/test_sqlite_adapter.py
git commit -m "feat: add SQLite adapter implementing PriceStoreProtocol"
```

---

### Task 7: OAuth2 Auth

**Files:**
- Create: `src/wow_ah/core/auth.py`

- [ ] **Step 1: Implement core/auth.py**

```python
import time

import httpx

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import APIErrorMessages

_TOKEN_URL = "https://oauth.battle.net/token"


class TokenManager:
    """Manages OAuth2 client credentials tokens with caching."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        self._refresh()
        return self._token  # type: ignore[return-value]

    def _refresh(self) -> None:
        try:
            resp = httpx.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise APIError(APIErrorMessages.AUTH_FAILED.format(error=str(e))) from e

        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 86400)
```

- [ ] **Step 2: Commit**

```bash
git add src/wow_ah/core/auth.py
git commit -m "feat: add OAuth2 token manager with caching"
```

---

### Task 8: Blizzard Adapter

**Files:**
- Create: `src/wow_ah/adapters/blizzard_adapter.py`
- Create: `tests/fixtures/sample_commodities.json`
- Test: `tests/test_blizzard_adapter.py`

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/sample_commodities.json`:

```json
{
  "auctions": [
    {"id": 1, "item": {"id": 210796}, "unit_price": 15000, "quantity": 200},
    {"id": 2, "item": {"id": 210796}, "unit_price": 14500, "quantity": 100},
    {"id": 3, "item": {"id": 210796}, "unit_price": 16000, "quantity": 50},
    {"id": 4, "item": {"id": 210799}, "unit_price": 25000, "quantity": 80},
    {"id": 5, "item": {"id": 210799}, "unit_price": 24000, "quantity": 120},
    {"id": 6, "item": {"id": 999999}, "unit_price": 500, "quantity": 10000}
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_blizzard_adapter.py`:

```python
import json
from pathlib import Path

from wow_ah.adapters.blizzard_adapter import parse_commodities


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_commodities.json"


def test_parse_commodities():
    raw = json.loads(FIXTURE_PATH.read_text())
    listings = parse_commodities(raw)
    assert len(listings) == 6
    assert listings[0].item_id == 210796
    assert listings[0].unit_price == 15000
    assert listings[0].quantity == 200


def test_parse_commodities_empty():
    listings = parse_commodities({"auctions": []})
    assert listings == []


def test_parse_commodities_filter_by_watchlist():
    raw = json.loads(FIXTURE_PATH.read_text())
    listings = parse_commodities(raw, watchlist={210796})
    assert len(listings) == 3
    assert all(l.item_id == 210796 for l in listings)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_blizzard_adapter.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 4: Implement blizzard_adapter.py**

Create `src/wow_ah/adapters/blizzard_adapter.py`:

```python
import httpx

from wow_ah.core.auth import TokenManager
from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import APIErrorMessages
from wow_ah.schemas.prices import CommodityListing, ItemInfo


def parse_commodities(
    raw: dict, watchlist: set[int] | None = None
) -> list[CommodityListing]:
    """Parse raw Blizzard API response into CommodityListing objects."""
    listings = []
    for auction in raw.get("auctions", []):
        item_id = auction["item"]["id"]
        if watchlist and item_id not in watchlist:
            continue
        listings.append(
            CommodityListing(
                item_id=item_id,
                unit_price=auction["unit_price"],
                quantity=auction["quantity"],
            )
        )
    return listings


class BlizzardAdapter:
    """Fetches market data from Blizzard Game Data API."""

    def __init__(self, token_manager: TokenManager, region: str = "us") -> None:
        self._token_manager = token_manager
        self._region = region
        self._base_url = f"https://{region}.api.blizzard.com"

    def fetch_commodities(self) -> list[CommodityListing]:
        token = self._token_manager.get_token()
        try:
            resp = httpx.get(
                f"{self._base_url}/data/wow/auctions/commodities",
                params={
                    "namespace": f"dynamic-{self._region}",
                    "locale": "en_US",
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code=e.response.status_code)
            ) from e
        except httpx.HTTPError as e:
            raise APIError(
                APIErrorMessages.FETCH_FAILED.format(status_code="connection_error")
            ) from e

        self._last_modified = resp.headers.get("Last-Modified")
        return parse_commodities(resp.json())

    def get_item(self, item_id: int) -> ItemInfo:
        token = self._token_manager.get_token()
        resp = httpx.get(
            f"{self._base_url}/data/wow/item/{item_id}",
            params={
                "namespace": f"static-{self._region}",
                "locale": "en_US",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return ItemInfo(
            item_id=data["id"],
            name=data["name"],
            quality=data.get("quality", {}).get("name"),
            item_class=data.get("item_class", {}).get("name"),
            item_subclass=data.get("item_subclass", {}).get("name"),
        )

    @property
    def last_modified(self) -> str | None:
        return getattr(self, "_last_modified", None)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_blizzard_adapter.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/adapters/blizzard_adapter.py tests/test_blizzard_adapter.py tests/fixtures/
git commit -m "feat: add Blizzard API adapter with commodity parsing"
```

---

### Task 9: Recipe Loader

**Files:**
- Create: `src/wow_ah/recipes/loader.py`
- Create: `src/wow_ah/recipes/data/alchemy.json`
- Test: `tests/test_recipe_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_recipe_loader.py`:

```python
import json

import pytest

from wow_ah.recipes.loader import load_recipes, get_watchlist_item_ids
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_recipe_loader.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement recipes/loader.py**

Create `src/wow_ah/recipes/loader.py`:

```python
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
```

- [ ] **Step 4: Create alchemy.json with initial recipes**

Create `src/wow_ah/recipes/data/alchemy.json`:

```json
{
  "recipes": [
    {
      "name": "Flask of Alchemical Chaos",
      "output_item_id": 212283,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 210796, "name": "Mycobloom", "quantity": 10},
        {"item_id": 210799, "name": "Luredrop", "quantity": 5},
        {"item_id": 210802, "name": "Aqirite", "quantity": 2}
      ]
    },
    {
      "name": "Algari Healing Potion",
      "output_item_id": 211954,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 210796, "name": "Mycobloom", "quantity": 5},
        {"item_id": 210930, "name": "Blessing Blossom", "quantity": 3}
      ]
    },
    {
      "name": "Algari Mana Potion",
      "output_item_id": 211955,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 210799, "name": "Luredrop", "quantity": 5},
        {"item_id": 210930, "name": "Blessing Blossom", "quantity": 3}
      ]
    },
    {
      "name": "Phial of Concentrated Ingenuity",
      "output_item_id": 212284,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 210796, "name": "Mycobloom", "quantity": 8},
        {"item_id": 210800, "name": "Arathor's Spear", "quantity": 6},
        {"item_id": 210802, "name": "Aqirite", "quantity": 1}
      ]
    },
    {
      "name": "Cauldron of the Potion Master",
      "output_item_id": 212285,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 210796, "name": "Mycobloom", "quantity": 20},
        {"item_id": 210799, "name": "Luredrop", "quantity": 15},
        {"item_id": 210800, "name": "Arathor's Spear", "quantity": 15},
        {"item_id": 210930, "name": "Blessing Blossom", "quantity": 10},
        {"item_id": 210802, "name": "Aqirite", "quantity": 5}
      ]
    }
  ]
}
```

Note: Item IDs are illustrative. The implementer should verify actual TWW item IDs from Wowhead or in-game before first real use. The tool will work correctly regardless — wrong IDs simply won't match any AH listings.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_recipe_loader.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/recipes/ tests/test_recipe_loader.py
git commit -m "feat: add recipe loader with initial alchemy recipes"
```

---

### Task 10: Fetch Service

**Files:**
- Create: `src/wow_ah/services/fetch_service.py`
- Test: `tests/test_fetch_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetch_service.py`:

```python
from wow_ah.schemas.prices import CommodityListing, PriceSnapshot
from wow_ah.services.fetch_service import FetchService, aggregate_listings


class FakeMarketData:
    def __init__(self, listings: list[CommodityListing]):
        self._listings = listings

    def fetch_commodities(self) -> list[CommodityListing]:
        return self._listings

    def get_item(self, item_id: int):
        return None


class FakeStore:
    def __init__(self):
        self.saved: list[PriceSnapshot] = []
        self._last_ts: str | None = None

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        self.saved.extend(snapshots)

    def get_price_history(self, item_id, start, end):
        return []

    def get_latest_prices(self, item_ids):
        return {}

    def get_last_fetch_timestamp(self) -> str | None:
        return self._last_ts


def test_aggregate_listings_single_item():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=100, unit_price=2000, quantity=5),
        CommodityListing(item_id=100, unit_price=1500, quantity=3),
    ]
    result = aggregate_listings(listings, "2026-04-10T14:00:00Z")
    assert len(result) == 1
    snap = result[0]
    assert snap.item_id == 100
    assert snap.min_price == 1000
    assert snap.total_quantity == 18
    assert snap.num_auctions == 3
    # weighted mean = (1000*10 + 2000*5 + 1500*3) / 18 = 24500/18 = 1361
    assert snap.mean_price == 1361


def test_aggregate_listings_multiple_items():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=200, unit_price=5000, quantity=20),
    ]
    result = aggregate_listings(listings, "2026-04-10T14:00:00Z")
    assert len(result) == 2
    ids = {s.item_id for s in result}
    assert ids == {100, 200}


def test_fetch_service_filters_watchlist():
    listings = [
        CommodityListing(item_id=100, unit_price=1000, quantity=10),
        CommodityListing(item_id=200, unit_price=2000, quantity=5),
        CommodityListing(item_id=999, unit_price=500, quantity=100),
    ]
    market = FakeMarketData(listings)
    store = FakeStore()
    service = FetchService(market_data=market, price_store=store, watchlist={100, 200})

    service.fetch()

    saved_ids = {s.item_id for s in store.saved}
    assert saved_ids == {100, 200}
    assert 999 not in saved_ids
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_fetch_service.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement fetch_service.py**

Create `src/wow_ah/services/fetch_service.py`:

```python
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from wow_ah.protocols.market_data import MarketDataProtocol
from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import CommodityListing, PriceSnapshot


def aggregate_listings(
    listings: list[CommodityListing], timestamp: str
) -> list[PriceSnapshot]:
    """Aggregate raw auction listings into one PriceSnapshot per item."""
    by_item: dict[int, list[CommodityListing]] = defaultdict(list)
    for listing in listings:
        by_item[listing.item_id].append(listing)

    snapshots = []
    for item_id, item_listings in by_item.items():
        total_qty = sum(l.quantity for l in item_listings)
        min_price = min(l.unit_price for l in item_listings)
        mean_price = sum(l.unit_price * l.quantity for l in item_listings) // total_qty

        # Weighted median: expand to per-unit prices, take median
        expanded = []
        for l in item_listings:
            expanded.extend([l.unit_price] * l.quantity)
        median_price = int(statistics.median(expanded))

        snapshots.append(
            PriceSnapshot(
                item_id=item_id,
                timestamp=timestamp,
                min_price=min_price,
                median_price=median_price,
                mean_price=mean_price,
                total_quantity=total_qty,
                num_auctions=len(item_listings),
            )
        )
    return snapshots


class FetchService:
    """Orchestrates fetching market data, filtering, and storing."""

    def __init__(
        self,
        market_data: MarketDataProtocol,
        price_store: PriceStoreProtocol,
        watchlist: set[int],
    ) -> None:
        self._market_data = market_data
        self._price_store = price_store
        self._watchlist = watchlist

    def fetch(self) -> int:
        """Fetch, filter, aggregate, and store. Returns number of snapshots saved."""
        all_listings = self._market_data.fetch_commodities()
        filtered = [l for l in all_listings if l.item_id in self._watchlist]

        if not filtered:
            return 0

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshots = aggregate_listings(filtered, timestamp)
        self._price_store.save_snapshots(snapshots)
        return len(snapshots)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_fetch_service.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/services/fetch_service.py tests/test_fetch_service.py
git commit -m "feat: add fetch service with listing aggregation"
```

---

### Task 11: Spread Service

**Files:**
- Create: `src/wow_ah/services/spread_service.py`
- Test: `tests/test_spread_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_spread_service.py`:

```python
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent
from wow_ah.services.spread_service import SpreadService

AH_FEE_RATE = 0.05


class FakeStore:
    def __init__(self, prices: dict[int, PriceSnapshot]):
        self._prices = prices

    def save_snapshots(self, snapshots):
        pass

    def get_price_history(self, item_id, start, end):
        return []

    def get_latest_prices(self, item_ids):
        return {iid: self._prices[iid] for iid in item_ids if iid in self._prices}

    def get_last_fetch_timestamp(self):
        return None


def _snap(item_id: int, min_price: int) -> PriceSnapshot:
    return PriceSnapshot(item_id=item_id, timestamp="2026-04-10T14:00:00Z", min_price=min_price)


def test_spread_profitable():
    store = FakeStore({
        1: _snap(1, 100),   # reagent A: 100 copper
        2: _snap(2, 200),   # reagent B: 200 copper
        100: _snap(100, 5000),  # product: 5000 copper
    })
    recipes = [
        Recipe(
            name="Test Flask",
            output_item_id=100,
            output_quantity=1,
            reagents=[
                Reagent(item_id=1, name="Herb A", quantity=10),
                Reagent(item_id=2, name="Herb B", quantity=5),
            ],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)

    assert len(results) == 1
    r = results[0]
    assert r.recipe_name == "Test Flask"
    assert r.material_cost == 10 * 100 + 5 * 200  # 2000
    assert r.product_price == 5000
    expected_profit = 5000 - int(5000 * AH_FEE_RATE) - 2000  # 5000 - 250 - 2000 = 2750
    assert r.profit == expected_profit
    assert r.margin_pct == expected_profit / 2000 * 100


def test_spread_loss():
    store = FakeStore({
        1: _snap(1, 1000),
        100: _snap(100, 500),
    })
    recipes = [
        Recipe(
            name="Bad Flask",
            output_item_id=100,
            output_quantity=1,
            reagents=[Reagent(item_id=1, name="Herb A", quantity=10)],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)

    assert len(results) == 1
    assert results[0].profit < 0


def test_spread_missing_price_skips_recipe():
    store = FakeStore({
        1: _snap(1, 100),
        # item 2 is missing from AH
    })
    recipes = [
        Recipe(
            name="Missing Reagent",
            output_item_id=100,
            output_quantity=1,
            reagents=[
                Reagent(item_id=1, name="Herb A", quantity=10),
                Reagent(item_id=2, name="Herb B", quantity=5),
            ],
        )
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)
    assert len(results) == 0


def test_spread_sorted_by_margin():
    store = FakeStore({
        1: _snap(1, 100),
        2: _snap(2, 100),
        100: _snap(100, 5000),
        200: _snap(200, 2000),
    })
    recipes = [
        Recipe(name="Low Margin", output_item_id=200, output_quantity=1,
               reagents=[Reagent(item_id=1, name="H", quantity=10)]),
        Recipe(name="High Margin", output_item_id=100, output_quantity=1,
               reagents=[Reagent(item_id=2, name="H", quantity=10)]),
    ]
    service = SpreadService(price_store=store)
    results = service.analyze(recipes)
    assert results[0].recipe_name == "High Margin"
    assert results[1].recipe_name == "Low Margin"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_spread_service.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement spread_service.py**

Create `src/wow_ah/services/spread_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_spread_service.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/services/spread_service.py tests/test_spread_service.py
git commit -m "feat: add spread service for recipe profit analysis"
```

---

### Task 12: Temporal Service

**Files:**
- Create: `src/wow_ah/services/temporal_service.py`
- Test: `tests/test_temporal_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_temporal_service.py`:

```python
import statistics
from datetime import datetime, timedelta, timezone

from wow_ah.schemas.prices import PriceSnapshot, TrendResult
from wow_ah.services.temporal_service import TemporalService


def _snaps_from(item_id: int, prices: list[int], end_dt: datetime) -> list[PriceSnapshot]:
    """Generate hourly snapshots ending at end_dt, one per price value."""
    start_dt = end_dt - timedelta(hours=len(prices) - 1)
    return [
        PriceSnapshot(
            item_id=item_id,
            timestamp=(start_dt + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            min_price=p,
        )
        for i, p in enumerate(prices)
    ]


class FakeStore:
    def __init__(self, history: dict[int, list[PriceSnapshot]]):
        self._history = history

    def save_snapshots(self, snapshots):
        pass

    def get_price_history(self, item_id, start, end):
        return [s for s in self._history.get(item_id, []) if start <= s.timestamp <= end]

    def get_latest_prices(self, item_ids):
        result = {}
        for iid in item_ids:
            snaps = self._history.get(iid, [])
            if snaps:
                result[iid] = snaps[-1]
        return result

    def get_last_fetch_timestamp(self):
        return None


def test_trend_result_fields():
    """TrendResult has all required multi-MA fields."""
    r = TrendResult(item_id=1, current_price=100, ma_24h=95.0, ma_72h=90.0,
                    ma_7d=88.0, std_7d=5.0, percentile_7d=75.0, signal="HOLD")
    assert r.ma_24h == 95.0
    assert r.ma_7d == 88.0


def test_trend_buy_signal_low_price():
    # 168 hours of data (7 days), last price drops well below mean - 1.5*std
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [30]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert len(results) == 1
    assert results[0].signal == "BUY"


def test_trend_sell_signal_high_price():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [300]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert results[0].signal == "SELL"


def test_trend_no_signal():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = [100] * 167 + [100]
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert results[0].signal == "HOLD"


def test_trend_percentile():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    prices = list(range(1, 169))  # 1..168, increasing hourly over 7 days
    snaps = _snaps_from(100, prices, end)
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    # Current price is 168, the highest — percentile should be 100%
    assert results[0].percentile_7d == 100.0


def test_trend_insufficient_data():
    end = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    snaps = _snaps_from(100, [100, 101], end)  # only 2 data points
    store = FakeStore({100: snaps})
    service = TemporalService(price_store=store)

    results = service.analyze(item_ids=[100], now="2026-04-10T12:00:00Z")
    assert len(results) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_temporal_service.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement temporal_service.py**

Create `src/wow_ah/services/temporal_service.py`:

```python
import statistics
from datetime import datetime, timedelta, timezone

from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.prices import PriceSnapshot, TrendResult

MIN_DATA_POINTS = 24  # need at least 24h of data
STD_MULTIPLIER = 1.5
BUY_PERCENTILE = 10
SELL_PERCENTILE = 90


def _ma(prices: list[int], count: int) -> float:
    """Moving average of the last `count` values."""
    subset = prices[-count:] if len(prices) >= count else prices
    return statistics.mean(subset)


class TemporalService:
    """Analyzes price trends and generates buy/sell signals."""

    def __init__(self, price_store: PriceStoreProtocol) -> None:
        self._store = price_store

    def analyze(
        self,
        item_ids: list[int],
        now: str,
        history_hours: int = 168,  # 7 days default
    ) -> list[TrendResult]:
        """Analyze price trends for the given items."""
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        start_dt = now_dt - timedelta(hours=history_hours)
        start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        results = []
        for item_id in item_ids:
            history = self._store.get_price_history(item_id, start, now)
            if len(history) < MIN_DATA_POINTS:
                continue

            prices = [s.min_price for s in history]
            current = prices[-1]

            ma_24h = _ma(prices, 24)
            ma_72h = _ma(prices, 72)
            ma_7d = statistics.mean(prices)  # full window = 7 days
            std_7d = statistics.pstdev(prices)

            # Percentile: % of historical prices <= current price
            below = sum(1 for p in prices if p <= current)
            percentile_7d = below / len(prices) * 100

            signal = self._compute_signal(current, ma_7d, std_7d, percentile_7d)

            results.append(
                TrendResult(
                    item_id=item_id,
                    current_price=current,
                    ma_24h=ma_24h,
                    ma_72h=ma_72h,
                    ma_7d=ma_7d,
                    std_7d=std_7d,
                    percentile_7d=percentile_7d,
                    signal=signal,
                )
            )

        return results

    def _compute_signal(
        self, current: int, ma_7d: float, std_7d: float, percentile_7d: float
    ) -> str:
        if std_7d == 0:
            return "HOLD"
        if current < ma_7d - STD_MULTIPLIER * std_7d or percentile_7d < BUY_PERCENTILE:
            return "BUY"
        if current > ma_7d + STD_MULTIPLIER * std_7d or percentile_7d > SELL_PERCENTILE:
            return "SELL"
        return "HOLD"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_temporal_service.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/services/temporal_service.py tests/test_temporal_service.py
git commit -m "feat: add temporal service with MA, std dev, and buy/sell signals"
```

---

### Task 13: CSV Export & Formatters

**Files:**
- Create: `src/wow_ah/export/csv_export.py`
- Create: `src/wow_ah/export/formatters.py`
- Test: `tests/test_csv_export.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_csv_export.py`:

```python
import csv
from io import StringIO

from wow_ah.schemas.prices import PriceSnapshot, SpreadResult, TrendResult
from wow_ah.export.csv_export import snapshots_to_csv, spreads_to_csv
from wow_ah.export.formatters import format_copper, format_spreads_table, format_trends_table


def test_snapshots_to_csv():
    snapshots = [
        PriceSnapshot(item_id=100, timestamp="2026-04-10T14:00:00Z", min_price=1500, median_price=1600, mean_price=1700, total_quantity=500, num_auctions=10),
        PriceSnapshot(item_id=200, timestamp="2026-04-10T14:00:00Z", min_price=2500, median_price=2600, mean_price=2700, total_quantity=300, num_auctions=5),
    ]
    output = snapshots_to_csv(snapshots)
    reader = csv.DictReader(StringIO(output))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["item_id"] == "100"
    assert rows[0]["min_price"] == "1500"


def test_spreads_to_csv():
    spreads = [
        SpreadResult(recipe_name="Flask A", output_item_id=100, material_cost=2000, product_price=5000, profit=2750, margin_pct=137.5),
    ]
    output = spreads_to_csv(spreads)
    reader = csv.DictReader(StringIO(output))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["recipe_name"] == "Flask A"
    assert rows[0]["profit"] == "2750"


def test_format_copper():
    assert format_copper(12345678) == "1234g 56s 78c"
    assert format_copper(10000) == "1g 0s 0c"
    assert format_copper(99) == "0g 0s 99c"
    assert format_copper(0) == "0g 0s 0c"


def test_format_spreads_table():
    spreads = [
        SpreadResult(recipe_name="Flask A", output_item_id=100, material_cost=20000, product_price=50000, profit=27500, margin_pct=137.5),
    ]
    table = format_spreads_table(spreads)
    assert "Flask A" in table
    assert "137.5" in table


def test_format_trends_table():
    trends = [
        TrendResult(item_id=100, current_price=15000, ma_24h=14500.0, ma_72h=14200.0,
                    ma_7d=14000.0, std_7d=1200.0, percentile_7d=75.0, signal="HOLD"),
    ]
    item_names = {100: "Mycobloom"}
    table = format_trends_table(trends, item_names)
    assert "Mycobloom" in table
    assert "HOLD" in table
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_csv_export.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement csv_export.py**

Create `src/wow_ah/export/csv_export.py`:

```python
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
```

- [ ] **Step 4: Implement formatters.py**

Create `src/wow_ah/export/formatters.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_csv_export.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/export/ tests/test_csv_export.py
git commit -m "feat: add CSV export and CLI table formatters"
```

---

### Task 14: CLI

**Files:**
- Create: `src/wow_ah/cli.py`

This is the integration layer — it wires Services, Adapters, and Config together. We test this via manual end-to-end verification (Task 15) rather than unit tests, since it's a thin routing layer.

- [ ] **Step 1: Implement cli.py**

Create `src/wow_ah/cli.py`:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from wow_ah.adapters.blizzard_adapter import BlizzardAdapter
from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.core.auth import TokenManager
from wow_ah.core.config import get_settings
from wow_ah.export.csv_export import snapshots_to_csv, spreads_to_csv
from wow_ah.export.formatters import format_copper, format_spreads_table, format_trends_table
from wow_ah.recipes.loader import get_watchlist_item_ids, load_recipes
from wow_ah.schemas.recipes import Recipe
from wow_ah.services.fetch_service import FetchService
from wow_ah.services.spread_service import SpreadService
from wow_ah.services.temporal_service import TemporalService

app = typer.Typer(help="WoW Auction House arbitrage analysis tool")
recipes_app = typer.Typer(help="Manage recipe definitions")
app.add_typer(recipes_app, name="recipes")

_RECIPE_PATH = Path(__file__).parent / "recipes" / "data" / "alchemy.json"


def _get_store() -> SQLiteAdapter:
    settings = get_settings()
    return SQLiteAdapter(settings.db_path)


def _get_recipes() -> list[Recipe]:
    return load_recipes(str(_RECIPE_PATH))


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
def fetch():
    """Fetch commodity prices from Blizzard API and store to database."""
    store = _get_store()
    market = _get_market()
    recipes = _get_recipes()
    watchlist = get_watchlist_item_ids(recipes)

    # Check Last-Modified to avoid duplicate writes
    last_ts = store.get_last_fetch_timestamp()

    service = FetchService(market_data=market, price_store=store, watchlist=watchlist)
    count = service.fetch()

    if count == 0 and last_ts:
        typer.echo("No new data (API not yet refreshed). Skipped.")
    else:
        typer.echo(f"Saved {count} price snapshots.")


@app.command()
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
def recipes_list():
    """List loaded recipes."""
    recipes = _get_recipes()
    for recipe in recipes:
        reagent_str = ", ".join(f"{r.name} x{r.quantity}" for r in recipe.reagents)
        typer.echo(f"  {recipe.name} -> [{recipe.output_item_id}]")
        typer.echo(f"    Reagents: {reagent_str}")
```

- [ ] **Step 2: Verify CLI entry point works**

```bash
uv run wow-ah --help
```
Expected: Help text showing all commands (fetch, prices, spreads, trends, export, recipes).

- [ ] **Step 3: Verify subcommand help**

```bash
uv run wow-ah recipes list --help
```
Expected: Help text for recipes list command.

- [ ] **Step 4: Commit**

```bash
git add src/wow_ah/cli.py
git commit -m "feat: add Typer CLI with all commands"
```

---

### Task 15: End-to-End Verification & Run All Tests

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS (approximately 30+ tests across all files).

- [ ] **Step 2: Verify CLI smoke test (without API credentials)**

```bash
uv run wow-ah recipes list
```
Expected: Lists the 5 initial recipes from alchemy.json.

- [ ] **Step 3: Verify empty database behavior**

```bash
uv run wow-ah prices
```
Expected: No crash, just no output or a clean message.

```bash
uv run wow-ah spreads
```
Expected: "No recipes with sufficient margin found."

```bash
uv run wow-ah trends
```
Expected: "Insufficient data for trend analysis."

- [ ] **Step 4: Final commit with any fixes**

```bash
git add -A
git status
# Only commit if there are changes
git commit -m "chore: final adjustments from end-to-end verification"
```

---

## Summary

| Task | Component | Test Count | Estimated Effort |
|------|-----------|-----------|-----------------|
| 1 | Project scaffolding | 0 | Setup |
| 2 | Schemas | 8 | 5 min |
| 3 | Exceptions | 0 | 3 min |
| 4 | Protocols | 0 | 3 min |
| 5 | Core config | 0 | 2 min |
| 6 | SQLite adapter | 7 | 15 min |
| 7 | OAuth2 auth | 0 | 5 min |
| 8 | Blizzard adapter | 3 | 10 min |
| 9 | Recipe loader | 5 | 10 min |
| 10 | Fetch service | 3 | 10 min |
| 11 | Spread service | 4 | 10 min |
| 12 | Temporal service | 6 | 15 min |
| 13 | CSV export & formatters | 5 | 10 min |
| 14 | CLI | 0 (manual) | 10 min |
| 15 | E2E verification | 0 (manual) | 10 min |
| **Total** | | **41 tests** | |
