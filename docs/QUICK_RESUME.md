# Quick Resume — 建築平面圖公共區域辨識系統

> 新 session 請先讀這個檔案，再讀 PROJECT_KNOWLEDGE_BASE.md 取得完整細節。

## 你在哪裡
POC Phase 2（牆體偵測+空間分割+分類），v3 完成，v4 (OCR) code ready 但未執行。

## 立刻要做的事
執行 OCR 增強版 pipeline：
```bash
cd /home/claude && python phase2v4_ocr.py
```
如果 numpy/cv2 版本衝突，先執行：
```bash
pip install --force-reinstall opencv-python-headless numpy --break-system-packages
apt-get install -y tesseract-ocr-chi-tra tesseract-ocr-chi-sim
pip install pytesseract --break-system-packages
```

## 關鍵檔案
- 樣本 input: `/mnt/user-data/uploads/1000009203.jpg` (住宅大樓 3-4F)
- 樣本 output 參考: `/mnt/user-data/uploads/1000009204.webp` (期望的簡化格式)
- 最佳 pipeline: `/home/claude/phase2v3_prototype.py` (v3, 無 OCR)
- OCR 增強版: `/home/claude/phase2v4_ocr.py` (v4, 待執行)
- 完整知識庫: `/mnt/user-data/outputs/PROJECT_KNOWLEDGE_BASE.md`

## 核心技術決策
1. **擦除模式**（非重繪）：在原圖上清空私有空間，保留外框+公共區域
2. **混合路線**：CV 做牆體偵測/空間分割，ML+OCR 做分類
3. **牆體提取必須從原始 binary 做**（先過濾會損失牆體 — v2 的教訓）
4. **用 building footprint 區分牆線 vs 尺寸線**（厚牆的 P2/P98 座標）

## 當前最大問題
1. 餐廳/廚房被誤判為梯廳（幾何相似，需 OCR 修正）
2. 頂部尺寸標註帶被誤判為走廊
3. 空間分割完整度 ~70%（門口間隙導致房間合併）

## 用戶偏好
- 語言：繁體中文
- 目標市場：台灣（消防法規、建築圖慣例）
- 輸出要清除所有尺寸標註，保留 FR1 防火區劃標註
- 優先驗證 PDF/掃描圖路線（難度高但市場價值大）
