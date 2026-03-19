# 建築平面圖公共區域辨識系統 — Project Knowledge Base

> 最後更新：2026-03-19
> 狀態：POC Phase 2 v5 完成，評估基礎設施就緒

---

## 1. 產品定義

### 1.1 核心概念
用戶提供建築物的樓層平面圖（PDF/掃描圖/圖片），系統自動辨識其中的公共區域，
產出簡化後的公共區域平面圖。用途是優化提交給地方政府的**消防檢查文件**準備流程。

### 1.2 目標使用者
- **建築師事務所**：加速消防檢查文件的平面圖準備
- **物業管理公司**：簡化定期消防安全檢查的文件更新

### 1.3 核心功能（擦除模式）
**Input**: 完整建築樓層平面圖（含公共空間+私人空間所有細節）
**Output**: 簡化平面圖 — 保留建築外框+公共區域細節，私人空間清空並標註「非申報範圍」

**產出邏輯不是「重繪」而是「選擇性擦除」**：
- 保留：建築外牆輪廓、公共區域內所有細節（牆線、門、樓梯符號等）、FR1 防火區劃標註
- 擦除：私有空間內的一切（傢俱、門窗符號、衛浴設備、尺寸標註等）
- 清除：全圖的尺寸標註線、軸線編號

### 1.4 需辨識的五類公共區域
1. 樓梯間（含安全梯）
2. 電梯/電梯廳
3. 走廊/通道
4. 大廳/門廳/梯廳
5. 安全梯/防火區劃

---

## 2. 技術架構

### 2.1 技術路線
**混合路線**：傳統電腦視覺 (CV) 做前處理與結構提取 + 機器學習 (ML) 做語意分類

### 2.2 五階段管線

```
Phase 1: 影像前處理
  PDF/圖片 → 光柵化 300DPI → 灰階 → Otsu 二值化 → 去噪
  
Phase 2: 結構理解（核心難點）
  2A. 牆體偵測：多尺度 morphological opening（H/V 方向，length=20/30/50/80）
  2B. 牆體分類：厚牆（結構牆，≥3px）vs 薄牆（隔間牆）
  2C. 建築邊界偵測：從厚牆座標的 P2/P98 推估 building footprint
  2D. 薄牆過濾：只保留 building footprint 內的薄牆（排除尺寸標註線）
  2E. 間隙封閉 (v5)：dilate(5x5) → close(7x7) → endpoint-targeted bridging(90px) → open(3x3)
      + _connect_walls_to_boundary() 修復邊緣房間漏失
      + _bridge_gaps_at_endpoints() 使用 morphological skeleton + hit-or-miss 端點偵測
  2F. 空間分割：invert walls → flood fill exterior → connected components
      + over-merge 偵測 (rel_area>4% & solidity<65%) → projection profile 拆分

Phase 3: 空間分類
  3A. OCR 文字辨識：Tesseract (chi_tra+eng, psm=11) 掃描全圖
  3B. 關鍵字匹配：將 OCR 結果比對公共/私有空間關鍵字表
  3C. OCR 優先分類：文字命中的空間直接判定
  3D. 幾何 fallback：面積、長寬比、位置、solidity、content density

Phase 4: 選擇性擦除
  - 私有空間區域填白
  - 重繪結構牆（thick_walls）
  - 重繪公共空間周邊原始內容
  - 清空區域標註「非申報範圍」

Phase 5: 輸出渲染
  - FR1 防火標註保留（待實作）
  - 輸出格式：PNG（預覽）+ PDF（正式文件）
```

### 2.3 技術 Stack
| 層級 | 選型 | 用途 |
|------|------|------|
| 語言 | Python 3.12 | 主開發語言 |
| PDF | pdf2image + PyMuPDF | PDF 光柵化 |
| 影像 | OpenCV 4.x | 二值化、morphology、輪廓、flood fill |
| OCR | Tesseract 5.3 (chi_tra+eng) | 中英文房間標註辨識 |
| ML | scikit-learn / XGBoost | 空間分類（待實作） |
| 幾何 | Shapely + NetworkX | 空間拓撲分析（待實作） |
| 輸出 | Pillow + ReportLab | 簡化平面圖生成 |

---

## 3. 開發進度

### 3.1 已完成

#### Phase 1: 影像前處理 ✅
- Otsu 二值化可正確處理住宅大樓平面圖
- 圖面品質分析（白比96%、黑比4%、高對比度）

#### Phase 2: 牆體偵測 + 空間分割 ✅ (v5)
- **v1**: 基礎 Connected Components，偵測到 21 個空間，但尺寸線干擾嚴重
- **v2**: 嘗試先過濾再偵測，但過濾太激進把牆也移掉了（0 rooms）
- **v3**: 從原始 binary 直接提取牆體，用 building footprint 過濾薄牆，36 rooms, coverage ~40.8%
- **v5 (當前)**: Endpoint-targeted gap bridging + boundary wall connection + over-merge split
  - 35 rooms, coverage 64.3% (+23.4pp vs v3)
  - Mean IoU 0.917 vs GT (matched rooms)
  - 48 張多樣本泛化測試，0 crash

