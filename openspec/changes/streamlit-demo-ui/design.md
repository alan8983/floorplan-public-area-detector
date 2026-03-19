## Context

目前 pipeline (`src/pipeline.py`) 是純 CLI 工具，`run_pipeline()` 直接 print 到 stdout 並用 `cv2.imwrite()` 存檔。沒有結構化回傳值，無法被 UI 程式消費。

現有模組：
- `preprocessing.py` → `load_and_binarize()`, `image_stats()`
- `wall_detection.py` → `detect_walls()`, `close_wall_gaps()`
- `segmentation.py` → `segment_rooms()`
- `ocr_classify.py` → `ocr_extract()`, `match_keywords()`, `classify_rooms()`
- `eraser.py` → `erase_private_areas()`
- `visualize.py` → `draw_classification()`, `draw_zones()`

依賴：`opencv-python-headless`, `numpy`, `Pillow`, `pytesseract`

## Goals / Non-Goals

**Goals:**
- 提供簡潔的 Web UI，支援上傳圖檔 → 執行 pipeline → 檢視所有階段輸出
- 讓開發者與利害關係人能快速 demo 與比較結果
- 不破壞既有 CLI 介面

**Non-Goals:**
- 不做 ground truth 標註功能（未來再加）
- 不做使用者帳號 / 權限管理
- 不做 PDF 上傳支援（目前 pipeline 只吃圖片）
- 不做部署優化（Streamlit Cloud 部署不在此範圍）

## Decisions

### D1: Pipeline 回傳重構 — 新增 `run_pipeline_ui()` wrapper

**選擇**: 新增一個 `run_pipeline_ui()` 函式包裝既有邏輯，回傳結構化 dict，不改動原 `run_pipeline()`。

**替代方案**: 直接修改 `run_pipeline()` 回傳值 → 會影響 CLI 行為，風險較高。

**回傳結構**:
```python
{
    "original": np.ndarray,        # 原圖
    "walls_thick": np.ndarray,     # 厚牆 mask
    "walls_closed": np.ndarray,    # gap-closed walls
    "classification": np.ndarray,  # 分類 overlay
    "zones": np.ndarray,           # 公私區 overlay
    "erased": np.ndarray,          # 擦除結果
    "rooms": list[dict],           # room 資料
    "metrics": {                   # 品質指標
        "room_count": int,
        "coverage": float,
        "avg_solidity": float,
        "largest_rel_area": float,
        "n_public": int,
        "n_private": int,
        "elapsed": float,
    }
}
```

### D2: UI 佈局 — Sidebar 控制 + 主區域展示

**選擇**: Streamlit sidebar 放輸入控制，主區域用 tabs 展示各階段輸出。

**佈局**:
```
┌──────────┬──────────────────────────────────┐
│ Sidebar  │  Main Area                       │
│          │                                  │
│ 📂 上傳   │  [原圖] [分類] [Zones] [擦除] [Debug]│
│ 📁 範例   │  ┌──────────────────────────┐    │
│ ☑ OCR    │  │                          │    │
│          │  │     當前 tab 的圖片        │    │
│ [Run]    │  │                          │    │
│          │  └──────────────────────────┘    │
│ ── 指標 ──│                                  │
│ Rooms: 36│  📊 Room Details Table            │
│ Cover:70%│  ┌────┬──────┬──────┬────────┐   │
│ Public:12│  │ #  │ type │ area │ reason │   │
│          │  └────┴──────┴──────┴────────┘   │
└──────────┴──────────────────────────────────┘
```

### D3: 圖片展示 — Tabs 切換（非並排）

**選擇**: 使用 `st.tabs()` 切換各階段輸出。

**替代方案**: 並排 `st.columns()` — 但平面圖解析度高（3000+ px），並排會太小看不清。Tabs 讓每張圖佔滿寬度。

### D4: 檔案結構

**選擇**: 單一 `app.py` 於專案根目錄 + `src/pipeline_ui.py` 包裝函式。

```
project/
├── app.py                  # Streamlit entry point（薄層，只管 UI）
├── src/
│   ├── pipeline.py         # 既有 CLI（不動）
│   ├── pipeline_ui.py      # 新增：UI 用 wrapper
│   └── ...
└── requirements.txt        # 加入 streamlit
```

### D5: 圖片格式轉換

OpenCV 用 BGR，Streamlit `st.image()` 吃 RGB。在 `pipeline_ui.py` 回傳時統一轉為 RGB，避免 app.py 處處 `cv2.cvtColor()`。

## Risks / Trade-offs

- **[大圖處理慢]** → 平面圖 3000+ px，pipeline 跑一次約 3-10 秒。用 `st.spinner()` 顯示進度，pipeline 結果用 `st.cache_data` 快取。
- **[Tesseract 未安裝]** → OCR 模式會失敗。UI 上顯示友善錯誤訊息，OCR toggle 預設關閉。
- **[記憶體]** → 大圖 * 多張中間產物可能吃記憶體。Streamlit 預設單 worker 足夠 demo 用途。
