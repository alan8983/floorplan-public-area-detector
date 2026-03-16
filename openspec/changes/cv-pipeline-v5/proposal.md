## Why

目前的 CV pipeline（v3）有三個根本問題阻礙產出品質：

1. **沒有量化評估**：每次參數調整都靠「開 PNG 用眼睛看」，無法客觀衡量改善或退步
2. **分割準確度不足（~70%）**：`close_wall_gaps()` 用固定 25px kernel，但實際門寬 80-90px，導致房間合併；錯誤向下游連鎖，分類和擦除都受影響
3. **分類規則位置相依**：幾何規則硬編碼 `rx < 0.42 = 樓梯間`，只對一張樣本有效，換一張圖就失敗

經過探索，我們確認：ML 路線（YOLO / Vision LLM）因資料量不足和離線需求暫不可行。當前最務實的路線是改良現有 CV pipeline，同時預留未來 ML 介入點。

## What Changes

- **新增評估基礎設施**：per-stage 品質指標、ground truth 標註格式、evaluate.py 評估腳本
- **改良空間分割**：門寬感知 gap closing（endpoint-targeted bridging）、邊界牆連接、over-merge 偵測與拆分
- **改良空間分類**：移除位置相依幾何規則，改用內在特徵（content density、wall thickness、connectivity）
- **改良擦除品質**：修復 import 路徑、CJK 文字渲染「非申報範圍」、邊界精度改善
- **預留 ML 插槽**：pipeline 架構加入 detection 模組介入點，未來資料充足時可無縫切換

## Capabilities

### New Capabilities
- `evaluation-infrastructure`: 評估腳本 + ground truth 格式 + per-stage 品質指標，讓每次改動都可量化
- `ml-readiness`: pipeline 架構預留 ML detection 模組介入點，未來可無縫整合 YOLO 等模型

### Modified Capabilities
（目前無已存在的 spec）

## Impact

- **修改檔案**：`src/wall_detection.py`, `src/segmentation.py`, `src/ocr_classify.py`, `src/eraser.py`, `src/pipeline.py`, `tests/test_pipeline.py`
- **新增檔案**：`src/evaluate.py`, `samples/sample1/ground_truth.json`
- **依賴**：不新增 Python 套件（純 OpenCV + NumPy），保持離線免費運作
- **向下相容**：pipeline CLI 介面不變，新增 `--evaluate` 選項
