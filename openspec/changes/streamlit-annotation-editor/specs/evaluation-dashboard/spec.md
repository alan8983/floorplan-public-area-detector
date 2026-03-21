## evaluation-dashboard

Pipeline 預測 vs Ground Truth 的量化比對儀表板。

### 功能需求

#### F1: 指標卡片
- 顯示分類準確度（%）：pipeline 預測 type vs GT type 的 match rate
- 顯示公共/私有二分類準確度（%）
- 顯示公共區域召回率（%）：GT 中的公共房間被 pipeline 正確偵測的比例

#### F2: 逐房間比較表
- 表格列出每個 GT 房間：bbox、GT type、pipeline 預測 type、是否一致
- 不一致的列以視覺標示區分（紅色/加粗）
- 未被 pipeline 偵測到的 GT 房間標示為「未偵測」

#### F3: 無 GT 狀態處理
- 當前圖片沒有 ground truth 時，顯示引導訊息
- 引導使用者到標註編輯 Tab 建立 ground truth

#### F4: 即時重新評估
- 使用者在標註編輯 Tab 修改標註後，切到評估 Tab 看到更新指標
- 使用 session_state 中最新的標註版本計算

### 非功能需求

- 沿用 `src/evaluate.py` 的比對邏輯，不重複實作
- 指標計算 < 1s
