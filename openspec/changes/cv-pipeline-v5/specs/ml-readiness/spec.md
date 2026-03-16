## ADDED Requirements

### Requirement: Pipeline ML detection 插槽
`pipeline.py` SHALL 支援 `use_ml_detection` 設定開關（default=False）。當開啟時，pipeline 使用 ML detection 模組取代 CV 分割；當關閉時，使用現有 CV pipeline。

#### Scenario: ML 關閉（預設）
- **WHEN** 使用者執行 pipeline 且未設定 `--ml-detect`
- **THEN** pipeline MUST 使用現有 CV 分割流程（wall detection → gap closing → flood fill）

#### Scenario: ML 開啟但模組未安裝
- **WHEN** 使用者執行 pipeline 且設定 `--ml-detect`，但 ML 模組未安裝
- **THEN** pipeline MUST 輸出警告並 fallback 到 CV 分割流程

### Requirement: Ground truth 格式與 YOLO 相容
Ground truth 的 bbox 格式 SHALL 可轉換為 YOLO 標註格式（normalized center_x, center_y, width, height），以便未來直接用於 YOLO 訓練。

#### Scenario: 格式轉換
- **WHEN** ground truth JSON 包含 `[x, y, w, h]` 像素座標和圖片尺寸
- **THEN** MUST 可計算出 YOLO 格式的 normalized 座標
