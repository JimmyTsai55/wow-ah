# WoW AH OpenAI 多 Agent 協作 — Design Spec

## Context

在現有的 `wow-ah` CLI 套利分析工具之上，加入一組由 OpenAI 驅動的協作式 AI agent。使用者可用自然語言提問（`wow-ah ask`）或請系統主動產出交易建議報告（`wow-ah advise`），同時把分析能力暴露成 MCP server（`wow-ah mcp`）供任何 MCP 客戶端調用。

採用 **orchestrator（主控）模式**：一個主控 agent 拆解使用者意圖、分派給專門的子 agent，再彙整成繁體中文答案。每個 agent 可獨立設定模型。

### 重要前提與限制

- **暴雪 Game Data API 為唯讀**：沒有任何下單／買進／掛賣 API，遊戲內交易動作無法被程式自動執行（且違反使用條款）。因此 agent 的產出是**分析與決策建議**，實際下單仍由使用者手動完成。
- **agent 不主動 fetch**：所有工具唯讀本地 SQLite（`data/wow_ah.db`），不打暴雪 API。資料更新仍透過既有的手動 `wow-ah fetch` 指令，避免 agent 亂打外部 API。

## Requirements

- **Provider**：OpenAI，使用原生 `openai` Python SDK（function calling）。
- **模型**：評估階段全部預設 `gpt-4.1-nano`（目前最便宜，$0.10/$0.40 per 1M tokens），每個 agent 可用環境變數獨立覆寫。
- **兩個入口行為**：
  1. 自然語言問答（`wow-ah ask "<問題>"`）
  2. 主動交易建議報告（`wow-ah advise`）
- **MCP server**：`wow-ah mcp` 用 FastMCP 暴露同一批工具。
- **輸出語言**：繁體中文（道具名稱可能維持英文，因暴雪 API 回傳英文）。
- **可測試性**：沿用專案慣例——以 protocol + 注入 fake 進行單元測試，測試完全不打網路（OpenAI 與暴雪皆不打）。

## Architecture

新增一個 `agent/` 層，位階在 `services` 之上、與 `cli` 平行（皆為組裝與入口）。核心原則：**工具實作只寫一次**，CLI agent 與 MCP server 共用。

```
src/wow_ah/agent/
  tools.py         # service-backed 工具: get_spreads / get_trends / get_prices / list_recipes
  freshness.py     # 確定性新鮮度關卡（不使用 LLM）
  llm.py           # LLMProtocol + OpenAIChatAdapter（包裝 openai SDK）
  base.py          # Agent 類別（name/model/system_prompt/tools + function-calling 迴圈）
  specialists.py   # 組裝 3 個專家 agent
  orchestrator.py  # 主控 agent（子 agent 當工具）+ 整體執行流程（含新鮮度關卡）
  mcp_server.py    # FastMCP server，暴露同一批 tools.py 工具
```

### 分層職責與依賴方向

| 層級 | 目錄 | 職責 | 可依賴 | 禁止依賴 |
|------|------|------|--------|----------|
| Agent | `agent/` | LLM 協作、工具組裝、CLI/MCP 入口 | services, adapters, recipes, schemas, core, 外部 SDK | — |
| Service | `services/` | 核心業務邏輯 | protocols, schemas | adapters, 外部 SDK |
| Protocol | `protocols/` | 抽象介面 | schemas | 任何實作 |
| Adapter | `adapters/` | 外部服務實作 | core, schemas, exceptions, 外部 SDK | services |
| Core | `core/` | 設定、OAuth2 token | 外部 SDK, exceptions | services |
| Schemas | `schemas/` | 資料模型 | 無 | 任何邏輯 |

`agent/` 層遵循與 `cli/` 相同的定位：它組裝 store/market/recipes 與 services，並呼叫它們；不把業務邏輯下放到 service 以外。

### LLMProtocol（可測試性核心）

仿照現有 `MarketDataProtocol`／`PriceStoreProtocol`，新增一個抽象 LLM 呼叫的 protocol，讓測試注入 `FakeLLM`：

```python
class LLMProtocol(Protocol):
    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse: ...
```

- `OpenAIChatAdapter` 為正式實作，包裝 `openai` SDK 的 `chat.completions.create`，並把 openai 例外映射成專案的 `APIError`。
- `FakeLLM` 在測試中依預設腳本回傳工具呼叫與最終訊息，**不打網路、不需 API key**。
- `LLMResponse` 為 schemas 層的 `@dataclass` DTO，封裝 `content`、`tool_calls`、`finish_reason`。

### Agent 類別

```python
@dataclass
class Agent:
    name: str
    model: str
    system_prompt: str
    tools: list[Tool]        # 每個 Tool 綁定名稱、JSON schema、可呼叫實作
    llm: LLMProtocol
```

