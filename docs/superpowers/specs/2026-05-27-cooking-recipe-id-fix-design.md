# Cooking Recipe ID Fix — Design Spec

## Context

[src/wow_ah/recipes/data/cooking.json](../../../src/wow_ah/recipes/data/cooking.json) 目前 8 個配方的 `item_id` 全部來自 [recipe/food.txt](../../../recipe/food.txt) 那份 `MidnightCookingDatabase Version 12.0` 規劃 XML 的虛構編號（`211001`、`213001`、`300001` 等），**不是 Blizzard 真實 item ID**。

實際影響：`wow-ah fetch` 過濾 watchlist 時對得起來，但 Blizzard commodities API 不回傳這些 item（因為它們不存在），結果是 cooking 相關的 snapshot 永遠是 0 筆，spreads / trends 對料理配方全部靜默失效。

驗證證據（2026-05-27 DB 查詢）：
```
SELECT DISTINCT item_id FROM price_snapshots;
210796, 210799, 210800, 210802, 210930, 212283   ← 全部來自 alchemy.json
```

## Goal

把 cooking.json 重建為**完整的 Midnight (12.0) cooking 配方資料庫，使用 Wowhead 上的真實 item ID**，讓 `wow-ah fetch` 對 cooking item 也能抓回有效資料。

## Out of Scope

明確排除，避免 scope creep：

- 不動 [alchemy.json](../../../src/wow_ah/recipes/data/alchemy.json)（現有 ID 是真實的）
- 不改 Recipe / Reagent schema（不加 `name_zh` / `name_en` 拆分欄位）
- 不加 `wow-ah recipes add` CLI 子指令
- 不寫入 SQLite 的 `recipes` / `recipe_reagents` 表（仍是 dead schema，未來別的工作再處理）
- 不追蹤品質階層（q1/q2/q3 同配方）
- 不做執行階段的 LLM 呼叫 — 純粹 Claude Code 在 brainstorming session 內用 WebFetch 完成

## Decisions Locked

腦力激盪過程中已敲定的選項：

| 決策 | 選擇 |
|---|---|
| Midnight 上線狀態 | **A**：已上線（12.0.5），Wowhead 有真實 ID |
| 涵蓋範圍 | **B**：完整 Midnight cooking（非僅修現有 8 筆） |
| `name` 欄位格式 | **B**：`中文 (English)` 混合（與現有 cooking.json 一致；alchemy.json 不動） |
| Hearty 變體 | **A**：全包（與 base 並列為獨立配方項） |

## Schema（不變）

繼續沿用現有結構：

```json
{
  "recipes": [
    {
      "name": "銀月大遊行 (Silvermoon Parade)",
      "output_item_id": 255845,
      "output_quantity": 1,
      "reagents": [
        {"item_id": 242639, "name": "大塊豬肉 (Practically Pork)", "quantity": 20}
      ]
    }
  ]
}
```

對應 [src/wow_ah/schemas/recipes.py](../../../src/wow_ah/schemas/recipes.py) 的 `Recipe` / `Reagent` dataclass，零改動。

## Workflow

```
1. DISCOVER
   WebFetch  https://www.wowhead.com/guide/midnight/professions/cooking-overview-trainer-leveling-recipes-tools
   ─→ 解析出 [(recipe_name_zh, recipe_name_en, recipe_item_id)] 完整清單
      （包含 base 與 Hearty 變體）

2. DETAIL
   for each recipe_item_id:
     WebFetch  https://www.wowhead.com/item={id}
     ─→ 抽出 reagents [(name_zh, name_en, item_id, quantity)] 與 output_quantity
   失敗的 recipe 暫存到 skip-list、不中斷流程

3. COMPOSE
   組合成 Recipe / Reagent 結構
   name 欄位格式統一為 "{中文} ({English})"

4. WRITE
   覆寫 src/wow_ah/recipes/data/cooking.json
   保持 JSON 排序（依 output_item_id 升冪），方便 diff 比對

5. VERIFY
   uv run wow-ah recipes list   ─→ 人眼掃一遍，確認名稱合理
   uv run wow-ah fetch          ─→ 跑一次（如果同小時已抓過，要繞過 throttle）
                                    觀察 snapshot 數是否大幅增加
   SELECT DISTINCT item_id FROM price_snapshots
     WHERE item_id NOT IN (alchemy_watchlist);
   ─→ 確認有 cooking item 真的被抓到（即使只是 reagents）
```

Throttle bypass：因為 5 步驟需要立即驗證，但 [fetch_service.py:65-72](../../../src/wow_ah/services/fetch_service.py#L65-L72) 同小時內會 skip。可用 `service.fetch(skip_if_same_hour=False)` 呼叫，或者刪掉當前小時的 snapshot 強迫重抓。CLI 目前沒暴露這個參數 — 一次性可直接用 `python -c` 呼叫，不必為了 verify 改 production 程式碼。

## Edge Cases

| 情境 | 處理方式 |
|---|---|
| Wowhead 頁面沒有中文名（只有英文） | name 改成純英文：`"Practically Pork"` |
| Reagent 是「可替代材料組」（料理較少見） | 取第一個列出的；輸出時 log 提醒讓人複查 |
| 個別 WebFetch 失敗 / Wowhead 結構變動 | 該 recipe 略過、記入 skip-list、最後一起報告 |
| Recipe 跟 reagent 共用同名（例：同名 base / Hearty） | 用 item ID 區分；name 加註標籤確保人類可讀 |
| `fetch` 驗證後仍有 cooking item 為 0 snapshots | 列出該 item ID，可能是 ID 抓錯或該 item 暫時無人掛賣 — 後者是業務常態（見 alchemy 成品案例） |

## Verification Criteria

成功定義：

1. cooking.json 內**至少 90% 的 recipe** 含有真實 Wowhead item ID（非 `300xxx` / `211xxx` 等規劃編號）
2. `wow-ah recipes list` 人工掃過、名稱與 ID 對得起來
3. 執行一次 `fetch` 後，DB 中 cooking item 的 distinct count > 0
   - 注意：reagents 比 outputs 更可能有資料（參考 alchemy 觀察結果）

## Artifacts

- 一份 spec doc（本檔）
- 重寫後的 [cooking.json](../../../src/wow_ah/recipes/data/cooking.json)
- 一次 git commit
- skip-list 報告（如有）

## Future Considerations（不在本次範圍）

- 把這套方法封裝成 `wow-ah recipes sync --profession cooking` CLI 指令，下個 patch 自動更新
- alchemy.json 也對齊驗證（目前手寫 ID，未來新配方時可重用同流程）
- 加品質階層追蹤 — 需要 schema 改動
- 把 cooking.json 的 `name` 欄位也統一為 `alchemy.json` 的純英文風格（需要 alchemy / cooking 同步決策）