#### Phase 3: OCR + 分類 ✅ (v5)
- Tesseract 已整合 (chi_tra + eng, PSM=11)
- OCR 優先 + 幾何 fallback 分類
- v5 移除 rx/ry 位置規則，改用內在特徵（content_ratio, aspect_ratio, area, solidity）
- **注意**: sample1 上 OCR 返回 0 text blocks，需調查

#### Phase 4: 擦除 ✅ (v5)
- 私有空間填白 + 結構牆重繪
- CJK 文字渲染「非申報範圍」（Pillow + 系統字型）
- 公共空間周邊動態 margin 復原

#### 評估基礎設施 ✅ (v5)
- `src/evaluate.py`: 自動比對 pipeline 輸出 vs ground truth
- `samples/sample1/ground_truth.json`: 手動標註 17 rooms (7 public, 10 private)
- `docs/baselines.md`: 完整評估指標記錄
- `tests/test_pipeline.py`: 7 項測試全部通過

### 3.2 待完成
- [ ] OCR 調查：為何 Tesseract 在 sample1 上 0 hits
- [ ] 核心區域分割改善：樓梯間/電梯/梯廳需被正確分割
- [ ] Over-merge 修復：底部大區域需拆分
- [ ] FR1 防火區劃標註辨識與保留
- [ ] Phase 5 輸出渲染模組
- [ ] 更多 ground truth 標註（sample2+）

### 3.3 已知問題
1. **核心區域未分割**: 樓梯間/電梯/梯廳在中央核心區未被正確分割為獨立房間
2. **Over-merge**: 底部區域合併為單一巨大房間 (rel_area=0.12)
3. **OCR 失效**: Tesseract 在 sample1 上返回 0 text blocks
4. **分類不準**: 幾何規則把臥室/浴室/陽台誤判為電梯/機電
5. **低解析度圖效果差**: taipei_social_housing (2339×1654) 平均 coverage 僅 17.5%
6. **高解析度圖處理慢**: hospital_gov (7000-8000px) 需 30-120 秒

---

## 4. 樣本資料

### 4.1 可用樣本
| 檔案 | 類型 | 說明 |
|------|------|------|
| `1000009203.jpg` | Input 樣本 | 台北市住宅大樓 3-4F 平面圖 (A戶)，S=1:100，3105x3601px |
| `1000009204.webp` | Output 參考 | 地上三層平面圖，展示期望的簡化輸出風格 |

### 4.2 Input 樣本特徵 (1000009203.jpg)
- 台灣典型住宅大樓建築圖，台北市新生南路
- 公共區域在左側：樓梯間（帶上下箭頭平行線）、電梯（10人份行動不便電梯）、機電空間、梯廳
- 私有空間在右側：客廳、餐廳/廚房、臥室x2、主臥室、浴室x2、陽台x2
- 密集標註：尺寸線、軸線(A/B/E, 2-6)、門窗編號(D1-D8, W1-W5)、地界線、建築線
- 白比96%、黑比4%，高對比度，適合二值化

### 4.3 Output 參考特徵 (1000009204.webp)
- 保留建築外框輪廓
- 中央核心保留完整：走道、門廳、EV、樓梯(S1/S2)、門(D1/D2)
- 三個大區標示「非申報範圍」/ 「非申報範圍（他棟建物）」
- FR1 防火區劃標註遍布
- 含比例尺（0-100-300-600 CM）

---

## 5. OCR 關鍵字表

### 5.1 公共區域關鍵字
```python
PUBLIC_KEYWORDS = {
    '樓梯': 'stairwell', '梯間': 'stairwell', '安全梯': 'stairwell',
    'ST': 'stairwell', 'STAIR': 'stairwell',
    '電梯': 'elevator', 'EV': 'elevator', 'EL': 'elevator',
    '走廊': 'corridor', '走道': 'corridor', '通道': 'corridor',
    '大廳': 'lobby', '門廳': 'lobby', '梯廳': 'lobby',
    'HALL': 'lobby', 'LOBBY': 'lobby',
    '機電': 'mechanical', '機械': 'mechanical', '機電空間': 'mechanical',
}
```

### 5.2 私有區域關鍵字
```python
PRIVATE_KEYWORDS = {
    '客廳': 'living_room', '餐廳': 'kitchen', '廚房': 'kitchen',
    '臥室': 'bedroom', '主臥': 'bedroom', '臥': 'bedroom',
    '浴室': 'bathroom', '廁所': 'bathroom', '衛浴': 'bathroom',
    '陽台': 'balcony', '陽臺': 'balcony',
    '儲藏': 'storage', '玄關': 'entrance',
}
```

---

## 6. 幾何分類規則（v5, OCR fallback）

v5 已移除所有 rx/ry 位置規則，改用內在特徵：