`Agent.run(user_input)` 執行 function-calling 迴圈：送訊息 → 若回 `tool_calls` 則執行對應工具、把結果回填 → 直到模型給出最終文字。迴圈設有最大輪數上限，避免無限循環。

## Agents 陣容

| Agent | 預設模型 | 工具 | 職責 |
|---|---|---|---|
| Orchestrator | `gpt-4.1-nano` | 把下面 3 個專家 agent 當工具 | 拆解使用者意圖、分派、彙整繁中最終答案 |
| 配方利潤分析師 | `gpt-4.1-nano` | `get_spreads`, `list_recipes` | spreads 領域：哪些配方淨利最高（含 AH 手續費） |
| 價格趨勢分析師 | `gpt-4.1-nano` | `get_trends`, `get_prices` | trends 領域：BUY/SELL/HOLD 訊號與進出場時機 |
| 風險審查員 | `gpt-4.1-nano` | `get_prices` | 檢查其他 agent 結論是否可靠（交易量、價格異常、資料量） |

**子 agent 以「agent-as-tool」方式暴露給 orchestrator**：orchestrator 把每個專家包成一個可呼叫的工具，由模型自行決定要諮詢誰。

### 資料新鮮度關卡（確定性，非 LLM）

`freshness.py` 提供一個確定性前置檢查：在啟動任何 LLM 之前，比較 DB 中最新 snapshot 時間戳與當前 UTC 時間。若超過門檻（預設 `MAX_DATA_AGE_HOURS = 6`，定義為模組常數），直接回傳提醒「資料太舊，請先執行 `wow-ah fetch`」，不進入 LLM 流程。此設計避免用過期價格做決策，也省下 token。

## 執行流程

以 `wow-ah ask "現在哪個煉金配方最賺？"` 為例：

1. CLI 讀 config，組裝 store/market/recipes、LLM adapter、各 agent（解析各自模型）。
2. **新鮮度關卡**：DB 太舊 → 直接提醒並結束；否則繼續。
3. Orchestrator 收到問題 → 決定諮詢「配方利潤分析師」。
4. 配方分析師執行其 function-calling 迴圈（呼叫 `get_spreads`／`list_recipes`，唯讀本地 DB）→ 回傳分析。
5. Orchestrator 視需要請「風險審查員」檢視該結論。
6. Orchestrator 彙整成繁體中文答案 → CLI 印出。

`wow-ah advise` 為相同流程，但 orchestrator 收到固定提示詞，主動同時諮詢配方與趨勢分析師、經風險審查後產出排序好的買進／賣出建議報告。

## 設定（core/config.py + .env）

```bash
OPENAI_API_KEY=...                     # 必填
OPENAI_BASE_URL=...                    # 選填（走代理／相容端點才需要）
OPENAI_DEFAULT_MODEL=gpt-4.1-nano      # 全域預設
WOW_AH_ORCHESTRATOR_MODEL=...          # 各 agent 選填覆寫
WOW_AH_RECIPE_MODEL=...
WOW_AH_TREND_MODEL=...
WOW_AH_RISK_MODEL=...
```

每個 agent 解析模型的順序：自己的專屬環境變數 → 未設則退回 `OPENAI_DEFAULT_MODEL`。`.env.example` 同步補上 OpenAI 區段。

## Error Handling

沿用專案慣例：

- 新增 `AgentErrorMessages` 至 `exceptions/messages.py`，涵蓋：缺少 `OPENAI_API_KEY`、OpenAI API 錯誤、超過最大工具呼叫輪數。
- 以 `AppException` 子類（`APIError` / `DataError`）拋出，訊息一律來自類別常數並 `.format(...)`，不內聯字串。
- `OpenAIChatAdapter` 不讓 `openai` 的例外逸出——攔截後重拋為 `APIError`。
- 新 CLI 指令（`ask` / `advise` / `mcp`）皆套用 `_handle_errors` 裝飾器。

## Testing

- 工具函式（`tools.py`）以現有 `FakeStore` / `FakeMarketData` 測試，不打網路、不需 API key。
- Agent 迴圈與 orchestrator 協作以注入 `FakeLLM` 測試：驗證工具被正確分派、結果正確回填、達到最大輪數時正確報錯。
- 新鮮度關卡以固定時間戳輸入做純函式測試。
- **測試絕不打真實 OpenAI 或暴雪 API**，suite 維持零網路、無 `unittest.mock`。

## 明確排除（YAGNI）

- ❌ 自動排程／背景監控（之後可用 cron 包 `advise`）。
- ❌ 自動下單（暴雪 API 不支援，技術上不可能）。
- ❌ agent 自動觸發 `fetch`（資料更新維持手動）。
- ❌ OpenAI Agents SDK（改用自寫薄協作層以維持可測試性與低依賴）。
