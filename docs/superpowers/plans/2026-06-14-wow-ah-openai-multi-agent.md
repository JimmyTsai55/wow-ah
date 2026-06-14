# WoW AH OpenAI 多 Agent 協作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在現有 `wow-ah` CLI 上加一個 OpenAI 驅動的 orchestrator 多 agent 層，提供 `wow-ah ask` / `wow-ah advise` 問答與建議報告，並以 FastMCP 暴露同一批工具。

**Architecture:** 新增 `agent/` 層（與 `cli` 平行）。一個 `LLMProtocol` 抽象 OpenAI 呼叫以利測試注入 fake；`Agent` 類別執行 function-calling 迴圈；orchestrator 把專家子 agent 當工具呼叫；資料新鮮度為確定性前置關卡（非 LLM）。所有工具唯讀本地 SQLite。

**Tech Stack:** Python 3.12、`openai` SDK、`mcp`（FastMCP）、Typer、pydantic-settings、pytest。所有測試注入 `FakeLLM` / `FakeStore`，零網路。

**設計慣例（沿用現有 codebase）：**
- 金錢一律整數 copper；時間戳為 ISO 8601 UTC 字串 `%Y-%m-%dT%H:%M:%SZ`。
- 錯誤訊息集中在 `exceptions/messages.py`，以 `AppException` 子類 `.format(...)` 拋出。
- 測試用結構化 fake（無 `unittest.mock`）、不打網路。
- 每個 agent 模型可獨立用環境變數覆寫，預設 `gpt-4.1-nano`。

**檔案結構：**
- Create `src/wow_ah/schemas/agents.py` — DTO：`ToolCall` / `LLMResponse` / `FreshnessResult`
- Create `src/wow_ah/protocols/llm.py` — `LLMProtocol`
- Create `src/wow_ah/agent/__init__.py`
- Create `src/wow_ah/agent/llm.py` — `OpenAIChatAdapter`
- Create `src/wow_ah/agent/freshness.py` — `check_freshness` 確定性關卡
- Create `src/wow_ah/agent/tools.py` — 共用工具函式 + `Tool` 建構器
- Create `src/wow_ah/agent/base.py` — `Tool` dataclass + `Agent` 迴圈
- Create `src/wow_ah/agent/specialists.py` — 3 個專家 agent 建構器
- Create `src/wow_ah/agent/orchestrator.py` — orchestrator + `run_advisor` 流程
- Create `src/wow_ah/agent/mcp_server.py` — FastMCP server
- Modify `src/wow_ah/core/config.py` — OpenAI 設定 + `model_for`
- Modify `src/wow_ah/exceptions/messages.py` — `AgentErrorMessages`
- Modify `src/wow_ah/cli.py` — `ask` / `advise` / `mcp` 指令
- Modify `pyproject.toml` — 加 `openai`、`mcp` 依賴
- Modify `.env.example` — OpenAI 區段

---

### Task 1: 依賴與設定

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/wow_ah/core/config.py`
- Modify: `.env.example`
- Test: `tests/test_config_openai.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_config_openai.py`:

```python
from wow_ah.core.config import Settings


def test_default_openai_model_is_cheapest():
    s = Settings(_env_file=None)
    assert s.openai_default_model == "gpt-4.1-nano"


def test_model_for_falls_back_to_default():
    s = Settings(_env_file=None, openai_default_model="gpt-4.1-nano")
    assert s.model_for("orchestrator") == "gpt-4.1-nano"


def test_model_for_uses_override():
    s = Settings(
        _env_file=None,
        openai_default_model="gpt-4.1-nano",
        wow_ah_recipe_model="gpt-5.4-nano",
    )
    assert s.model_for("recipe") == "gpt-5.4-nano"
    assert s.model_for("trend") == "gpt-4.1-nano"
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_config_openai.py -v`
Expected: FAIL（`AttributeError: 'Settings' object has no attribute 'openai_default_model'`）

- [ ] **Step 3: 改 config.py**

Replace the whole `src/wow_ah/core/config.py` with:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    blizzard_client_id: str = ""
    blizzard_client_secret: str = ""
    blizzard_region: str = "us"
    db_path: str = "data/wow_ah.db"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_default_model: str = "gpt-4.1-nano"
    wow_ah_orchestrator_model: str = ""
    wow_ah_recipe_model: str = ""
    wow_ah_trend_model: str = ""
    wow_ah_risk_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_for(self, agent: str) -> str:
        """Resolve the model for an agent key, falling back to the global default."""
        override = getattr(self, f"wow_ah_{agent}_model", "")
        return override or self.openai_default_model


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_config_openai.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 加依賴並安裝**

Edit `pyproject.toml` — 在 `dependencies` 陣列加入兩行（放在 `"tabulate>=0.9",` 之後）：

```toml
    "openai>=1.60",
    "mcp>=1.2",
```

Then install into the conda env:

Run: `conda run -n wow-ah pip install "openai>=1.60" "mcp>=1.2"`
Expected: `Successfully installed openai-... mcp-...`

- [ ] **Step 6: 更新 .env.example**

Append to `.env.example`:

```
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=
OPENAI_DEFAULT_MODEL=gpt-4.1-nano
WOW_AH_ORCHESTRATOR_MODEL=
WOW_AH_RECIPE_MODEL=
WOW_AH_TREND_MODEL=
WOW_AH_RISK_MODEL=
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/wow_ah/core/config.py .env.example tests/test_config_openai.py
git commit -m "feat: add OpenAI settings with per-agent model resolution"
```

---

### Task 2: Agent schemas 與錯誤訊息

**Files:**
- Create: `src/wow_ah/schemas/agents.py`
- Modify: `src/wow_ah/exceptions/messages.py`
- Test: `tests/test_agent_schemas.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_agent_schemas.py`:

```python
from wow_ah.schemas.agents import ToolCall, LLMResponse, FreshnessResult


