## Why

Pipeline 目前分割偵測率 41%、分類準確度 14%，要改善必須有高品質 ground truth 做量化基準。現有 ground truth 建立方式是手寫 JSON 或用 OpenCV 桌面 GUI，效率低且只能校對 pipeline 已偵測到的房間。**pipeline 漏掉的房間無法補標，意味著 ground truth 的完整度受限於 pipeline 本身的能力**——這讓評估失去意義。

需要一個獨立於 pipeline 的完整標註工具，讓使用者能在瀏覽器中從零建立 ground truth：畫新 bbox、刪除多餘的、調整邊界、修改分類。這是後續所有 pipeline 改善的基石。

## What Changes

- 將標註編輯 Tab 從「校對分類」升級為「完整 Ground Truth 編輯器」
  - 新增：在圖上拖曳畫新 bbox（pipeline 漏掉的房間）
  - 新增：拖曳調整既有 bbox 邊界
  - 新增：刪除多餘/碎片 bbox
  - 保留：點選修改分類類型
- 支援「不跑 pipeline，直接載圖標註」模式——標註獨立於 pipeline
- 新增評估儀表板 Tab，比對 pipeline vs ground truth
- 替換互動元件：從 `streamlit-image-coordinates`（只能點）改為 `streamlit-image-annotation`（原生 bbox 繪製 + label）

## Capabilities

### New Capabilities
- `annotation-editor`: 瀏覽器內的完整 Ground Truth 編輯器（畫 bbox、調整邊界、刪除、改分類），獨立於 pipeline
- `evaluation-dashboard`: 評估指標儀表板（pipeline vs ground truth 的分類準確度、公共召回率、逐房間比較）

### Modified Capabilities

（無既有 spec 需修改）

## Impact

- **替換依賴**: `streamlit-image-coordinates` → `streamlit-image-annotation`（`requirements.txt`）
- **重寫檔案**: `src/annotation_tab.py`（從點選校對改為完整標註編輯器）
- **修改檔案**: `app.py`（整合新 Tab 結構）
- **新增檔案**: `src/evaluation_tab.py`
- **資料格式**: 沿用 `ground_truth.json` 格式 `[{bbox: [x,y,w,h], type, is_public, note}]`
- **不影響**: CLI pipeline、`annotation_editor.py`（OpenCV GUI 保留但不再是主要工具）
