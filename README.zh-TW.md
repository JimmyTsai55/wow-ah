# wow-ah

[English](README.md) | **繁體中文**

**WoW 拍賣場套利分析工具** — 一個 Python 3.12 CLI，從暴雪 Game Data API 抓取魔獸世界（正式服 / *地心之戰*）的拍賣場資料、找出有利可圖的交易，並可選擇性地透過 **OpenAI 多 agent 顧問**把原始分析轉成排好優先順序的白話建議。

> ⚠️ 暴雪 Game Data API 是**唯讀**的——沒有任何下單或掛賣的 API。本工具負責**分析與建議**，實際交易需你在遊戲內手動完成。

---

## 功能

兩種套利策略，再加上一層 AI：

1. **配方價差分析** — 比較製造材料成本與成品售價（扣除 5% 拍賣場手續費），依利潤率排序配方。
2. **時間序列價格訊號** — 追蹤價格歷史，用移動平均、標準差、百分位排名產出 **BUY / SELL / HOLD** 訊號。
3. **多 agent 顧問**（選用，需 OpenAI 金鑰）— 由主控 agent 分派給專家 agent（配方 / 趨勢 / 風險），彙整成繁體中文建議報告。亦可作為 **MCP server** 使用。

所有分析皆**唯讀本地 SQLite 資料庫**。金額全程以整數 copper 計算；時間戳為 ISO 8601 UTC。

---

## 架構

Clean Architecture——依賴方向由外向內，並依分層強制：

| 層級 | 路徑 | 職責 |
|---|---|---|
| Agent | `src/wow_ah/agent/` | OpenAI 多 agent 協作 + 確定性新鮮度關卡 + CLI/MCP 工具 |
| CLI | `src/wow_ah/cli.py` | Typer 指令接線 |
| Services | `src/wow_ah/services/` | 業務邏輯（fetch / spread / temporal） |
| Protocols | `src/wow_ah/protocols/` | `MarketDataProtocol`、`PriceStoreProtocol`、`LLMProtocol` |
| Adapters | `src/wow_ah/adapters/` | `BlizzardAdapter`（HTTPS + OAuth2）、`SQLiteAdapter` |
| Core | `src/wow_ah/core/` | 設定、OAuth2 token 管理 |
| Schemas | `src/wow_ah/schemas/` | 純 `@dataclass` DTO（無邏輯） |

測試透過 protocol 注入 fake——整套測試完全不打網路（暴雪或 OpenAI 皆然）。

---

## 安裝

需要 **Python ≥ 3.12**。

### 用 uv（推薦——`uv.lock` 已提交）

```bash
uv sync                 # 安裝執行期 + 開發依賴
uv run wow-ah --help
```

### 用 conda / pip

```bash
conda create -n wow-ah python=3.12 -y
conda run -n wow-ah python -m pip install -e ".[dev]"
# 或：python -m pip install -r requirements-dev.txt
```

> **conda PATH 注意**：直接 `conda run -n wow-ah pytest|pip|wow-ah` 可能會解析到 `PATH` 上的系統 Python。請改用 `conda run -n wow-ah python -m pytest` / `python -m pip`，或先 `conda activate wow-ah`。

---

## 設定

建立 `.env`（參考 `.env.example`）：

```bash
# 暴雪 Game Data API（fetch 需要）
BLIZZARD_CLIENT_ID=your_client_id
BLIZZARD_CLIENT_SECRET=your_client_secret
BLIZZARD_REGION=us            # us | eu | kr | tw | cn

# OpenAI（ask / advise 需要）
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=              # 選用（代理 / 相容端點）
OPENAI_DEFAULT_MODEL=gpt-4.1-nano

# 各 agent 模型覆寫（選用；未設則退回 OPENAI_DEFAULT_MODEL）
WOW_AH_ORCHESTRATOR_MODEL=
WOW_AH_RECIPE_MODEL=
WOW_AH_TREND_MODEL=
WOW_AH_RISK_MODEL=
```

- `fetch` 需要暴雪憑證。其他指令只讀本地 SQLite 資料庫 `data/wow_ah.db`（可用 `DB_PATH` 覆寫）。
- 每個 agent 的模型獨立解析——設定特定的 `WOW_AH_*_MODEL` 即覆寫，否則用 `OPENAI_DEFAULT_MODEL`。預設 `gpt-4.1-nano` 最便宜；若你的 OpenAI project 沒有權限，改設 `OPENAI_DEFAULT_MODEL=gpt-4o-mini`。