def test_tool_call_holds_parsed_arguments():
    tc = ToolCall(id="call_1", name="get_spreads", arguments={"min_margin": 5.0})
    assert tc.arguments["min_margin"] == 5.0


def test_llm_response_defaults_to_no_tool_calls():
    resp = LLMResponse(content="hi", tool_calls=[], finish_reason="stop")
    assert resp.tool_calls == []
    assert resp.content == "hi"


def test_freshness_result_fields():
    fr = FreshnessResult(is_fresh=False, last_fetch=None, age_hours=None, message="stale")
    assert fr.is_fresh is False
    assert fr.message == "stale"
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_agent_schemas.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.schemas.agents'`）

- [ ] **Step 3: 建立 schemas/agents.py**

Create `src/wow_ah/schemas/agents.py`:

```python
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A single tool/function call requested by the model."""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Normalized response from one LLM completion call."""
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"


@dataclass
class FreshnessResult:
    """Outcome of the deterministic data-freshness gate."""
    is_fresh: bool
    last_fetch: str | None
    age_hours: float | None
    message: str
```

- [ ] **Step 4: 加錯誤訊息**

Append to `src/wow_ah/exceptions/messages.py`:

```python


class AgentErrorMessages:
    MISSING_API_KEY = "OPENAI_API_KEY is not set. Add it to your .env file."
    OPENAI_ERROR = "OpenAI API call failed: {error}"
    MAX_ROUNDS_EXCEEDED = (
        "Agent '{agent}' exceeded the maximum of {limit} tool-call rounds"
    )
    UNKNOWN_TOOL = "Agent '{agent}' requested an unknown tool: {tool}"
```

- [ ] **Step 5: 執行確認通過**

Run: `pytest tests/test_agent_schemas.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/schemas/agents.py src/wow_ah/exceptions/messages.py tests/test_agent_schemas.py
git commit -m "feat: add agent DTOs and AgentErrorMessages"
```

---

### Task 3: LLMProtocol 與 OpenAIChatAdapter

**Files:**
- Create: `src/wow_ah/protocols/llm.py`
- Create: `src/wow_ah/agent/__init__.py`
- Create: `src/wow_ah/agent/llm.py`
- Test: `tests/test_openai_adapter.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_openai_adapter.py`. 用假的 OpenAI client 注入，驗證回應正規化與例外映射——不打網路：

```python
import json
import pytest

from wow_ah.agent.llm import OpenAIChatAdapter
from wow_ah.exceptions.base import APIError


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message, finish_reason):
        self.message = message
        self.finish_reason = finish_reason


class _FakeCompletion:
    def __init__(self, choices):
        self.choices = choices


class _FakeCompletions:
    def __init__(self, completion=None, error=None):
        self._completion = completion
        self._error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return self._completion


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def test_adapter_normalizes_tool_calls():
    tc = _FakeToolCall("call_1", "get_spreads", json.dumps({"min_margin": 5.0}))
    completion = _FakeCompletion([_FakeChoice(_FakeMessage(None, [tc]), "tool_calls")])
    client = _FakeClient(_FakeCompletions(completion=completion))
    adapter = OpenAIChatAdapter(client=client)

    resp = adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)

    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_spreads"
    assert resp.tool_calls[0].arguments == {"min_margin": 5.0}


def test_adapter_handles_plain_content():
    completion = _FakeCompletion([_FakeChoice(_FakeMessage("answer", None), "stop")])
    client = _FakeClient(_FakeCompletions(completion=completion))
    adapter = OpenAIChatAdapter(client=client)

    resp = adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)

    assert resp.content == "answer"
    assert resp.tool_calls == []


def test_adapter_wraps_openai_errors():
    from openai import OpenAIError
    client = _FakeClient(_FakeCompletions(error=OpenAIError("boom")))
    adapter = OpenAIChatAdapter(client=client)

    with pytest.raises(APIError):
        adapter.complete("gpt-4.1-nano", [{"role": "user", "content": "hi"}], None)
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_openai_adapter.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent'`）

- [ ] **Step 3: 建立 protocol**

Create `src/wow_ah/protocols/llm.py`:

```python
from typing import Protocol

from wow_ah.schemas.agents import LLMResponse


class LLMProtocol(Protocol):
    """Abstract interface for a chat-completion LLM call."""

    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        """Run one completion. `tools` is OpenAI-format function schemas or None."""
        ...
```

- [ ] **Step 4: 建立 agent 套件與 adapter**

Create empty `src/wow_ah/agent/__init__.py` (0 bytes).

Create `src/wow_ah/agent/llm.py`:

```python
import json

from openai import OpenAI, OpenAIError

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import AgentErrorMessages
from wow_ah.schemas.agents import LLMResponse, ToolCall


class OpenAIChatAdapter:
    """Wraps the OpenAI Chat Completions API behind LLMProtocol."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str | None = None,
        client=None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(api_key=api_key, base_url=base_url or None)

    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse:
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except OpenAIError as e:
            raise APIError(
                AgentErrorMessages.OPENAI_ERROR.format(error=str(e))
            ) from e

        choice = completion.choices[0]
        raw_calls = choice.message.tool_calls or []
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in raw_calls
        ]
        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
        )
```

- [ ] **Step 5: 執行確認通過**

Run: `pytest tests/test_openai_adapter.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: Commit**

```bash
git add src/wow_ah/protocols/llm.py src/wow_ah/agent/__init__.py src/wow_ah/agent/llm.py tests/test_openai_adapter.py
git commit -m "feat: add LLMProtocol and OpenAIChatAdapter"
```

---

### Task 4: 資料新鮮度關卡

**Files:**
- Create: `src/wow_ah/agent/freshness.py`
- Test: `tests/test_freshness.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_freshness.py`:

```python
from wow_ah.agent.freshness import check_freshness, MAX_DATA_AGE_HOURS


