## ADDED Requirements

### Requirement: Per-stage quality metrics
Pipeline 執行時 SHALL 輸出每個階段的品質指標，包括：
- Phase 2A（牆體）：thick/thin wall pixel count、wall continuity score
- Phase 2B（分割）：room count、coverage %（segmented area / building interior）、largest room rel_area、avg solidity
- Phase 3（分類）：OCR hit count vs geometry fallback count

#### Scenario: Pipeline 輸出包含品質指標
- **WHEN** 使用者執行 `python src/pipeline.py input.jpg -o output/`
- **THEN** console 輸出 MUST 包含 room count、coverage %、largest room rel_area

#### Scenario: 分割覆蓋率警告
- **WHEN** segmentation coverage 低於 60%
- **THEN** pipeline MUST 輸出警告訊息 `⚠ Low coverage`

### Requirement: Ground truth 標註格式
系統 SHALL 支援 JSON 格式的 ground truth 標註檔，位於 `samples/<sample_name>/ground_truth.json`。

每個房間 entry MUST 包含：
- `bbox`: `[x, y, w, h]` 像素座標
- `type`: 房間類型（英文，如 `stairwell`, `elevator`, `corridor`, `lobby`, `bedroom`）
- `is_public`: boolean

#### Scenario: Ground truth 檔案結構
- **WHEN** 使用者建立 `samples/sample1/ground_truth.json`
- **THEN** 檔案格式 MUST 為 JSON array，每個元素包含 `bbox`、`type`、`is_public` 欄位

### Requirement: 評估腳本
系統 SHALL 提供 `src/evaluate.py` 腳本，比對 pipeline 輸出與 ground truth。

輸出指標 MUST 包含：
- **Segmentation IoU**：每個 ground truth 房間的最佳匹配 IoU，以及平均 IoU
- **Classification accuracy**：匹配房間（IoU > 0.5）的類型正確率
- **Public/private accuracy**：公共/私有二分類正確率

#### Scenario: 執行評估
- **WHEN** 使用者執行 `python src/evaluate.py output/ samples/sample1/ground_truth.json`
- **THEN** 輸出 MUST 包含 mean IoU、classification accuracy、public/private accuracy 數值

#### Scenario: 無 ground truth 檔案
- **WHEN** 指定的 ground truth 路徑不存在
- **THEN** 腳本 MUST 輸出錯誤訊息並 exit code 非零

### Requirement: 分割品質測試
`tests/test_pipeline.py` SHALL 包含分割品質的自動化測試。

#### Scenario: Room count 合理範圍
- **WHEN** 對 sample1 執行分割
- **THEN** room count MUST 在 25-60 之間

#### Scenario: 無超大房間
- **WHEN** 對 sample1 執行分割
- **THEN** 每個房間的 rel_area MUST 小於 0.15

#### Scenario: 覆蓋率下限
- **WHEN** 對 sample1 執行分割
- **THEN** segmentation coverage MUST 大於 60%
