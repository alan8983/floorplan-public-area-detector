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
3. **間隙封閉參數** — dilate(5x5,1次) → close(25x1) → close(1x25) → close(7x7)；kernel 太大會合併走廊兩側房間
4. **OCR 優先於幾何** — 幾何規則位置依賴性強（左公共右私有），OCR 命中直接覆蓋

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

# 單步測試
python -m src.walls samples/sample_input.jpg -o output/
python -m src.ocr samples/sample_input.jpg
python -m pytest tests/ -v
```

## 當前進度
- Phase 1 (前處理): ✅
- Phase 2 (牆體+分割) v3: ✅ — 36 rooms, 空間分割 ~70%
- Phase 3 (OCR+分類) v4: 🔄 code ready, 待驗證
- Phase 4 (擦除): 🔄 prototype
- Phase 5 (輸出): ⬜

## 待解決問題
1. 餐廳/廚房誤判為梯廳（幾何相似，待 OCR 修正）
2. 頂部尺寸標註帶被誤判為走廊
3. 空間分割完整度 ~70%（門口間隙導致合併）
4. 擦除區域有殘留元素

## 樣本資料
放在 `samples/` 下（不入版控）：
- `sample_input.jpg` — 台北市住宅大樓 3-4F 平面圖 (3105x3601px, S=1:100)
- `sample_output_ref.webp` — 期望輸出風格參考（地上三層平面圖）

## 語言與市場
- 程式碼註解/文件：中文（繁體）+ 英文
- OCR 辨識：繁體中文 + 英文
- 目標市場：台灣

## 完整技術知識庫
詳見 `docs/KNOWLEDGE_BASE.md`
