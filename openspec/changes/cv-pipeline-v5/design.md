## Context

現有 pipeline（v3）可運作但品質不足：分割 ~70%、分類 ~55%（純幾何）。經過深度探索，確認：
- ML 路線（CubiCasa5K / MLSTRUCT-FP / YOLO / Vision LLM）因資料量不足 + 離線需求暫緩
- 最大瓶頸是分割（不是分類）— 錯誤向下游連鎖
- 缺乏評估基礎設施，每次改動無法量化

技術棧限制：純 Python + OpenCV + NumPy，不引入新依賴，離線免費運作。

## Goals / Non-Goals

**Goals:**
- 建立可量化的評估流程（per-stage 指標 + ground truth 比對）
- 分割準確度從 ~70% 提升到 ~85%
- 移除位置相依的分類規則，改用內在特徵
- 預留 ML 模組介入點

**Non-Goals:**
- 不引入 ML 模型訓練或推論（Phase D 未來做）
- 不新增 Python 套件依賴
- 不處理 PDF 輸入/輸出（另案）
- 不實作 FR1 防火區劃偵測（另案）

## Decisions

### D1: 評估先於演算法改良

**決定**：先建立 evaluate.py + ground truth，再做任何演算法修改。

**理由**：沒有量化指標的改動是猜測。每次 kernel 調整、規則修改都需要一個數字來判斷是改善還是退步。

**替代方案**：先改演算法再補評估 → 拒絕，因為無法確認改動是否真正有效。

### D2: Endpoint-targeted gap bridging（分割核心改良）

**決定**：不用全域大 kernel closing，改為偵測牆體端點（endpoint），只在端點附近做定向 bridging。

**理由**：
- 全域 `close(90x1)` 會合併平行薄牆（adjacent bathrooms）
- Endpoint-targeted 只在有缺口的地方 bridge，不影響其他區域
- 不需要 `opencv-contrib-python`（用 morphological hit-or-miss 偵測 endpoint）

**替代方案**：
- 全域加大 kernel → 拒絕，over-closing 問題
- Contour-based gap detection → 更精確但實作複雜度高，留作後續優化

### D3: 分類改用內在特徵

**決定**：移除 `rx`/`ry` 位置閾值，改用 content_ratio、wall_thickness_around_room、aspect_ratio 等內在特徵。

**理由**：位置規則（`rx < 0.42 = 樓梯間`）是對一張樣本的 overfitting。樓梯間的真正特徵是「密集平行線 = 高 content_ratio」，不是「在圖面左側」。

### D4: Pipeline 預留 ML 插槽

**決定**：在 `pipeline.py` 加入 `config.use_ml_detection` 開關，目前 default=False。未來資料充足時，插入 YOLO detection 模組不需重寫管線。

**理由**：探索階段確認 YOLO Object Detection 是最適合的 ML 路線（偵測 5 類公共區域物件），但目前資料不足。架構預留成本極低。

### D5: Ground truth 格式

**決定**：JSON 格式，每個房間一個 entry，包含 `bbox`、`type`、`is_public`。不用 SVG 多邊形。

**理由**：
- Bounding box 標註比多邊形快 5-10 倍
- 足以計算 IoU 和分類準確度
- 與 YOLO 標註格式相容（未來可直接用於訓練）

## Risks / Trade-offs

- **Endpoint 偵測在噪音圖面上可能不穩定** → Mitigation: 先 skeleton 再偵測，加上最小端點距離過濾
- **只有 1 張 ground truth 仍有 overfitting 風險** → Mitigation: 評估指標設計為多樣本兼容，取得新圖面後立即加入
- **移除位置規則可能短期降低單一樣本準確度** → Mitigation: 保留 legacy 函數做 A/B 比較，確認內在特徵規則在 sample1 上不退步再切換
- **Morphological skeleton 在 3000x3600 圖面上可能慢** → Mitigation: 預計 1-2 秒，可接受；若太慢可只對 wall mask ROI 做
