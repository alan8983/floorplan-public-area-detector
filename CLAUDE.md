# CLAUDE.md — 建築平面圖公共區域辨識系統

## 專案概要
從建築樓層平面圖（PDF/掃描圖/圖片）自動辨識公共區域（樓梯/電梯/走廊/大廳/防火區劃），產出簡化消防檢查用平面圖。**擦除模式**：在原圖上清空私有空間，保留外框+公共區域細節。

## 技術架構
混合路線：CV（OpenCV 牆體偵測+空間分割）+ ML（Tesseract OCR 分類）

五階段管線：
1. **preprocess.py** — 影像前處理（光柵化、Otsu 二值化、去噪）
2. **walls.py** — 牆體偵測+空間分割（morphological opening 提取 H/V 牆線 → building footprint 過濾 → 間隙封閉 → flood fill 分割）
3. **ocr.py** + **classify.py** — OCR 文字辨識+空間分類（OCR 關鍵字優先 → 幾何規則 fallback）
4. **erase.py** — 選擇性擦除（私有空間填白、結構牆重繪、標註清除）
5. 輸出渲染（FR1 標註保留、PDF 生成）— 待實作

## 核心技術決策（踩坑紀錄）
1. **牆體提取必須從原始 binary 做** — 先過濾文字再提取會損失薄牆（v2 的教訓，0 rooms）
2. **用 building footprint 區分牆線 vs 尺寸線** — 厚牆（≥3px）座標的 P2/P98 推估建築範圍，範圍外的薄線視為尺寸標註
3. **v5 間隙封閉** — dilate(5x5) → close(7x7) → endpoint-targeted bridging(max_gap=90) → open(3x3)；使用 morphological skeleton + hit-or-miss 偵測牆端點，只在端點附近做定向 closing，避免 over-close 平行牆
4. **OCR 優先於幾何** — 幾何規則位置依賴性強，OCR 命中直接覆蓋
5. **v5 移除 rx/ry 位置規則** — 改用內在特徵分類（content_ratio, aspect_ratio, area, solidity），提升泛化性
6. **close_wall_gaps 必須傳 building_bounds** — 不傳會 fallback 到 legacy 行為，coverage 從 64% 降到 38%

## 開發環境
```bash
pip install -r requirements.txt
# Tesseract OCR:
sudo apt-get install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-chi-sim
```

## 常用指令
```bash
# 完整管線
python -m src.pipeline samples/sample_input.jpg -o output/

# Web UI（含辨識 + 標註編輯 + 評估儀表板）
streamlit run app.py

# 單步測試
python -m src.walls samples/sample_input.jpg -o output/
python -m src.ocr samples/sample_input.jpg
python -m pytest tests/ -v
```

## Web UI 功能
Streamlit 介面 (`app.py`)，`streamlit run app.py` 啟動後瀏覽 http://localhost:8501
- **辨識結果 Tab**: 上傳/選擇圖片 → 執行 pipeline → 查看分類/分區/擦除結果
- **標註編輯 Tab**: 完整 Ground Truth 編輯器（獨立於 pipeline）
  - 在平面圖上拖曳畫新 bbox、調整邊界、刪除
  - 支援 6 種分類：stairwell / elevator / corridor / lobby / mechanical / private
  - 三種初始來源：空白標註 / 從 Pipeline 載入 / 載入既存 GT
  - 儲存為 `ground_truth.json`
- **評估 Tab**: Pipeline 預測 vs Ground Truth 比對（準確度、IoU、逐房間比較表）
- 依賴: `streamlit-image-annotation` (bbox 繪製與標註元件)

## 當前進度
- Phase 1 (前處理): ✅
- Phase 2 (牆體+分割) v5: ✅ — 35 rooms, coverage 64.3%, endpoint-targeted gap bridging
- Phase 3 (OCR+分類) v5: ✅ — geometry rules + OCR fallback, rx/ry 規則已移除
- Phase 4 (擦除) v5: ✅ — CJK 文字渲染, dynamic margin
- Phase 5 (輸出): ⬜
- 評估基礎設施: ✅ — evaluate.py, ground_truth.json, baselines.md
- 測試: ✅ — 7/7 tests pass, 48 樣本泛化測試 0 crash

## v5 Baseline (sample1)
- Detection rate: 41.2% (7/17 GT rooms matched)
- Mean IoU: 0.917 (matched rooms alignment good)
- Type accuracy: 14.3% (OCR 0 hits, geometry-only)
- Coverage: 64.3% (v5) vs 40.8% (legacy v3) → **+23.4pp improvement**

## 待解決問題
1. **核心區域未分割**: 樓梯間/電梯/梯廳/機電空間在中央核心區未被正確分割為獨立房間
2. **Over-merge**: 底部區域合併為單一巨大房間 (rel_area=0.12)
3. **OCR 失效**: Tesseract 在此 sample 上 0 text blocks（需調查）
4. **分類不準**: 幾何規則把臥室誤判為電梯/機電/梯廳
5. **低解析度圖效果差**: taipei_social_housing 平均 coverage 僅 17.5%

## 樣本資料
放在 `samples/` 下（不入版控）：
- `sample1_input_residential_3F.jpg` — 台北市住宅大樓 3-4F 平面圖 (3105x3601px, S=1:100)
- `sample1/ground_truth.json` — 手動標註 ground truth (17 rooms: 7 public, 10 private)
- `sample2_expected_output_3F.webp` — 期望輸出風格參考（地上三層平面圖）
- `residential/` — 7 張住宅平面圖
- `taipei_social_housing/` — 12 張社會住宅
- `tku_university/` — 15 張大學建築
- `hospital_gov/` — 6 張醫院/政府建築
- `areo_airport_city/` — 8 張航空城

## 語言與市場
- 程式碼註解/文件：中文（繁體）+ 英文
- OCR 辨識：繁體中文 + 英文
- 目標市場：台灣

## 完整技術知識庫
詳見 `docs/PROJECT_KNOWLEDGE_BASE.md`

## 評估基準
詳見 `docs/baselines.md`
