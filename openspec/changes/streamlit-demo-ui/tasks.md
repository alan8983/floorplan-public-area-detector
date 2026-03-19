## 1. Pipeline UI Wrapper

- [x] 1.1 新增 `src/pipeline_ui.py`，實作 `run_pipeline_ui(image_bytes, use_ocr)` 回傳結構化 dict（original, walls_thick, walls_closed, classification, zones, erased, rooms, metrics）
- [x] 1.2 所有回傳圖片統一轉為 RGB（OpenCV BGR → RGB），灰階 mask 轉為 3-channel
- [x] 1.3 處理例外情況：包裝 try/except，失敗時回傳錯誤訊息而非拋出例外

## 2. Streamlit App 主體

- [x] 2.1 新增 `app.py`，建立基本 Streamlit 頁面結構（page title, sidebar layout）
- [x] 2.2 實作 sidebar：file uploader（JPG/PNG）+ samples/ dropdown 選擇 + OCR checkbox + Run 按鈕
- [x] 2.3 實作主區域 tabs：原圖、分類、公私區、擦除、Debug（牆體/walls_closed）
- [x] 2.4 實作 room 分類結果表格（DataFrame 顯示：編號、類型、面積比、長寬比、位置、原因、公共標記）
- [x] 2.5 實作 sidebar 品質指標摘要（room count, coverage, public/private count, elapsed time）
- [x] 2.6 加入 `st.spinner()` 顯示處理進度 + 低覆蓋率 `st.warning()`

## 3. 整合與收尾

- [x] 3.1 `requirements.txt` 加入 `streamlit>=1.30`
- [x] 3.2 確認 `streamlit run app.py` 可正常啟動並跑完完整流程
- [x] 3.3 UI 美化：自訂頁面標題/icon、sidebar 分區標題、表格樣式（公共區域 highlight）
