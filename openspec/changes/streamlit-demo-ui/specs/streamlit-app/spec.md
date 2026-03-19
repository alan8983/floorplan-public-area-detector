## ADDED Requirements

### Requirement: 圖檔輸入
系統 SHALL 支援兩種圖檔輸入方式：使用者上傳與預設範例選擇。

#### Scenario: 使用者上傳圖檔
- **WHEN** 使用者透過 file uploader 上傳 JPG 或 PNG 圖檔
- **THEN** 系統顯示原圖預覽，並啟用 Run 按鈕

#### Scenario: 選擇預設範例
- **WHEN** samples/ 目錄存在圖檔，且使用者從 dropdown 選擇一個範例
- **THEN** 系統載入該圖檔顯示原圖預覽，並啟用 Run 按鈕

#### Scenario: 無範例可選
- **WHEN** samples/ 目錄不存在或為空
- **THEN** dropdown 顯示「無可用範例」，使用者仍可透過上傳操作

### Requirement: Pipeline 參數控制
系統 SHALL 在 sidebar 提供 pipeline 參數控制。

#### Scenario: OCR 開關
- **WHEN** 使用者勾選 OCR 啟用 checkbox
- **THEN** pipeline 執行時使用 OCR 分類模式

#### Scenario: OCR 預設關閉
- **WHEN** 頁面初始載入
- **THEN** OCR checkbox 預設為未勾選

### Requirement: Pipeline 執行
系統 SHALL 提供一鍵執行 pipeline 的功能。

#### Scenario: 成功執行
- **WHEN** 使用者點擊 Run 按鈕，且已選擇圖檔
- **THEN** 系統顯示 spinner/進度提示，執行完成後顯示所有階段輸出

#### Scenario: 未選擇圖檔
- **WHEN** 使用者點擊 Run 按鈕，但未上傳或選擇圖檔
- **THEN** 系統顯示提示訊息要求先選擇圖檔

#### Scenario: Pipeline 執行失敗
- **WHEN** pipeline 執行過程中拋出例外
- **THEN** 系統顯示友善錯誤訊息，不崩潰

### Requirement: 各階段輸出展示
系統 SHALL 以 tabs 方式展示 pipeline 各階段輸出圖片。

#### Scenario: Tabs 切換檢視
- **WHEN** pipeline 執行完成
- **THEN** 主區域顯示 tabs：原圖、分類、公私區、擦除、Debug（牆體）

#### Scenario: 圖片全寬顯示
- **WHEN** 使用者點選任一 tab
- **THEN** 該階段圖片以全寬顯示，可清楚檢視細節

### Requirement: Room 分類結果表格
系統 SHALL 顯示 room 分類的詳細結果表格。

#### Scenario: 表格內容
- **WHEN** pipeline 執行完成
- **THEN** 顯示表格包含：編號、類型（中文）、面積比、長寬比、位置、分類原因、是否公共區域

#### Scenario: 公共區域標記
- **WHEN** 表格中某 room 被分類為公共區域
- **THEN** 該列以醒目方式標記（如星號或顏色）

### Requirement: 品質指標摘要
系統 SHALL 在 sidebar 顯示 pipeline 品質指標。

#### Scenario: 指標顯示
- **WHEN** pipeline 執行完成
- **THEN** sidebar 顯示：偵測房間數、覆蓋率、公共/私有數量、處理時間

#### Scenario: 低覆蓋率警告
- **WHEN** 覆蓋率低於 60%
- **THEN** 顯示警告訊息提示分割可能不完整
