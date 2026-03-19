## Why

目前 pipeline 只有 CLI 介面，每次執行後要手動開啟 output/ 下的 PNG 比較結果。調參、debug、demo 給利害關係人看都非常不方便。需要一個 Web UI 讓使用者能即時上傳平面圖、執行辨識、並排比較各階段輸出，加速開發迭代與對外展示。

## What Changes

- 新增 Streamlit Web 應用作為 pipeline 的互動式前端
- 支援圖檔上傳（JPG/PNG）與 samples/ 預設圖檔選擇
- 即時執行 pipeline 並顯示各階段產出（牆體、分割、分類、zones、擦除）
- 以並排 / tabs 方式比較原圖與各階段輸出
- 顯示 room 分類結果表格（type、area、aspect ratio、reason）
- 顯示 pipeline 品質指標（coverage、room count、solidity）
- 提供 OCR 開關等基本參數控制

## Capabilities

### New Capabilities
- `streamlit-app`: Streamlit Web UI 應用，包含圖檔上傳、pipeline 執行、結果展示、參數控制

### Modified Capabilities
（無既有 spec 需變更）

## Impact

- **新增依賴**: `streamlit` 加入 requirements.txt
- **程式碼**: 新增 `app.py`（或 `streamlit_app.py`）於專案根目錄
- **既有程式碼**: `src/pipeline.py` 的 `run_pipeline()` 需重構回傳結構化資料（目前只 print + cv2.imwrite，無法被 UI 消費）
- **啟動方式**: `streamlit run app.py`
