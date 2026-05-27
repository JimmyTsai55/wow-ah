# WoW AH Gold Arbitrage Bot — Design Spec

## Context

玩家擁有煉金 + 草藥學雙採，希望透過 Blizzard 官方 AH API 拉取拍賣場即時價格，用 Python 進行材料-成品價差分析與時間序列波動偵測，找出有利可圖的套利機會。這是純資料面的分析工具（CLI），不涉及遊戲內自動化操作。

## Requirements

- **遊戲版本**：Retail（The War Within）
- **資料來源**：Blizzard Game Data API（OAuth2 client credentials）
- **雙策略**：
  1. 材料 vs 成品價差（配方利潤分析）
  2. 跨時段價格波動（買低賣高訊號）
- **輸出**：CLI 報表 + CSV 匯出
- **配方資料**：第一版手動 JSON，之後可擴展為 API 自動同步
- **預測複雜度**：統計規則型（移動平均、標準差、百分位）

## Architecture

遵循 Clean Architecture 原則，依賴方向由外向內：

```
CLI (cli.py)
  → Service (services/)
    → Protocol (protocols/)  ← Adapter (adapters/)
                                  ↑
                           Schemas (schemas/) — 無依賴
```

### 分層職責

| 層級 | 目錄 | 職責 | 可依賴 | 禁止依賴 |
|------|------|------|--------|----------|
| CLI | `cli.py` | 薄控制器，參數解析與路由 | Service, Schemas | 業務邏輯 |
| Service | `services/` | 核心業務邏輯 | Protocol, Schemas | Adapter, 外部 SDK |
| Protocol | `protocols/` | 抽象介面定義 | 無 | 任何實作 |
| Adapter | `adapters/` | 外部服務實作 | 外部 SDK, Protocol | Service |
| Core | `core/` | 設定、OAuth2 token | 外部 SDK | Service |
| Schemas | `schemas/` | 資料模型 | 無 | 任何邏輯 |
| Export | `export/` | CSV 匯出、CLI 格式化 | Schemas | Service |
| Exceptions | `exceptions/` | 錯誤訊息集中管理 | 無 | 任何邏輯 |

### Protocol 設計（務實抽象）

只在以下兩處使用 Protocol：

**`MarketDataProtocol`** — 抽象市場資料來源，讓 Service 可用 fixture 做單元測試：
```python
class MarketDataProtocol(Protocol):
    def fetch_commodities(self) -> list[CommodityListing]: ...
    def get_item(self, item_id: int) -> ItemInfo: ...
```

**`PriceStoreProtocol`** — 抽象儲存層，未來可從 SQLite 換 DuckDB：
```python
class PriceStoreProtocol(Protocol):
    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None: ...
    def get_price_history(self, item_id: int, start: str, end: str) -> list[PriceSnapshot]: ...
    def get_latest_prices(self, item_ids: list[int]) -> dict[int, PriceSnapshot]: ...
```

**不使用 Protocol 的地方**（只有一個實作，無需抽象）：
- 配方 loader — 純粹的 JSON 讀取
- CSV export — 純函式工具
- OAuth2 auth — 綁死 Blizzard，無替代

## Project Structure

```
wow/
  pyproject.toml
  .env                              # BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET
  src/wow_ah/
    __init__.py
    cli.py                          # Typer CLI entry point
    
    services/
      __init__.py
      fetch_service.py              # 協調 API 拉取 → 過濾 → 存入
      spread_service.py             # 材料 vs 成品價差分析
      temporal_service.py           # 移動平均、標準差、百分位訊號
    
    protocols/
      __init__.py
      market_data.py                # MarketDataProtocol
      price_store.py                # PriceStoreProtocol
    
    adapters/
      __init__.py
      blizzard_adapter.py           # 實作 MarketDataProtocol
      sqlite_adapter.py             # 實作 PriceStoreProtocol
    
    core/
      __init__.py
      config.py                     # pydantic-settings，載入 .env
      auth.py                       # OAuth2 token 取得與快取
    
    schemas/
      __init__.py
      prices.py                     # PriceSnapshot, CommodityListing, SpreadResult
      recipes.py                    # Recipe, Reagent
    
    recipes/
      __init__.py
      loader.py                     # 載入 + 驗證 alchemy.json
      data/
        alchemy.json                # 手動配方定義
    
    export/
      __init__.py
      csv_export.py                 # CSV 匯出
      formatters.py                 # CLI 表格格式化（tabulate）
    
    exceptions/
      __init__.py
      base.py                       # AppException 基礎類別
      messages.py                   # 錯誤訊息常數集中管理
  
  tests/
    __init__.py
    test_spread_service.py          # 用 mock PriceStoreProtocol 測試
    test_temporal_service.py
    test_blizzard_adapter.py        # integration test with fixture
    test_recipe_loader.py
    fixtures/
      sample_commodities.json       # Blizzard API 回應範例
  
  data/                             # gitignored
    wow_ah.db
    exports/
```

