## Context

標註工具需要從「校對 pipeline 輸出」升級為「獨立的完整 Ground Truth 編輯器」。使用者可以：
1. 不依賴 pipeline，直接在原圖上畫 bbox 標註房間
2. 也可以先跑 pipeline 產出 draft，再人工校對（增刪改）
3. 儲存為 ground truth JSON，供 evaluate.py 量化比對

現有 ground truth 格式：`[{bbox: [x,y,w,h], type: str, is_public: bool, note: str}]`

## Goals / Non-Goals

**Goals:**
- 在 Streamlit 瀏覽器中完成完整的 bbox 標註：新增、刪除、調整邊界、修改分類
- 標註獨立於 pipeline——可以直接載圖標註，不需要先跑 pipeline
- 支援從 pipeline 結果或既存 ground truth JSON 載入初始標註
- 評估 Tab 顯示 pipeline vs ground truth 的量化指標

**Non-Goals:**
- 不做多邊形/語義分割標註（bbox 足夠用於 room-level 評估）
- 不做多人協作標註
- 不做 ML 訓練整合（保留 `gt_to_yolo.py` 做離線轉換）

## Decisions

### D1: 互動元件 — `streamlit-image-annotation` detection 模式

**選項比較：**

| 方案 | 畫新 bbox | 調整邊界 | 刪除 | Label | 缺點 |
|------|:---------:|:--------:|:----:|:-----:|------|
| `streamlit-image-coordinates` | ❌ | ❌ | ❌ | ❌ | 只能點擊取座標 |
| `streamlit-drawable-canvas` | ✅ | ✅ | ✅ | ❌ | 已 archived (2025-03)，fabric.js 太重，label 需自建 |
| `streamlit-image-annotation` | ✅ | ✅ | ✅ | ✅ | 元件介面較簡單，但功能完整 |
| 自建 Streamlit component | ✅ | ✅ | ✅ | ✅ | 開發量大，不值得 |

**決定**：使用 `streamlit-image-annotation` 的 `detection()` 函數。

理由：
- 原生支援 bbox 繪製 + label 指定，回傳 `[{bbox: [x,y,w,h], label_id, label}]`
- 格式與我們的 ground truth JSON 幾乎一致
- 支援預載入既有 bbox（從 pipeline 或 JSON 載入）
- 輕量、專注於標註用途

### D2: 兩種工作模式

```
  模式 A：從零標註                  模式 B：Pipeline 輔助標註
  ═══════════════════              ═══════════════════════════

  1. 選擇/上傳圖片                  1. 選擇/上傳圖片
  2. 進入標註編輯 Tab                2. 在辨識結果 Tab 跑 pipeline
  3. 直接在原圖上畫 bbox             3. 切到標註編輯 Tab
  4. 為每個 bbox 選 label            4. 看到 pipeline 產出的 bbox（可編輯）
  5. 儲存 ground truth               5. 增刪改 → 儲存 ground truth
```

兩種模式共用同一個 UI，差別只在初始標註來源：
- 模式 A：`bboxes=[]`（空白開始）
- 模式 B：`bboxes=pipeline_rooms`（預載）
- 也可以載入既存 `ground_truth.json`

### D3: 頁面結構

```
app.py
├── Tab 1: 辨識結果（現有功能，保留）
│   └── pipeline 跑完後結果存 session_state
├── Tab 2: 標註編輯（重寫）
│   ├── 上方工具列：[自動標註] [載入 GT] [儲存 GT] [⚠️ 未儲存]
│   ├── 主區域：streamlit-image-annotation detection 元件
│   │   └── 原圖為背景 + bbox overlay（可畫新、拖曳調整、點選）
│   └── 側欄/下方：選中 bbox 的詳細資訊 + 類型修改
└── Tab 3: 評估儀表板（新）
    ├── 指標卡片（準確度、公共召回率）
    └── 逐房間比較表
```

### D4: 資料流

```
  ┌──────────────────┐     ┌──────────────────────┐     ┌────────────┐
  │  資料來源          │     │  session_state        │     │  輸出       │
  │                    │     │  annotations[]         │     │            │
  │  A) 空白           │──►  │                        │──►  │ GT JSON    │
  │  B) pipeline rooms │──►  │  ┌──────────────────┐ │     │ file       │
  │  C) 既存 GT JSON   │──►  │  │ detection() 元件  │ │     └────────────┘
  │                    │     │  │ 雙向同步           │ │            │
  └──────────────────┘     │  └──────────────────┘ │     ┌────────┴───┐
                             │                        │     │ evaluate.py│
                             └──────────────────────┘     └────────────┘
```

`detection()` 元件每次互動回傳最新的 bbox 列表，直接寫回 `session_state.annotations`。

### D5: Label 體系

`detection()` 需要 `label_list` 參數。定義：

```python
LABEL_LIST = [
    "stairwell",     # 樓梯間
    "elevator",      # 電梯
    "corridor",      # 走廊
    "lobby",         # 梯廳/門廳
    "mechanical",    # 機電空間
    "private",       # 私有空間（統稱）
]
PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}
```

`is_public` 自動從 type 推導，不需要使用者手動設定。

### D6: 座標系統

`streamlit-image-annotation` 的 `detection()` 回傳原始圖片座標（非顯示座標），即使圖片在瀏覽器中被縮放。`height`/`width` 參數控制顯示尺寸。

大圖（3000x3600px）策略：
- 顯示尺寸設為寬度 800px，等比縮放
- 元件內部自動處理座標轉換
- 儲存到 JSON 的 bbox 為原始圖片座標

### D7: 檔案結構

```
src/
├── annotation_tab.py    ← 重寫：完整 GT 編輯器
├── evaluation_tab.py    ← 新增：評估儀表板
├── evaluate.py          ← 現有，不改
├── auto_annotate.py     ← 現有，標註 Tab 的「自動標註」呼叫其邏輯
└── pipeline_ui.py       ← 現有，Tab1 使用
app.py                   ← 修改：整合 3 個 Tab
requirements.txt         ← 修改：加 streamlit-image-annotation
```

### D8: session_state 設計

```python
st.session_state:
  image_path: str              # 當前選擇的圖片路徑
  original_image: np.ndarray   # 原圖（BGR）
  pipeline_result: dict | None # pipeline 執行結果（Tab1 跑完快取）
  annotations: list[dict]      # 當前標註 [{bbox, type, is_public, note}]
  modified: bool               # 有未儲存修改
```

## Risks / Trade-offs

- **[風險] `streamlit-image-annotation` 的 bbox 編輯體驗** — 需實測大圖的流暢度和座標精度。→ 緩解：先用 sample1 實測，不行再換 `streamlit-drawable-canvas-fix`（maintained fork）
- **[風險] Streamlit rerun 機制** — 每次互動 rerun script，需確保 annotations 不因 rerun 遺失。→ 緩解：所有狀態存 `session_state`，detection() 的回傳值即時同步
- **[取捨] 不做多邊形標註** — bbox 無法精確描述不規則房間形狀。→ 可接受：room-level 評估用 bbox IoU 已足夠，後續需要時可升級