class _Store:
    def __init__(self, last):
        self._last = last

    def get_last_fetch_timestamp(self):
        return self._last

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids): return {}


def test_no_data_is_not_fresh():
    result = check_freshness(_Store(None), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is False
    assert result.last_fetch is None
    assert "fetch" in result.message.lower()


def test_recent_data_is_fresh():
    result = check_freshness(_Store("2026-06-14T11:00:00Z"), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is True
    assert result.age_hours == 1.0


def test_stale_data_is_not_fresh():
    old = "2026-06-14T00:00:00Z"  # 12h before noon, > MAX_DATA_AGE_HOURS
    result = check_freshness(_Store(old), now="2026-06-14T12:00:00Z")
    assert result.is_fresh is False
    assert result.age_hours == 12.0
    assert str(MAX_DATA_AGE_HOURS) in result.message
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_freshness.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.freshness'`）

- [ ] **Step 3: 實作 freshness.py**

Create `src/wow_ah/agent/freshness.py`:

```python
from datetime import datetime

from wow_ah.protocols.price_store import PriceStoreProtocol
from wow_ah.schemas.agents import FreshnessResult

MAX_DATA_AGE_HOURS = 6


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_freshness(store: PriceStoreProtocol, now: str) -> FreshnessResult:
    """Deterministic gate: is the newest snapshot recent enough to trust?"""
    last = store.get_last_fetch_timestamp()
    if last is None:
        return FreshnessResult(
            is_fresh=False,
            last_fetch=None,
            age_hours=None,
            message="資料庫沒有任何價格資料，請先執行 `wow-ah fetch`。",
        )

    age_hours = (_parse(now) - _parse(last)).total_seconds() / 3600
    if age_hours > MAX_DATA_AGE_HOURS:
        return FreshnessResult(
            is_fresh=False,
            last_fetch=last,
            age_hours=age_hours,
            message=(
                f"資料已過期：最後一次 fetch 在 {age_hours:.0f} 小時前"
                f"（門檻 {MAX_DATA_AGE_HOURS} 小時）。請先執行 `wow-ah fetch` 再分析。"
            ),
        )

    return FreshnessResult(
        is_fresh=True,
        last_fetch=last,
        age_hours=age_hours,
        message=f"資料新鮮（{age_hours:.0f} 小時前更新）。",
    )
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_freshness.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/agent/freshness.py tests/test_freshness.py
git commit -m "feat: add deterministic data-freshness gate"
```

---

### Task 5: 共用工具函式

**Files:**
- Create: `src/wow_ah/agent/tools.py`
- Test: `tests/test_agent_tools.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_agent_tools.py`:

```python
import json

from wow_ah.agent.tools import spreads_json, trends_json, prices_json, recipes_json
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest=None, history=None):
        self._latest = latest or {}
        self._history = history or []

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return self._history
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


def _snap(item_id, min_price, ts="2026-06-14T12:00:00Z"):
    return PriceSnapshot(item_id=item_id, timestamp=ts, min_price=min_price)


def _recipe():
    return Recipe(
        name="Test Flask", output_item_id=100, output_quantity=1,
        reagents=[Reagent(item_id=1, name="Herb A", quantity=10)],
    )


def test_spreads_json_returns_recipe_profit():
    store = FakeStore(latest={1: _snap(1, 100), 100: _snap(100, 5000)})
    out = json.loads(spreads_json(store, [_recipe()], min_margin=0.0))
    assert out[0]["recipe_name"] == "Test Flask"
    assert out[0]["profit"] == 5000 - (5000 * 5 // 100) - 1000


def test_recipes_json_lists_definitions():
    out = json.loads(recipes_json([_recipe()]))
    assert out[0]["name"] == "Test Flask"
    assert out[0]["reagents"][0]["name"] == "Herb A"


def test_trends_json_empty_when_no_history():
    store = FakeStore(history=[])
    out = json.loads(trends_json(store, [_recipe()], now="2026-06-14T12:00:00Z", days=7))
    assert out == []


def test_prices_json_filters_by_item_name():
    store = FakeStore(history=[_snap(1, 100)])
    out = json.loads(prices_json(store, [_recipe()], now="2026-06-14T12:00:00Z", item="Nonexistent"))
    assert out == []
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_agent_tools.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.tools'`）

- [ ] **Step 3: 實作 tools.py**

Create `src/wow_ah/agent/tools.py`:

```python
import json
from datetime import datetime, timedelta

from wow_ah.recipes.loader import get_watchlist_item_ids
from wow_ah.schemas.recipes import Recipe
from wow_ah.services.spread_service import SpreadService
from wow_ah.services.temporal_service import TemporalService

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _item_names(recipes: list[Recipe]) -> dict[int, str]:
    names: dict[int, str] = {}
    for recipe in recipes:
        names[recipe.output_item_id] = recipe.name
        for reagent in recipe.reagents:
            names[reagent.item_id] = reagent.name
    return names


def spreads_json(store, recipes: list[Recipe], min_margin: float = 0.0) -> str:
    """Recipe profit spreads (after AH fee), sorted by margin descending."""
    results = SpreadService(price_store=store).analyze(recipes)
    payload = [
        {
            "recipe_name": r.recipe_name,
            "output_item_id": r.output_item_id,
            "material_cost": r.material_cost,
            "product_price": r.product_price,
            "profit": r.profit,
            "margin_pct": round(r.margin_pct, 2),
        }
        for r in results
        if r.margin_pct >= min_margin
    ]
    return json.dumps(payload, ensure_ascii=False)


def trends_json(store, recipes: list[Recipe], now: str, days: int = 7) -> str:
    """BUY/SELL/HOLD signals per tracked item over `days` of history."""
    watchlist = list(get_watchlist_item_ids(recipes))
    names = _item_names(recipes)
    results = TemporalService(price_store=store).analyze(
        item_ids=watchlist, now=now, history_hours=days * 24
    )
    payload = [
        {
            "item_id": r.item_id,
            "item_name": names.get(r.item_id, str(r.item_id)),
            "current_price": r.current_price,
            "ma_7d": round(r.ma_7d, 2),
            "percentile_7d": round(r.percentile_7d, 2),
            "signal": r.signal,
        }
        for r in results
    ]
    return json.dumps(payload, ensure_ascii=False)


def prices_json(
    store, recipes: list[Recipe], now: str, item: str | None = None, hours: int = 24
) -> str:
    """Latest known price for each tracked item within the last `hours`."""
    watchlist = sorted(get_watchlist_item_ids(recipes))
    names = _item_names(recipes)
    now_dt = datetime.strptime(now, _TS_FMT)
    start = (now_dt - timedelta(hours=hours)).strftime(_TS_FMT)

    payload = []
    for item_id in watchlist:
        name = names.get(item_id, str(item_id))
        if item and item.lower() not in name.lower():
            continue
        history = store.get_price_history(item_id, start, now)
        if not history:
            continue
        latest = history[-1]
        payload.append(
            {
                "item_id": item_id,
                "item_name": name,
                "min_price": latest.min_price,
                "snapshots": len(history),
            }
        )
    return json.dumps(payload, ensure_ascii=False)


def recipes_json(recipes: list[Recipe]) -> str:
    """All loaded recipe definitions."""
    payload = [
        {
            "name": r.name,
            "output_item_id": r.output_item_id,
            "output_quantity": r.output_quantity,
            "reagents": [
                {"item_id": g.item_id, "name": g.name, "quantity": g.quantity}
                for g in r.reagents
            ],
        }
        for r in recipes
    ]
    return json.dumps(payload, ensure_ascii=False)
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_agent_tools.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: add service-backed agent tool functions"
```

---

### Task 6: Agent 基底類別與 function-calling 迴圈

**Files:**
- Create: `src/wow_ah/agent/base.py`
- Test: `tests/test_agent_base.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_agent_base.py`. 用 `FakeLLM` 腳本化回應，驗證工具被呼叫、結果回填、最終文字回傳、超輪報錯：

```python
import pytest

from wow_ah.agent.base import Agent, Tool
from wow_ah.exceptions.base import APIError
from wow_ah.schemas.agents import LLMResponse, ToolCall


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _echo_tool(received):
    def _run(text: str) -> str:
        received.append(text)
        return f"got:{text}"

    return Tool(
        name="echo",
        description="echo text",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        func=_run,
    )


def test_agent_executes_tool_then_returns_final_text():
    received = []
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "echo", {"text": "hi"})], finish_reason="tool_calls"),
        LLMResponse(content="done", tool_calls=[], finish_reason="stop"),
    ])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[_echo_tool(received)], llm=llm)

    answer = agent.run("question")

    assert answer == "done"
    assert received == ["hi"]
    assert llm.calls[0]["model"] == "gpt-4.1-nano"
    # tool result was fed back on the second call
    assert any(m.get("role") == "tool" and m.get("content") == "got:hi" for m in llm.calls[1]["messages"])


def test_agent_returns_immediately_when_no_tool_calls():
    llm = FakeLLM([LLMResponse(content="straight answer", tool_calls=[], finish_reason="stop")])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[], llm=llm)
    assert agent.run("q") == "straight answer"


def test_agent_raises_on_unknown_tool():
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "missing", {})], finish_reason="tool_calls"),
    ])
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[], llm=llm)
    with pytest.raises(APIError):
        agent.run("q")


def test_agent_raises_when_max_rounds_exceeded():
    # Always returns a tool call -> never terminates -> hits the cap
    tool_loop = [
        LLMResponse(content=None, tool_calls=[ToolCall(f"c{i}", "echo", {"text": "x"})], finish_reason="tool_calls")
        for i in range(20)
    ]
    llm = FakeLLM(tool_loop)
    agent = Agent(name="t", model="gpt-4.1-nano", system_prompt="sys", tools=[_echo_tool([])], llm=llm)
    with pytest.raises(APIError):
        agent.run("q")
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_agent_base.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.base'`）

- [ ] **Step 3: 實作 base.py**

Create `src/wow_ah/agent/base.py`:

```python
import json
from dataclasses import dataclass
from typing import Callable

from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import AgentErrorMessages
from wow_ah.protocols.llm import LLMProtocol

MAX_TOOL_ROUNDS = 8


@dataclass
class Tool:
    """A callable the model may invoke. `parameters` is a JSON schema."""
    name: str
    description: str
    parameters: dict
    func: Callable[..., str]


class Agent:
    """Runs an OpenAI function-calling loop with a fixed tool set."""

    def __init__(
        self,
        name: str,
        model: str,
        system_prompt: str,
        tools: list[Tool],
        llm: LLMProtocol,
    ) -> None:
        self.name = name
        self.model = model
        self._system_prompt = system_prompt
        self._tools = {t.name: t for t in tools}
        self._llm = llm

    def _tool_schemas(self) -> list[dict] | None:
        if not self._tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def run(self, user_input: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input},
        ]
        schemas = self._tool_schemas()

        for _ in range(MAX_TOOL_ROUNDS):
            resp = self._llm.complete(self.model, messages, schemas)
            if not resp.tool_calls:
                return resp.content or ""

            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )

            for tc in resp.tool_calls:
                tool = self._tools.get(tc.name)
                if tool is None:
                    raise APIError(
                        AgentErrorMessages.UNKNOWN_TOOL.format(agent=self.name, tool=tc.name)
                    )
                result = tool.func(**tc.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

        raise APIError(
            AgentErrorMessages.MAX_ROUNDS_EXCEEDED.format(agent=self.name, limit=MAX_TOOL_ROUNDS)
        )
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_agent_base.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/agent/base.py tests/test_agent_base.py
git commit -m "feat: add Agent function-calling loop with Tool abstraction"
```

---

### Task 7: 專家 agent 建構器

**Files:**
- Create: `src/wow_ah/agent/specialists.py`
- Test: `tests/test_specialists.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_specialists.py`. 驗證建構器產出正確 agent、工具齊全、且工具能透過 FakeLLM 走完一輪：

```python
from wow_ah.agent.specialists import build_recipe_agent, build_trend_agent, build_risk_agent
from wow_ah.schemas.agents import LLMResponse, ToolCall
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest=None):
        self._latest = latest or {}

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _recipe():
    return Recipe(name="Flask", output_item_id=100, output_quantity=1,
                  reagents=[Reagent(item_id=1, name="Herb", quantity=10)])


def test_recipe_agent_uses_given_model_and_has_spread_tool():
    store = FakeStore(latest={1: PriceSnapshot(1, "2026-06-14T12:00:00Z", 100),
                              100: PriceSnapshot(100, "2026-06-14T12:00:00Z", 5000)})
    llm = FakeLLM([
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "get_spreads", {})], finish_reason="tool_calls"),
        LLMResponse(content="配方分析完成", tool_calls=[], finish_reason="stop"),
    ])
    agent = build_recipe_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-4.1-nano")

    answer = agent.run("哪個配方最賺？")

    assert agent.name == "recipe_analyst"
    assert agent.model == "gpt-4.1-nano"
    assert answer == "配方分析完成"
    # the spread tool actually ran and fed JSON back
    assert any(m.get("role") == "tool" for m in llm.calls[1]["messages"])


def test_trend_and_risk_agents_build_with_model():
    store = FakeStore()
    llm = FakeLLM([LLMResponse(content="ok", tool_calls=[], finish_reason="stop")])
    trend = build_trend_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-5.4-nano",
                              now="2026-06-14T12:00:00Z")
    assert trend.name == "trend_analyst"
    assert trend.model == "gpt-5.4-nano"

    risk = build_risk_agent(llm=llm, store=store, recipes=[_recipe()], model="gpt-4.1-nano",
                            now="2026-06-14T12:00:00Z")
    assert risk.name == "risk_reviewer"
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_specialists.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.specialists'`）

- [ ] **Step 3: 實作 specialists.py**

Create `src/wow_ah/agent/specialists.py`:

```python
from wow_ah.agent.base import Agent, Tool
from wow_ah.agent.tools import prices_json, recipes_json, spreads_json, trends_json
from wow_ah.protocols.llm import LLMProtocol
from wow_ah.schemas.recipes import Recipe

_RECIPE_PROMPT = (
    "你是「配方利潤分析師」。用 get_spreads 取得各配方扣除拍賣場手續費後的淨利，"
    "必要時用 list_recipes 了解配方組成。以繁體中文點出最值得製造販售的配方與理由，"
    "金額以 copper 為單位。只依工具回傳的資料回答，不要編造價格。"
)
_TREND_PROMPT = (
    "你是「價格趨勢分析師」。用 get_trends 取得各物品的 BUY/SELL/HOLD 訊號，"
    "必要時用 get_prices 查最新價。以繁體中文說明現在適合買進或賣出哪些物品與理由。"
    "只依工具回傳的資料回答，不要編造價格。"
)
_RISK_PROMPT = (
    "你是「風險審查員」。針對其他分析師提出的交易建議，用 get_prices 檢查相關物品的"
    "資料筆數是否足夠、價格是否異常。以繁體中文指出建議中不可靠或證據不足之處；"
    "若無明顯風險，明確說明通過審查。"
)

_SPREADS_SCHEMA = {
    "type": "object",
    "properties": {"min_margin": {"type": "number", "description": "最低利潤率%，預設0"}},
}
_TRENDS_SCHEMA = {
    "type": "object",
    "properties": {"days": {"type": "integer", "description": "分析的歷史天數，預設7"}},
}
_PRICES_SCHEMA = {
    "type": "object",
    "properties": {
        "item": {"type": "string", "description": "以名稱子字串過濾，可省略"},
        "hours": {"type": "integer", "description": "回溯小時數，預設24"},
    },
}
_RECIPES_SCHEMA = {"type": "object", "properties": {}}


def _spreads_tool(store, recipes: list[Recipe]) -> Tool:
    return Tool(
        name="get_spreads",
        description="取得各配方扣手續費後的淨利列表（依利潤率排序）。",
        parameters=_SPREADS_SCHEMA,
        func=lambda min_margin=0.0: spreads_json(store, recipes, min_margin),
    )


def _recipes_tool(recipes: list[Recipe]) -> Tool:
    return Tool(
        name="list_recipes",
        description="列出所有已載入的配方定義與其材料。",
        parameters=_RECIPES_SCHEMA,
        func=lambda: recipes_json(recipes),
    )


def _trends_tool(store, recipes: list[Recipe], now: str) -> Tool:
    return Tool(
        name="get_trends",
        description="取得各物品的 BUY/SELL/HOLD 價格訊號。",
        parameters=_TRENDS_SCHEMA,
        func=lambda days=7: trends_json(store, recipes, now, days),
    )


def _prices_tool(store, recipes: list[Recipe], now: str) -> Tool:
    return Tool(
        name="get_prices",
        description="取得各追蹤物品的最新價格與資料筆數。",
        parameters=_PRICES_SCHEMA,
        func=lambda item=None, hours=24: prices_json(store, recipes, now, item, hours),
    )


def build_recipe_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str) -> Agent:
    return Agent(
        name="recipe_analyst",
        model=model,
        system_prompt=_RECIPE_PROMPT,
        tools=[_spreads_tool(store, recipes), _recipes_tool(recipes)],
        llm=llm,
    )


def build_trend_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str, now: str) -> Agent:
    return Agent(
        name="trend_analyst",
        model=model,
        system_prompt=_TREND_PROMPT,
        tools=[_trends_tool(store, recipes, now), _prices_tool(store, recipes, now)],
        llm=llm,
    )


def build_risk_agent(*, llm: LLMProtocol, store, recipes: list[Recipe], model: str, now: str) -> Agent:
    return Agent(
        name="risk_reviewer",
        model=model,
        system_prompt=_RISK_PROMPT,
        tools=[_prices_tool(store, recipes, now)],
        llm=llm,
    )
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_specialists.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/agent/specialists.py tests/test_specialists.py
git commit -m "feat: add recipe/trend/risk specialist agent builders"
```

---

### Task 8: Orchestrator 與 run_advisor 流程

**Files:**
- Create: `src/wow_ah/agent/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_orchestrator.py`. 驗證：新鮮度關卡擋下舊資料、新鮮時 orchestrator 把專家當工具呼叫、各 agent 使用正確模型：

```python
from wow_ah.agent.orchestrator import run_advisor, ADVISE_PROMPT
from wow_ah.core.config import Settings
from wow_ah.schemas.agents import LLMResponse, ToolCall


class FakeStore:
    def __init__(self, last):
        self._last = last

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids): return {}
    def get_last_fetch_timestamp(self): return self._last


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, model, messages, tools):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self._responses.pop(0)


def _settings():
    return Settings(_env_file=None, openai_default_model="gpt-4.1-nano",
                    wow_ah_orchestrator_model="gpt-5.4-nano")


def test_stale_data_short_circuits_before_llm():
    store = FakeStore(last=None)  # no data
    llm = FakeLLM([])  # must never be called
    out = run_advisor("哪個配方最賺？", llm=llm, store=store, recipes=[],
                      settings=_settings(), now="2026-06-14T12:00:00Z")
    assert "fetch" in out.lower()
    assert llm.calls == []


def test_orchestrator_consults_specialist_and_uses_models():
    store = FakeStore(last="2026-06-14T11:00:00Z")  # fresh
    llm = FakeLLM([
        # orchestrator decides to consult the recipe analyst
        LLMResponse(content=None, tool_calls=[ToolCall("c1", "consult_recipe_analyst", {"question": "哪個配方最賺"})], finish_reason="tool_calls"),
        # recipe analyst answers directly (no tool)
        LLMResponse(content="建議製造 Flask", tool_calls=[], finish_reason="stop"),
        # orchestrator synthesizes final answer
        LLMResponse(content="最終建議：製造 Flask", tool_calls=[], finish_reason="stop"),
    ])
    out = run_advisor("哪個配方最賺？", llm=llm, store=store, recipes=[],
                      settings=_settings(), now="2026-06-14T12:00:00Z")

    assert out == "最終建議：製造 Flask"
    # orchestrator's own calls use the orchestrator model
    assert llm.calls[0]["model"] == "gpt-5.4-nano"
    # the specialist call uses the recipe model (default here)
    assert llm.calls[1]["model"] == "gpt-4.1-nano"


def test_advise_prompt_is_nonempty():
    assert "建議" in ADVISE_PROMPT
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.orchestrator'`）

- [ ] **Step 3: 實作 orchestrator.py**

Create `src/wow_ah/agent/orchestrator.py`:

```python
from wow_ah.agent.base import Agent, Tool
from wow_ah.agent.freshness import check_freshness
from wow_ah.agent.specialists import (
    build_recipe_agent,
    build_risk_agent,
    build_trend_agent,
)
from wow_ah.core.config import Settings
from wow_ah.protocols.llm import LLMProtocol
from wow_ah.schemas.recipes import Recipe

_ORCHESTRATOR_PROMPT = (
    "你是 WoW 拍賣場套利顧問的主控者。依使用者問題，呼叫適合的專家工具："
    "consult_recipe_analyst（配方利潤）、consult_trend_analyst（買賣時機）、"
    "consult_risk_reviewer（檢查建議是否可靠）。先取得分析，再請風險審查員把關，"
    "最後以繁體中文彙整成清楚、可執行的建議。記住：暴雪 API 無法自動下單，"
    "你的建議僅供使用者手動操作參考。"
)

ADVISE_PROMPT = (
    "請主動分析目前拍賣場：找出最值得製造販售的配方，以及現在適合買進或賣出的物品，"
    "經風險審查後，產出一份依優先順序排列的繁體中文交易建議報告，並附上理由。"
)

_CONSULT_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "要交給該專家的問題"}},
    "required": ["question"],
}


def _consult_tool(name: str, description: str, specialist: Agent) -> Tool:
    return Tool(
        name=name,
        description=description,
        parameters=_CONSULT_SCHEMA,
        func=lambda question: specialist.run(question),
    )


def build_orchestrator(
    *, llm: LLMProtocol, store, recipes: list[Recipe], settings: Settings, now: str
) -> Agent:
    recipe_agent = build_recipe_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for("recipe")
    )
    trend_agent = build_trend_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for("trend"), now=now
    )
    risk_agent = build_risk_agent(
        llm=llm, store=store, recipes=recipes, model=settings.model_for("risk"), now=now
    )

    tools = [
        _consult_tool("consult_recipe_analyst", "請配方利潤分析師分析配方淨利。", recipe_agent),
        _consult_tool("consult_trend_analyst", "請價格趨勢分析師分析買賣時機。", trend_agent),
        _consult_tool("consult_risk_reviewer", "請風險審查員檢查建議是否可靠。", risk_agent),
    ]
    return Agent(
        name="orchestrator",
        model=settings.model_for("orchestrator"),
        system_prompt=_ORCHESTRATOR_PROMPT,
        tools=tools,
        llm=llm,
    )


def run_advisor(
    prompt: str,
    *,
    llm: LLMProtocol,
    store,
    recipes: list[Recipe],
    settings: Settings,
    now: str,
) -> str:
    """Run the freshness gate, then the orchestrated multi-agent flow."""
    freshness = check_freshness(store, now)
    if not freshness.is_fresh:
        return freshness.message

    orchestrator = build_orchestrator(
        llm=llm, store=store, recipes=recipes, settings=settings, now=now
    )
    return orchestrator.run(prompt)
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/agent/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator with freshness gate and run_advisor flow"
```

---

### Task 9: CLI 指令 ask / advise

**Files:**
- Modify: `src/wow_ah/cli.py`
- Test: `tests/test_cli_agent.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_cli_agent.py`. 用 Typer 的 `CliRunner`，並 monkeypatch `run_advisor` 與 store/設定，驗證 CLI 接線（不打網路）：

```python
from typer.testing import CliRunner

from wow_ah import cli
from wow_ah.core.config import Settings

runner = CliRunner()


def test_ask_errors_without_api_key(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key=""))
    result = runner.invoke(cli.app, ["ask", "哪個配方最賺？"])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output


def test_ask_prints_advisor_answer(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    monkeypatch.setattr(cli, "_get_store", lambda: object())
    monkeypatch.setattr(cli, "_get_recipes", lambda: [])
    monkeypatch.setattr(cli, "OpenAIChatAdapter", lambda *a, **k: object())
    monkeypatch.setattr(cli, "run_advisor", lambda prompt, **kw: "最終建議：製造 Flask")

    result = runner.invoke(cli.app, ["ask", "哪個配方最賺？"])
    assert result.exit_code == 0
    assert "最終建議：製造 Flask" in result.output


def test_advise_uses_advise_prompt(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    monkeypatch.setattr(cli, "_get_store", lambda: object())
    monkeypatch.setattr(cli, "_get_recipes", lambda: [])
    monkeypatch.setattr(cli, "OpenAIChatAdapter", lambda *a, **k: object())

    def _fake_run(prompt, **kw):
        captured["prompt"] = prompt
        return "報告"

    monkeypatch.setattr(cli, "run_advisor", _fake_run)
    result = runner.invoke(cli.app, ["advise"])
    assert result.exit_code == 0
    assert captured["prompt"] == cli.ADVISE_PROMPT
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_cli_agent.py -v`
Expected: FAIL（`AttributeError: module 'wow_ah.cli' has no attribute 'run_advisor'` 或 ask 指令不存在）

- [ ] **Step 3: 在 cli.py 加 import 與指令**

Add to the imports block of `src/wow_ah/cli.py` (after line 19, the existing service imports):

```python
from wow_ah.agent.llm import OpenAIChatAdapter
from wow_ah.agent.orchestrator import ADVISE_PROMPT, run_advisor
from wow_ah.exceptions.base import APIError
from wow_ah.exceptions.messages import AgentErrorMessages
```

Append these two commands to the end of `src/wow_ah/cli.py` (before the `recipes` sub-app section is fine; place after the `export` command):

```python
def _run_advisor_cli(prompt: str) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise APIError(AgentErrorMessages.MISSING_API_KEY)
    store = _get_store()
    recipes = _get_recipes()
    llm = OpenAIChatAdapter(settings.openai_api_key, settings.openai_base_url or None)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = run_advisor(prompt, llm=llm, store=store, recipes=recipes, settings=settings, now=now)
    typer.echo(answer)


@app.command()
@_handle_errors
def ask(question: str = typer.Argument(..., help="自然語言問題（繁體中文）")):
    """Ask the multi-agent advisor a natural-language question."""
    _run_advisor_cli(question)


@app.command()
@_handle_errors
def advise():
    """Generate a proactive multi-agent trading recommendation report."""
    _run_advisor_cli(ADVISE_PROMPT)
```

- [ ] **Step 4: 執行確認通過**

Run: `pytest tests/test_cli_agent.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add src/wow_ah/cli.py tests/test_cli_agent.py
git commit -m "feat: add 'ask' and 'advise' CLI commands"
```

---

### Task 10: MCP server 與 mcp 指令

**Files:**
- Create: `src/wow_ah/agent/mcp_server.py`
- Modify: `src/wow_ah/cli.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: 寫失敗測試**

Create `tests/test_mcp_server.py`. 不啟動伺服器，只驗證 server 建得起來、且工具邏輯（共用函式）以 FakeStore 回傳正確 JSON：

```python
import json

from wow_ah.agent.mcp_server import build_server
from wow_ah.agent.tools import spreads_json
from wow_ah.schemas.prices import PriceSnapshot
from wow_ah.schemas.recipes import Recipe, Reagent


class FakeStore:
    def __init__(self, latest):
        self._latest = latest

    def save_snapshots(self, snapshots): ...
    def get_price_history(self, item_id, start, end): return []
    def get_latest_prices(self, item_ids):
        return {i: self._latest[i] for i in item_ids if i in self._latest}
    def get_last_fetch_timestamp(self): return None


def _recipe():
    return Recipe(name="Flask", output_item_id=100, output_quantity=1,
                  reagents=[Reagent(item_id=1, name="Herb", quantity=10)])


def test_build_server_returns_named_fastmcp():
    server = build_server(store=FakeStore({}), recipes=[_recipe()], now="2026-06-14T12:00:00Z")
    assert server.name == "wow-ah"


def test_shared_tool_logic_used_by_mcp():
    store = FakeStore({1: PriceSnapshot(1, "2026-06-14T12:00:00Z", 100),
                       100: PriceSnapshot(100, "2026-06-14T12:00:00Z", 5000)})
    out = json.loads(spreads_json(store, [_recipe()], 0.0))
    assert out[0]["recipe_name"] == "Flask"
```

- [ ] **Step 2: 執行確認失敗**

Run: `pytest tests/test_mcp_server.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'wow_ah.agent.mcp_server'`）

- [ ] **Step 3: 實作 mcp_server.py**

Create `src/wow_ah/agent/mcp_server.py`:

```python
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from wow_ah.agent.tools import prices_json, recipes_json, spreads_json, trends_json
from wow_ah.core.config import get_settings
from wow_ah.adapters.sqlite_adapter import SQLiteAdapter
from wow_ah.recipes.loader import load_all_recipes
from wow_ah.schemas.recipes import Recipe


def build_server(*, store, recipes: list[Recipe], now: str) -> FastMCP:
    """Build a FastMCP server exposing the read-only analysis tools."""
    mcp = FastMCP("wow-ah")

    @mcp.tool()
    def get_spreads(min_margin: float = 0.0) -> str:
        """各配方扣手續費後的淨利列表（JSON）。"""
        return spreads_json(store, recipes, min_margin)

    @mcp.tool()
    def get_trends(days: int = 7) -> str:
        """各物品的 BUY/SELL/HOLD 價格訊號（JSON）。"""
        return trends_json(store, recipes, now, days)

    @mcp.tool()
    def get_prices(item: str | None = None, hours: int = 24) -> str:
        """各追蹤物品的最新價格（JSON）。"""
        return prices_json(store, recipes, now, item, hours)

    @mcp.tool()
    def list_recipes() -> str:
        """所有已載入的配方定義（JSON）。"""
        return recipes_json(recipes)

    return mcp


def run_server() -> None:
    settings = get_settings()
    store = SQLiteAdapter(settings.db_path)
    recipes = load_all_recipes()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_server(store=store, recipes=recipes, now=now).run()
```

- [ ] **Step 4: 加 mcp CLI 指令**

Append to the end of `src/wow_ah/cli.py`:

```python
@app.command()
@_handle_errors
def mcp():
    """Start the MCP server exposing wow-ah analysis tools."""
    from wow_ah.agent.mcp_server import run_server
    run_server()
```

- [ ] **Step 5: 執行確認通過**

Run: `pytest tests/test_mcp_server.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 跑全套測試**

Run: `conda run -n wow-ah pytest -q`
Expected: PASS（原 61 + 新增測試全綠）

- [ ] **Step 7: Commit**

```bash
git add src/wow_ah/agent/mcp_server.py src/wow_ah/cli.py tests/test_mcp_server.py
git commit -m "feat: add FastMCP server and 'mcp' CLI command"
```

---

### Task 11: 文件與收尾

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md**

在 `CLAUDE.md` 的 Architecture 表格新增一列（在 CLI 列之上）：

```markdown
| Agent | [src/wow_ah/agent/](src/wow_ah/agent/) | OpenAI 多 agent 協作（orchestrator + 配方/趨勢/風險專家）、新鮮度關卡、CLI/MCP 入口 | services, adapters, recipes, schemas, core, protocols, openai/mcp SDK |
```

在 Commands 區塊新增：

```markdown
uv run wow-ah ask "<問題>"          # 多 agent 問答（需 OPENAI_API_KEY）
uv run wow-ah advise               # 主動產生交易建議報告
uv run wow-ah mcp                  # 啟動 MCP server 暴露分析工具
```

在 `.env` 說明段補上：`OPENAI_API_KEY` 為 `ask` / `advise` 所需；各 agent 模型可用 `WOW_AH_*_MODEL` 覆寫，預設 `gpt-4.1-nano`。

- [ ] **Step 2: 跑全套測試確認無回歸**

Run: `conda run -n wow-ah pytest -q`
Expected: PASS（全綠）

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document agent layer, CLI commands, and OpenAI env vars"
```

---

## Self-Review

**Spec coverage：**
- Provider/SDK（openai）→ Task 1、3 ✅
- 每 agent 可調模型、預設 gpt-4.1-nano → Task 1（`model_for`）、Task 7/8（套用）✅
- `LLMProtocol` + `FakeLLM` 測試零網路 → Task 3、6、7、8 ✅
- 工具唯讀本地 SQLite、不打暴雪、不自動 fetch → Task 5（tools 只讀 store）✅
- 確定性新鮮度關卡（6h）→ Task 4、8 ✅
- 5 agent（orchestrator + 配方/趨勢/風險 + 新鮮度 gate）→ Task 7、8 ✅
- `ask` / `advise` / `mcp` 入口 → Task 9、10 ✅
- 錯誤處理（AgentErrorMessages + `_handle_errors`）→ Task 2、9 ✅
- 繁體中文輸出 → 各 system prompt ✅
- YAGNI 排除（排程/下單/自動 fetch/Agents SDK）→ 計劃未納入 ✅

**型別一致性：** `LLMResponse(content, tool_calls, finish_reason)`、`ToolCall(id, name, arguments)`、`Tool(name, description, parameters, func)`、`Agent(name, model, system_prompt, tools, llm).run()`、`check_freshness(store, now)→FreshnessResult`、`settings.model_for(key)`、tools 共用函式 `spreads_json/trends_json/prices_json/recipes_json` — 跨 Task 一致 ✅

**Placeholder 掃描：** 無 TBD/TODO，每步皆含實際程式碼與指令 ✅