## Data Model

### SQLite Schema

```sql
CREATE TABLE price_snapshots (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,          -- ISO 8601
    min_price INTEGER NOT NULL,       -- 銅幣單位
    median_price INTEGER,
    mean_price INTEGER,
    total_quantity INTEGER,
    num_auctions INTEGER
);
CREATE INDEX idx_snapshots_item_ts ON price_snapshots(item_id, timestamp);

CREATE TABLE items (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    quality TEXT,
    item_class TEXT,
    item_subclass TEXT,
    last_updated TEXT
);

CREATE TABLE recipes (
    recipe_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    profession TEXT NOT NULL DEFAULT 'Alchemy',
    output_item_id INTEGER NOT NULL,
    output_quantity INTEGER DEFAULT 1
);

CREATE TABLE recipe_reagents (
    recipe_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, item_id)
);
```

### Data Models (dataclasses)

```python
# schemas/prices.py
@dataclass
class CommodityListing:
    """Blizzard API 回傳的單筆拍賣"""
    item_id: int
    unit_price: int         # 銅幣
    quantity: int

@dataclass
class PriceSnapshot:
    """聚合後的價格快照（每個 item 每次 fetch 一行）"""
    item_id: int
    timestamp: str
    min_price: int          # 銅幣（該物品所有拍賣中的最低單價）
    median_price: int | None  # 按數量加權的中位數單價
    mean_price: int | None    # 按數量加權的平均單價
    total_quantity: int | None  # 所有拍賣的總數量
    num_auctions: int | None    # 拍賣筆數

@dataclass
class ItemInfo:
    """物品 metadata（快取自 Blizzard Item API）"""
    item_id: int
    name: str
    quality: str | None
    item_class: str | None
    item_subclass: str | None

@dataclass
class SpreadResult:
    recipe_name: str
    output_item_id: int
    material_cost: int      # 銅幣
    product_price: int      # 銅幣
    profit: int             # 銅幣（已扣 5% AH 手續費）
    margin_pct: float       # 利潤率 %

# schemas/recipes.py
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
    reagents: list[Reagent]
```

### 聚合邏輯

Blizzard commodity endpoint 回傳的是逐筆拍賣 (`CommodityListing`)，ingest 時需聚合為 `PriceSnapshot`：

```python
# 在 fetch_service 中，對同一 item_id 的所有 listings：
listings = [l for l in all_listings if l.item_id == target_id]
min_price = min(l.unit_price for l in listings)
total_qty = sum(l.quantity for l in listings)
# 加權平均：Σ(unit_price × quantity) / total_qty
mean_price = sum(l.unit_price * l.quantity for l in listings) // total_qty
# 加權中位數：展開為逐個數量的價格序列，取中位數
num_auctions = len(listings)
```

## Blizzard API Integration

### Authentication (core/auth.py)

- OAuth2 Client Credentials flow
- POST `https://oauth.battle.net/token` with client_id/client_secret
- Token 有效期 24 小時，快取在記憶體中，過期前自動 refresh
- Credentials 從 `.env` 載入（透過 `config.py`）

### Commodity Fetch (adapters/blizzard_adapter.py)

- GET `https://{region}.api.blizzard.com/data/wow/auctions/commodities`
  - `namespace=dynamic-{region}`（預設 `us`）
  - `locale=en_US`
- 回應 ~5-15 MB JSON，包含所有 commodity auctions
- **關鍵優化**：ingest 時只處理 watchlist 中的 item_id（從配方 reagents + outputs 衍生），把 ~50,000 條拍賣過濾為 ~30-50 行快照
- 檢查 `Last-Modified` header，若與最後一次快照相同則 skip（避免重複寫入）

### Item Metadata (adapters/blizzard_adapter.py)

- GET `https://{region}.api.blizzard.com/data/wow/item/{itemId}`
  - `namespace=static-{region}`
- 只在首次遇到新 item_id 或 metadata 過期時呼叫
- 快取在 `items` 表

## Analysis Logic

### Strategy 1: Spread Analysis (services/spread_service.py)