| 類型 | 相對面積 | 長寬比 | 其他特徵 |
|------|---------|--------|---------|
| annotation | — | >4 或 <0.25 | rel_y 在建築邊緣 |
| corridor | < 2% | >3.5 或 <0.28 | 建築內部 (5%-95% height) |
| stairwell | 0.3%~3% | 0.3~3.0 | content_ratio > 12% |
| elevator | < 0.6% | 0.4~2.5 | — |
| mechanical | 0.3%~1.2% | — | solidity > 70% |
| lobby | 0.8%~4% | — | solidity > 50% |
| private_large | > 2.5% | — | — |
| private | default | — | — |

---

## 7. 關鍵技術發現

### 7.1 牆體偵測策略
**正確做法**: 從原始 binary 直接用 morphological opening 提取 H/V 線段
**錯誤做法**: 先過濾文字/標註再提取牆（會把薄牆也移除）

### 7.2 尺寸線 vs 牆線區分
- 尺寸線：薄（1-2px）、位於 building footprint 外的邊距區域
- 牆線：厚（≥3px）或位於 building footprint 內
- 策略：用 building footprint（厚牆的 P2/P98 座標）作為分界

### 7.3 空間分割的關鍵挑戰
- 門口間隙導致相鄰房間合併 → 需要定向 morphological closing
- 過度 closing 會合併走廊兩側的房間 → closing kernel 不能太大
- **v5 策略**: endpoint-targeted bridging — 用 morphological skeleton 找牆端點，只在端點附近 90px 內做 closing
- **v3 legacy**: dilate(5x5) → close(25x1) → close(1x25) → close(7x7)，coverage 僅 40.8%
- **v5 結果**: coverage 64.3%（+23.4pp），但 over-merge 增加（largest room 0.12 vs 0.04）

### 7.4 圖面元素層次
```
Layer 1 (結構): 外牆、承重牆（厚線）
Layer 2 (隔間): 隔間牆（薄線）
Layer 3 (開口): 門弧線、窗線
Layer 4 (設備): 傢俱、衛浴設備、廚具
Layer 5 (標註): 尺寸線、數字、軸線編號、房間名稱
Layer 6 (符號): 樓梯符號、電梯符號、FR1 標記
Layer 7 (邊界): 地界線、建築線（虛線）
```

---

## 8. POC 成功指標

| 指標 | 目標 | v3 | v5 (geometry) | v5 (with OCR) |
|------|------|-----|---------------|---------------|
| Detection rate | ≥ 80% | ~47% | 41.2% | 41.2% (OCR 0 hits) |
| Mean IoU | ≥ 0.70 | 0.716 | **0.917** | 0.917 |
| Type accuracy | ≥ 75% | 0% | 14.3% | 14.3% |
| Coverage | ≥ 85% | 40.8% | **64.3%** | 64.3% |
| 單張處理時間 | < 60s | ~5s | ~8s | ~8s |
| 穩定性 (48 samples) | 0 crash | — | **0 crash** | — |

---

## 9. 檔案索引

### 9.1 程式碼 (src/)
| 檔案 | 說明 | 狀態 |
|------|------|------|
| `pipeline.py` | CLI 入口，五階段管線控制器 | ✅ v5 |
| `preprocessing.py` | Phase 1: 影像載入、Otsu 二值化 | ✅ |
| `wall_detection.py` | Phase 2A: 牆體偵測、gap closing、building bounds | ✅ v5 |
| `segmentation.py` | Phase 2B: Flood-fill 空間分割、over-merge split | ✅ v5 |
| `ocr_classify.py` | Phase 3: OCR + 幾何分類 | ✅ v5 |
| `eraser.py` | Phase 4: 選擇性擦除、CJK 文字渲染 | ✅ v5 |
| `visualize.py` | 視覺化輔助（classification, zones overlay） | ✅ |
| `evaluate.py` | Ground truth 評估腳本 | ✅ v5 |

### 9.2 測試與文件
| 檔案 | 說明 |
|------|------|
| `tests/test_pipeline.py` | 7 項 smoke tests (all pass) |
| `samples/sample1/ground_truth.json` | 手動標註 GT (17 rooms) |
| `docs/baselines.md` | 評估基準記錄（v5 vs legacy, 多樣本測試） |
| `docs/PROJECT_KNOWLEDGE_BASE.md` | 完整技術知識庫 |
| `docs/QUICK_RESUME.md` | 快速上手參考 |

---

## 10. 下一步行動項

### 立即（本週）
1. **調查 OCR 失效原因**: Tesseract 在 sample1 上 0 text blocks，需檢查 PSM 設定、圖面品質、解析度
2. **改善核心區域分割**: 樓梯間/電梯/梯廳需被正確分割為獨立房間
3. **處理 over-merge**: 改進 projection profile split logic

### 短期（1-2 週）
4. 為更多樣本建立 ground truth（sample2+）
5. FR1 防火區劃辨識模組
6. Phase 5 輸出渲染（PDF 生成）

### 中期（3-4 週）
7. 低解析度圖面優化（resizing 策略）
8. Web 介面原型
9. ML 路線評估（如累積 30+ 張標註圖面）
