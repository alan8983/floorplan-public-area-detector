## 0. 你（使用者）的準備工作

- [ ] 0.1 取得 3-5 張台灣建築平面圖（不同建築師事務所、不同格局，住宅為主）。來源建議：建管處公開建照圖、建築師事務所合作、消防圖說檔案
- [ ] 0.2 將圖面放入 `samples/` 目錄，命名為 `sample2_*.jpg`, `sample3_*.jpg` 等
- [ ] 0.3 為 sample1 手動標註 ground truth：用標註工具（Label Studio 或直接寫 JSON）標出每個公共區域的 bounding box 和類型，存為 `samples/sample1/ground_truth.json`
- [ ] 0.4 為每張新圖面也建立 ground truth 標註
- [ ] 0.5 （未來可選）如果累積 30+ 張圖面，可啟動 ML 路線（YOLO Object Detection 訓練）

## 1. 評估基礎設施

- [x] 1.1 在 `src/pipeline.py` 加入 per-stage 品質指標輸出：room count、coverage %、largest room rel_area、OCR hit rate
- [x] 1.2 建立 `src/evaluate.py`：讀取 pipeline 輸出 + ground truth JSON，計算 segmentation IoU、classification accuracy、public/private accuracy
- [x] 1.3 在 `tests/test_pipeline.py` 新增分割品質測試：room count 25-60、max rel_area < 0.15、coverage > 60%
- [ ] 1.4 執行 pipeline on sample1，用 evaluate.py 記錄 baseline 指標到 `docs/baselines.md`

## 2. 分割改良

- [x] 2.1 修改 `close_wall_gaps()` 簽名，接受 `building_bounds` 參數；更新 `pipeline.py` 呼叫處
- [x] 2.2 實作 `_find_wall_endpoints()`：用 morphological hit-or-miss（8 個旋轉 endpoint kernel）偵測牆體端點
- [x] 2.3 實作 `_bridge_gaps_at_endpoints(walls, max_gap=90)`：只在端點附近做定向 closing，避免 over-closing 平行牆
- [x] 2.4 實作 `_connect_walls_to_boundary()`：邊界牆連接，修復邊緣房間漏失
- [x] 2.5 整合到 `close_wall_gaps()`，保留舊實作為 `_close_wall_gaps_legacy()` 供 A/B 比較
- [x] 2.6 在 `segmentation.py` 加入 over-merge 偵測：rel_area > 0.04 且 solidity < 0.65 的房間嘗試拆分（projection profile 找窄通道）
- [ ] 2.7 用 evaluate.py 驗證分割 IoU 提升，與 baseline 比較

## 3. 分類改良

- [x] 3.1 移除 `ocr_classify.py` 中所有 `rx`/`ry` 位置相依規則
- [x] 3.2 改用內在特徵分類：content_ratio（樓梯=高密度）、aspect_ratio（走廊=極長）、area（電梯=極小方形）、solidity
- [ ] 3.3 用 evaluate.py 驗證分類準確度，確認不退步

## 4. 擦除改良

- [x] 4.1 修復 `eraser.py` 的 import 路徑（`from ocr_classify` → 相對 import 或修正 path）
- [x] 4.2 將 `cv2.putText("Non-filing")` 改為 CJK 文字渲染「非申報範圍」（用 Pillow + 系統字型）
- [x] 4.3 改善 public room 周邊復原精度（dilate margin 動態調整）

## 5. ML 預留

- [x] 5.1 在 `pipeline.py` 加入 `--ml-detect` CLI 選項（default=False），加入 if/else 分支框架
- [x] 5.2 確保 ground truth JSON 格式可轉換為 YOLO 標註格式（寫一個小工具函數或記錄轉換方式）

## 6. 驗收

- [ ] 6.1 在所有可用 sample 上執行 pipeline + evaluate.py，確認各項指標達標
- [ ] 6.2 執行 `python -m pytest tests/ -v` 確認所有測試通過
- [ ] 6.3 更新 `CLAUDE.md` 和 `docs/PROJECT_KNOWLEDGE_BASE.md` 反映 v5 變更
