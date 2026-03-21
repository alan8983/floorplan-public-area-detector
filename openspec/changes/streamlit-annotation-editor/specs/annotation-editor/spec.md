## annotation-editor

瀏覽器內的完整 Ground Truth 編輯器，獨立於 pipeline。

### 功能需求

#### F1: Bbox 繪製與編輯
- 使用者可在平面圖上拖曳畫新的 bounding box
- 使用者可拖曳調整既有 bbox 的邊界（移動、縮放）
- 使用者可刪除既有 bbox
- 每個 bbox 必須有 label（類型分類）

#### F2: 分類類型
- 支援以下 label：stairwell, elevator, corridor, lobby, mechanical, private
- `is_public` 根據 type 自動推導（stairwell/elevator/corridor/lobby/mechanical = public）
- 使用者選擇 label 後立即生效，不需額外確認

#### F3: 多種初始標註來源
- **空白模式**：直接在原圖上從零開始標註
- **Pipeline 輔助**：載入 pipeline 偵測結果作為初始 bbox（可增刪改）
- **載入既存 GT**：讀取 `samples/<name>/ground_truth.json` 作為初始標註
- 三種來源互不衝突，使用者可自行選擇

#### F4: 儲存
- 「儲存 Ground Truth」按鈕，將標註寫入 `samples/<name>/ground_truth.json`
- 格式：`[{bbox: [x,y,w,h], type: str, is_public: bool, note: str}]`
- 有未儲存修改時顯示警告提示

#### F5: 座標系統
- 儲存的 bbox 座標為原始圖片像素座標（非顯示座標）
- 大圖（3000+px）在瀏覽器中等比縮放顯示，座標轉換由元件處理

### 非功能需求

- 標註操作（畫框、改 label）的回應時間 < 500ms
- 支援 3000x3600px 以上的平面圖圖片
- 切換 Tab 不丟失未儲存的標註（session_state 保持）
