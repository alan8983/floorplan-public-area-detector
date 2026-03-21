## ADDED Requirements

### Requirement: 點選房間修改分類
使用者 SHALL 能在 Streamlit「標註編輯」頁籤中，點擊平面圖上的房間區域，系統根據點擊座標 hit-test 找到對應房間並高亮選取，顯示該房間的修改面板。

#### Scenario: 點擊房間選取
- **WHEN** 使用者在標註編輯頁籤中點擊平面圖上某個房間的區域
- **THEN** 系統 SHALL 高亮該房間的 bbox，並在右側顯示該房間的當前類型、面積、特徵資訊

#### Scenario: 點擊空白區域
- **WHEN** 使用者點擊的座標不在任何房間 bbox 內
- **THEN** 系統 SHALL 取消當前選取狀態（清除高亮）

### Requirement: 修改房間分類類型
使用者 SHALL 能透過下拉選單或按鈕，將選取房間的分類類型改為任意支援的類型（stairwell / elevator / corridor / lobby / mechanical / private 細分類型）。

#### Scenario: 透過下拉選單改類型
- **WHEN** 使用者選取一個房間後，從下拉選單選擇新的類型
- **THEN** 系統 SHALL 立即更新該房間的 type 和 is_public 欄位，並重新渲染圖上的顏色標記

#### Scenario: 修改後顯示未儲存標記
- **WHEN** 使用者修改了任何房間的類型但尚未儲存
- **THEN** 系統 SHALL 顯示「未儲存的修改」提示

### Requirement: 儲存 ground truth JSON
使用者 SHALL 能將編輯後的標註儲存為 ground truth JSON 檔案，格式與現有 `auto_annotate.py` 輸出格式相容。

#### Scenario: 儲存標註
- **WHEN** 使用者點擊「儲存」按鈕
- **THEN** 系統 SHALL 將標註以 `[{bbox, type, is_public, note}]` 格式寫入 `samples/<name>/ground_truth.json`

#### Scenario: 載入既有 ground truth
- **WHEN** 使用者選擇的圖片在 `samples/` 下已有對應的 `ground_truth.json`
- **THEN** 系統 SHALL 自動載入該 ground truth 作為初始標註

### Requirement: 自動標註轉校對流程
系統 SHALL 提供「自動標註」按鈕，執行 pipeline 產出 draft 標註，使用者再逐一校對。

#### Scenario: 一鍵自動標註
- **WHEN** 使用者上傳圖片後點擊「自動標註」
- **THEN** 系統 SHALL 執行 pipeline（wall detection → segmentation → classification），將結果轉為可編輯的標註列表

### Requirement: 標註圖視覺化
系統 SHALL 在可點選的平面圖上，以不同顏色的半透明 overlay 或 bbox 框線顯示各房間的分類類型。

#### Scenario: 顏色編碼顯示
- **WHEN** 標註編輯頁籤載入完成
- **THEN** 系統 SHALL 以色彩區分公共類型（綠色系）與私有類型（紅色系），並在 bbox 旁顯示類型文字標籤