```
對每個配方：
  material_cost = Σ(reagent.latest_min_price × reagent.quantity)
  product_revenue = output.latest_min_price × output_quantity
  ah_fee = product_revenue × 0.05
  profit = product_revenue - ah_fee - material_cost
  margin_pct = profit / material_cost × 100

輸出：依 margin_pct 降序排列的 SpreadResult 清單
標記：profit > 0 為綠色，< 0 為紅色
```

### Strategy 2: Temporal Analysis (services/temporal_service.py)

```
對每個追蹤物品（使用歷史快照資料）：
  ma_24h  = 24 小時移動平均
  ma_72h  = 72 小時移動平均
  ma_7d   = 7 天移動平均
  std_7d  = 7 天標準差
  pct_7d  = 當前價格在 7 天歷史中的百分位

  買入訊號條件（任一觸發）：
    - current_price < ma_7d - 1.5 × std_7d
    - pct_7d < 10

  賣出訊號條件（任一觸發）：
    - current_price > ma_7d + 1.5 × std_7d
    - pct_7d > 90

輸出：物品價格報表，含 MA、訊號標記、百分位
```

## CLI Commands

| 指令 | 功能 | 核心參數 |
|------|------|---------|
| `wow-ah fetch` | 拉取 API → 過濾 → 存入 SQLite | `--region us` |
| `wow-ah prices` | 查看最近價格 | `--item NAME`, `--hours 24` |
| `wow-ah spreads` | 配方利潤排名 | `--min-margin 0` |
| `wow-ah trends` | 移動平均 + 買賣訊號 | `--item NAME`, `--days 7` |
| `wow-ah export` | 匯出歷史資料 CSV | `--days 30`, `--output path` |
| `wow-ah recipes list` | 列出已載入配方 | — |
| `wow-ah recipes reload` | 從 JSON 重新匯入 SQLite | — |

Entry point 定義在 `pyproject.toml`：
```toml
[project.scripts]
wow-ah = "wow_ah.cli:app"
```

## Recipe JSON Format

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
    }
  ]
}
```

初始版本手動維護 5-10 個常用煉金配方，之後可擴展為從 Blizzard Profession API 自動拉取。

## Scheduling

- 使用 macOS cron，每小時執行一次 fetch：
  ```
  0 * * * * cd /Users/jimmytsai/Documents/code/wow && uv run wow-ah fetch >> data/fetch.log 2>&1
  ```
- 分析指令（prices, spreads, trends）為按需手動執行
- `Last-Modified` header 檢查防止重複寫入

## Error Handling

遵循 `error-messages` skill 原則，錯誤訊息集中在 `exceptions/messages.py`：

```python
# exceptions/messages.py
class APIErrorMessages:
    AUTH_FAILED = "Blizzard OAuth2 認證失敗: {error}"
    FETCH_FAILED = "商品資料拉取失敗: {status_code}"
    RATE_LIMITED = "API 速率限制，請稍後再試"

class DataErrorMessages:
    NO_SNAPSHOTS = "沒有找到 {item_name} 的價格快照，請先執行 fetch"
    INSUFFICIENT_HISTORY = "{item_name} 歷史資料不足 {required} 小時，目前只有 {actual} 小時"
    RECIPE_NOT_FOUND = "找不到配方: {recipe_name}"

# exceptions/base.py
class AppException(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details
```

## Testing Strategy

| 層級 | 測試類型 | Mock 什麼 | 重點 |
|------|---------|-----------|------|
| SpreadService | Unit test | PriceStoreProtocol | 利潤計算正確性、邊界案例 |
| TemporalService | Unit test | PriceStoreProtocol | MA/std/percentile 計算 |
| BlizzardAdapter | Integration test | 無（用 fixture JSON） | API 回應解析 |
| RecipeLoader | Unit test | 無 | JSON 驗證、錯誤處理 |
| SQLiteAdapter | Integration test | 無 | CRUD 操作 |

## Dependencies

```toml
[project]
dependencies = [
    "httpx",              # HTTP client（async-ready，比 requests 現代）
    "typer",              # CLI framework
    "pydantic-settings",  # .env 配置載入
    "tabulate",           # CLI 表格格式化
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
]
```

## Verification Plan

1. **API 連線測試**：`wow-ah fetch` 成功拉取並存入 SQLite
2. **資料驗證**：`wow-ah prices` 顯示正確的物品價格
3. **價差分析**：`wow-ah spreads` 正確計算材料成本 vs 成品收入
4. **時序分析**：累積 24hr+ 資料後，`wow-ah trends` 產出正確的 MA 和訊號
5. **匯出驗證**：`wow-ah export` 產出格式正確的 CSV
6. **單元測試**：`pytest tests/` 全部通過
