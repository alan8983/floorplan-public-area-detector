# 建築平面圖公共區域辨識系統 — Project Knowledge Base

> 最後更新：2026-03-16
> 狀態：POC Phase 2 開發中（v3 完成，v4 OCR 整合待執行）

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
  2E. 間隙封閉：dilate(5x5) → directional close(25x1, 1x25) → close(7x7)
  2F. 空間分割：invert walls → flood fill exterior → connected components

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

#### Phase 2: 牆體偵測 + 空間分割 ✅ (v3)
- **v1**: 基礎 Connected Components，偵測到 21 個空間，但尺寸線干擾嚴重
- **v2**: 嘗試先過濾再偵測，但過濾太激進把牆也移掉了（0 rooms）
- **v3 (當前最佳)**: 改為從原始 binary 直接提取牆體，再用 building footprint 過濾薄牆
  - 偵測到 36 個空間
  - 16 個公共 / 20 個私有
  - 空間分割完整度 ~70%
  - 分類準確度 ~55%（純幾何規則，無 OCR）

#### Phase 3: OCR 整合 🔄 (v4 code ready, not yet executed)
- Tesseract 已安裝 (chi_tra + eng)
- v4 script 已完成，包含完整 OCR + 分類 pipeline
- **尚未執行**（上一輪 session 修完 numpy 相容性後到達 tool-use 上限）

### 3.2 待完成
- [ ] 執行 v4 OCR pipeline 並評估結果
- [ ] 調整 OCR 參數（PSM mode、conf threshold）
- [ ] FR1 防火區劃標註辨識與保留
- [ ] 擦除品質優化（邊界精確度、殘留元素清理）
- [ ] 多樣本泛化測試
- [ ] Phase 5 輸出渲染模組

### 3.3 已知問題
1. **餐廳/廚房誤判為梯廳**：幾何特徵相似，需 OCR 修正
2. **頂部尺寸標註區被誤判為走廊**：極長窄形狀觸發走廊規則
3. **右側邊界出現碎片空間**：牆體與邊界線之間的縫隙
4. **門口間隙封閉不完整**：部分房間仍合併
5. **擦除區域有殘留元素**：空間遮罩邊界偏差

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

## 6. 幾何分類規則（OCR fallback）

當 OCR 無法辨識房間標註時，使用以下規則：

| 類型 | 相對面積 | 長寬比 | 位置 | 其他 |
|------|---------|--------|------|------|
| 走廊 | < 0.02 | > 3.5 或 < 0.28 | 建築內部 | — |
| 樓梯間 | 0.003~0.03 | 0.3~3.0 | rx < 0.42 | content > 0.12 |
| 電梯 | < 0.006 | 0.4~2.5 | rx < 0.48 | — |
| 機電空間 | 0.003~0.012 | — | rx < 0.40, ry 0.4~0.7 | — |
| 梯廳 | 0.008~0.04 | — | rx 0.3~0.55 | solidity > 0.5 |
| 陽台 | < 0.015 | — | ry < 0.35 | — |

注意：這些位置規則是基於 sample1 的左公共右私有佈局，泛化性有限。

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
- 門口間隙導致相鄰房間合併 → 需要 directional morphological closing
- 過度 closing 會合併走廊兩側的房間 → closing kernel 不能太大
- 最佳參數組合：dilate(5x5,1次) → close(25x1) → close(1x25) → close(7x7)

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

| 指標 | 目標 | 當前 (v3) | 預估 (v4+OCR) |
|------|------|-----------|---------------|
| 公共區域偵測率 | ≥ 80% | ~65% | ~80% |
| 分類準確率 | ≥ 75% | ~55% | ~80% |
| 空間分割完整度 | ≥ 85% | ~70% | ~70% |
| 單張處理時間 | < 60s | ~5s | ~10s |

---

## 9. 檔案索引

### 9.1 程式碼（/home/claude/）
| 檔案 | 說明 | 狀態 |
|------|------|------|
| `analyze_samples.py` | Phase 1 樣本分析（histogram, LSD, MSER） | ✅ 完成 |
| `phase2_prototype.py` | Phase 2 v1（基礎 CC 分割） | ✅ 已棄用 |
| `phase2v3_prototype.py` | Phase 2 v3（牆體優先提取，當前最佳） | ✅ 完成 |
| `phase2v4_ocr.py` | Phase 2 v4（OCR 增強分類，完整版） | 🔄 待執行 |
| `poc_plan.js` | POC 計畫 Word 文件生成器 | ✅ 完成 |

### 9.2 輸出文件（/mnt/user-data/outputs/）
| 檔案 | 說明 |
|------|------|
| `POC_技術驗證計畫_v1.docx` | POC 計畫文件（需更新為擦除模式架構） |
| `v3_01_room_classification.png` | v3 空間分類結果 |
| `v3_02_public_private_zones.png` | v3 公私區域分區圖 |
| `v3_03_simulated_erasure.png` | v3 模擬擦除輸出 |

---

## 10. 下一步行動項

### 立即（本週）
1. **執行 v4 OCR pipeline**：`python /home/claude/phase2v4_ocr.py`
   - 環境已就緒：Tesseract 5.3 + chi_tra + numpy/cv2 相容
2. 評估 OCR 對分類準確度的提升
3. 調整 OCR 參數如果初始結果不理想

### 短期（1-2 週）
4. FR1 防火區劃辨識模組
5. 擦除品質優化（邊界精確度）
6. 第二張樣本 (1000009204.webp) 的反向驗證

### 中期（3-4 週）
7. 更多樣本泛化測試
8. Web 介面原型
9. 更新 POC 計畫文件