---

## 使用

```bash
# 資料
wow-ah fetch                        # 抓取商品價格（每小時限一次）
wow-ah prices                       # 追蹤物品的最新價
wow-ah export                       # 匯出價格歷史到 data/exports/prices.csv

# 分析
wow-ah spreads                      # 配方利潤率（排序；預設隱藏虧損）
wow-ah spreads --min-margin=-100    # 含虧損配方一起顯示
wow-ah trends                       # BUY / SELL / HOLD 訊號（需 ≥24h 歷史）
wow-ah recipes list                 # 列出已載入的配方

# AI 多 agent 顧問（需 OPENAI_API_KEY）
wow-ah ask "現在哪個煉金配方最賺？"      # 自然語言問答
wow-ah advise                       # 主動產生交易建議報告
wow-ah mcp                          # 啟動 MCP server 暴露分析工具
```

**追蹤清單由配方推導**——新增配方就是開始追蹤新物品的方式。配方定義以 JSON 放在 `src/wow_ah/recipes/data/`（`alchemy.json`、`cooking.json`）；要新增一個專業，丟一個新的 `*.json` 進去即可。

---

## 多 agent 顧問

`ask` 與 `advise` 會跑一個**主控 agent（orchestrator）**，把每個專家當成可呼叫的工具：

```
問題
  → [資料新鮮度關卡]   （確定性、不用 LLM——資料超過 6 小時就擋下）
  → orchestrator       → 配方分析師   （get_spreads / list_recipes）
                       → 趨勢分析師   （get_trends / get_prices）
                       → 風險審查員   （檢查結論是否可靠）
  → orchestrator 彙整成繁體中文報告
```

- **唯讀**：工具不會呼叫暴雪 API、不會下單；`fetch` 維持手動。
- **各 agent 可調模型**：用 `WOW_AH_*_MODEL` 環境變數依角色混搭便宜與強力的模型。
- LLM **不計算**價格——數字由確定性的 services 算；agent 負責挑選、排序、給理由、彙整。

### MCP server

`wow-ah mcp` 透過 Model Context Protocol（FastMCP）暴露 `get_spreads`、`get_trends`、`get_prices`、`list_recipes`，讓任何 MCP 客戶端（Claude Desktop、Claude Code 等）都能呼叫同一批唯讀工具。

---

## 用合成資料實驗

真實資料在累積 ≥24 小時的逐時 fetch 之前會很稀疏，而且製造的成品往往沒有商品價格。想立刻端到端跑 agent，可以灌一個**獨立的**合成資料庫：

```bash
python scripts/seed_sim_db.py                                   # 寫入 data/wow_ah_sim.db
DB_PATH=data/wow_ah_sim.db OPENAI_DEFAULT_MODEL=gpt-4o-mini wow-ah advise
```

種子腳本會產生 7 天的逐時歷史，含有賺有賠的配方與 BUY/SELL/HOLD 訊號（deterministic）。調整 `FACTORS` / `END_MULT` 常數可改變情境。各 agent 能分析什麼、以及現成的實驗指令，見 [`docs/agent-experiment-guide.md`](docs/agent-experiment-guide.md)。

> 樣本 DB 的時間戳固定在產生當下——約 6 小時後新鮮度關卡會視其為過期；重跑種子腳本即可刷新。

---

## 開發

```bash
uv run pytest                       # 全套測試
uv run pytest --cov=wow_ah          # 含覆蓋率
# conda：conda run -n wow-ah python -m pytest -q
```

- Services 用結構上符合 protocol 的 `FakeStore` / `FakeMarketData` / `FakeLLM` 測試——不用 `unittest.mock`、不打網路。
- 錯誤處理集中管理：拋出 `AppException` 子類（`APIError` / `DataError`），訊息來自 `src/wow_ah/exceptions/messages.py` 的常數。

設計文件與實作計劃放在 [`docs/superpowers/`](docs/superpowers/)。

---

## 領域慣例

- **金額全程整數 copper**；轉換成 `Ng Xs Yc` 只在顯示時發生。
- **拍賣場手續費**固定 5%，以整數運算。
- **`fetch` 每 UTC 小時限一次**。
- **趨勢分析需 ≥24 筆資料**；顧問執行前，新鮮度關卡會擋下超過 6 小時的資料。
