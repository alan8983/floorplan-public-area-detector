## 0. 前置準備

- [x] 0.1 同步本地 main：`git pull origin main`，確保 PR#2-4 的 `app.py`、`pipeline_ui.py`、`auto_annotate.py`、`evaluate.py` 等檔案存在
- [x] 0.2 安裝新依賴：`pip install streamlit-image-annotation`，替換 `requirements.txt` 中的 `streamlit-image-coordinates`
- [x] 0.3 驗證現有 Streamlit UI 可啟動：`streamlit run app.py`，確認 Tab1 辨識結果正常運作

## 1. 標註編輯 Tab — 完整 GT 編輯器

- [x] 1.1 重寫 `src/annotation_tab.py` 模組：定義 `render_annotation_tab()` 函數，使用 `streamlit-image-annotation` 的 `detection()` 元件
- [x] 1.2 實作 detection 元件整合：以原圖為背景，`label_list` 為 6 種分類，支援畫新 bbox + 拖曳調整 + 刪除
- [x] 1.3 實作標註來源切換：工具列按鈕「空白標註」/「從 Pipeline 載入」/「載入既存 GT」，設定 detection() 的 bboxes/labels 參數
- [x] 1.4 實作 pipeline → annotation 轉換：將 pipeline_result 的 rooms[] 轉為 detection() 接受的 bboxes + labels 格式
- [x] 1.5 實作 detection 回傳 → session_state 同步：detection() 回傳的 `[{bbox, label_id, label}]` 轉為 `annotations[]` 格式，自動推導 `is_public`

## 2. 標註編輯 Tab — 儲存與載入

- [x] 2.1 實作「儲存 Ground Truth」按鈕：將 `session_state.annotations` 寫入 `samples/<name>/ground_truth.json`，格式 `[{bbox, type, is_public, note}]`
- [x] 2.2 實作自動載入：選擇圖片時，檢查是否有既存 `ground_truth.json`，有則自動載入
- [x] 2.3 實作「自動標註」按鈕：呼叫 pipeline 邏輯產出 draft annotations，載入 detection 元件
- [x] 2.4 實作「未儲存修改」提示：`session_state.modified` flag，有修改時顯示警告

## 3. 評估儀表板 Tab

- [x] 3.1 建立 `src/evaluation_tab.py` 模組：定義 `render_evaluation_tab()` 函數
- [x] 3.2 實作指標卡片：呼叫 `evaluate.py` 比對邏輯，以 `st.metric` 顯示分類準確度、公共/私有準確度、公共召回率
- [x] 3.3 實作逐房間比較表：`st.dataframe` 顯示 pipeline vs GT，不一致列以紅色標示
- [x] 3.4 處理無 GT 狀態：顯示引導訊息到標註編輯 Tab

## 4. 整合與完善

- [x] 4.1 修改 `app.py`：整合 3 個 Tab（辨識結果 / 標註編輯 / 評估），確保 session_state 跨 Tab 保持
- [x] 4.2 確保大圖（3000+px）在 detection 元件中正常顯示和操作
- [x] 4.3 端到端測試：上傳 sample1 → 載入既存 GT → 修改標註 → 儲存 → 切到評估 → 確認指標
- [x] 4.4 更新 `CLAUDE.md` 反映新增的 Web 標註功能
