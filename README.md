# 建築平面圖公共區域辨識系統

**Automatic Public Area Detection in Architectural Floor Plans**

從建築樓層平面圖中自動辨識公共區域（樓梯、電梯、走廊、大廳、防火區劃），產出簡化後的消防檢查用平面圖。

## 概述

建築師事務所和物業管理公司在準備消防檢查文件時，需要將完整的建築平面圖簡化為僅含公共區域的版本。本工具將這個手動流程自動化：

**Input** → 完整建築樓層平面圖（PDF / 掃描圖 / 圖片）

**Output** → 簡化平面圖（保留外框+公共區域，私有空間擦除標註「非申報範圍」）

## 技術路線

混合路線：電腦視覺 (CV) 做前處理與結構提取 + OCR/ML 做語意分類

```
影像輸入 → 二值化 → 牆體偵測 → 空間分割 → OCR+分類 → 選擇性擦除 → 輸出
```

### 五階段管線

| Phase | 內容 | 技術 | 狀態 |
|-------|------|------|------|
| 1 | 影像前處理 | Otsu 二值化、去噪 | ✅ |
| 2 | 牆體偵測 + 空間分割 | Morphological opening、flood fill | ✅ v3 |
| 3 | 空間分類 | Tesseract OCR + 幾何規則 | 🔄 v4 code ready |
| 4 | 選擇性擦除 | Mask-based erasure | 🔄 prototype |
| 5 | 輸出渲染 | FR1 標註、PDF 生成 | ⬜ |

## 快速開始

### 環境需求

```bash
pip install -r requirements.txt

# Tesseract OCR with Chinese support
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-chi-sim
# macOS:
brew install tesseract tesseract-lang
```

### 執行

```bash
# 完整管線
python -m src.pipeline samples/sample_input.jpg -o output/

# 僅牆體偵測 + 空間分割
python -m src.walls samples/sample_input.jpg -o output/

# 僅 OCR 文字辨識
python -m src.ocr samples/sample_input.jpg
```

## 專案結構

```
├── CLAUDE.md              # Claude Code 專案指引
├── src/
│   ├── pipeline.py        # 端到端主管線
│   ├── preprocess.py      # Phase 1: 影像前處理
│   ├── walls.py           # Phase 2: 牆體偵測 + 空間分割
│   ├── ocr.py             # Phase 3: OCR 文字辨識
│   ├── classify.py        # Phase 3: 空間分類
│   ├── erase.py           # Phase 4: 選擇性擦除
│   └── config.py          # 參數與關鍵字表
├── tests/
├── samples/               # 樣本圖（本地放置，不入版控）
├── docs/
│   └── KNOWLEDGE_BASE.md  # 完整技術知識庫
└── output/                # 輸出目錄
```

## 目標市場

台灣建築師事務所、物業管理公司

## License

MIT
