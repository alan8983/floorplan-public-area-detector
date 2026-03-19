#!/usr/bin/env python3
"""自動標註工具 — 跑完整 pipeline 產出 ground truth draft JSON + 視覺化 PNG。

用法：
    # 單張圖
    python src/auto_annotate.py samples/residential/residential_AB_lobby.png -o samples/annotations/

    # 批次（整個目錄，遞迴掃描）
    python src/auto_annotate.py samples/ -o samples/annotations/ --recursive

    # 啟用 OCR
    python src/auto_annotate.py samples/residential/ -o samples/annotations/ --ocr
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import cv2
import numpy as np

from preprocessing import load_and_binarize
from wall_detection import detect_walls, close_wall_gaps
from segmentation import segment_rooms
from ocr_classify import PUBLIC_TYPES, ocr_extract, match_keywords, classify_rooms

# ── 顏色定義（BGR）──
COLOR_PUBLIC = (0, 200, 0)       # 綠色
COLOR_PRIVATE = (0, 0, 200)      # 紅色
COLOR_ANNOTATION = (180, 180, 180)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


def annotate_single(image_path: str, output_dir: str, use_ocr: bool = False) -> dict:
    """對單張圖片跑 pipeline，輸出 JSON + 視覺化 PNG。

    Returns:
        {"image": 檔名, "rooms": int, "public": int, "private": int, "elapsed": float}
    """
    stem = Path(image_path).stem
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    # ── Phase 1: 前處理 ──
    img, gray, binary = load_and_binarize(image_path)
    h, w = img.shape[:2]

    # ── Phase 2: 牆體偵測 + 分割 ──
    wall_data = detect_walls(binary)
    walls_closed = close_wall_gaps(wall_data["walls"], wall_data["building_bounds"])
    rooms, labels = segment_rooms(walls_closed, binary)
    bounds = wall_data["building_bounds"]

    # ── Phase 3: OCR + 分類 ──
    matched_labels = []
    if use_ocr:
        texts = ocr_extract(binary)
        matched_labels = match_keywords(texts)

    classify_rooms(rooms, bounds, h, w, matched_labels)

    # ── 產出 ground truth JSON ──
    annotations = []
    for r in rooms:
        if r["type"] == "annotation":
            continue
        x, y, bw, bh = r["bbox"]
        is_public = r["type"] in PUBLIC_TYPES
        annotations.append({
            "bbox": [int(x), int(y), int(bw), int(bh)],
            "type": r["type"],
            "type_zh": r.get("type_zh", r["type"]),
            "is_public": is_public,
            "confidence": r.get("reason", "geo:unknown"),
            "area": int(r["area"]),
            "aspect_ratio": round(r["aspect_ratio"], 3),
            "solidity": round(r["solidity"], 3),
        })

    gt_data = {
        "image": os.path.basename(image_path),
        "image_size": [w, h],
        "num_rooms": len(annotations),
        "annotations": annotations,
    }

    json_path = os.path.join(output_dir, f"{stem}_gt_draft.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(gt_data, f, ensure_ascii=False, indent=2)

    # ── 視覺化 PNG ──
    vis = img.copy()
    for ann in annotations:
        x, y, bw, bh = ann["bbox"]
        is_pub = ann["is_public"]
        color = COLOR_PUBLIC if is_pub else COLOR_PRIVATE

        # 半透明填充
        overlay = vis.copy()
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, -1)
        alpha = 0.25
        vis = cv2.addWeighted(vis, 1 - alpha, overlay, alpha, 0)

        # bbox 外框
        thickness = max(2, min(h, w) // 500)
        cv2.rectangle(vis, (x, y), (x + bw, y + bh), color, thickness)

        # 標籤
        label = f"{ann['type_zh']}"
        tag = "[PUB]" if is_pub else "[PRI]"
        text = f"{tag} {label}"

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.4, min(h, w) / 3000)
        text_thick = max(1, int(font_scale * 2))
        (tw, th_text), _ = cv2.getTextSize(text, font, font_scale, text_thick)

        # 背景色塊
        tx, ty = x + 2, y + th_text + 4
        cv2.rectangle(vis, (tx - 1, ty - th_text - 2), (tx + tw + 1, ty + 2),
                       (255, 255, 255), -1)
        cv2.putText(vis, text, (tx, ty), font, font_scale, color, text_thick, cv2.LINE_AA)

    # 圖例
    legend_h = 60
    legend_w = 280
    ly = h - legend_h - 10
    lx = 10
    cv2.rectangle(vis, (lx, ly), (lx + legend_w, ly + legend_h), (255, 255, 255), -1)
    cv2.rectangle(vis, (lx, ly), (lx + legend_w, ly + legend_h), (0, 0, 0), 1)
    cv2.rectangle(vis, (lx + 8, ly + 8), (lx + 28, ly + 24), COLOR_PUBLIC, -1)
    cv2.putText(vis, "Public", (lx + 35, ly + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.rectangle(vis, (lx + 8, ly + 32), (lx + 28, ly + 48), COLOR_PRIVATE, -1)
    cv2.putText(vis, "Private", (lx + 35, ly + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    # 統計文字
    n_pub = sum(1 for a in annotations if a["is_public"])
    n_pri = len(annotations) - n_pub
    stat_text = f"Rooms: {len(annotations)} (pub={n_pub}, pri={n_pri})"
    cv2.putText(vis, stat_text, (lx + 140, ly + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    vis_path = os.path.join(output_dir, f"{stem}_annotated.png")
    cv2.imwrite(vis_path, vis)

    elapsed = time.time() - t0
    print(f"  [OK] {stem}: {len(annotations)} rooms "
          f"(pub={n_pub}, pri={n_pri}) — {elapsed:.1f}s")

    return {
        "image": os.path.basename(image_path),
        "rooms": len(annotations),
        "public": n_pub,
        "private": n_pri,
        "elapsed": round(elapsed, 1),
    }


def collect_images(input_path: str, recursive: bool = False,
                   exclude_dirs: list[str] = None) -> list[str]:
    """收集圖片路徑。支援單檔或目錄。

    Args:
        exclude_dirs: 排除的目錄名稱（如 ['annotations']），避免處理輸出檔。
    """
    exclude_dirs = set(exclude_dirs or ["annotations"])
    p = Path(input_path)
    if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
        return [str(p)]
    if p.is_dir():
        pattern = "**/*" if recursive else "*"
        files = sorted(
            str(f) for f in p.glob(pattern)
            if f.is_file()
            and f.suffix.lower() in IMAGE_EXTS
            and not any(ex in f.parts for ex in exclude_dirs)
        )
        return files
    return []


def main():
    parser = argparse.ArgumentParser(
        description="自動標註工具 — pipeline → ground truth JSON + 視覺化 PNG")
    parser.add_argument("input", help="圖片路徑或目錄")
    parser.add_argument("-o", "--output", default="samples/annotations",
                        help="輸出目錄 (預設: samples/annotations/)")
    parser.add_argument("--ocr", action="store_true", help="啟用 OCR 分類")
    parser.add_argument("--recursive", action="store_true",
                        help="遞迴掃描子目錄")
    args = parser.parse_args()

    images = collect_images(args.input, args.recursive)
    if not images:
        print(f"[ERROR] 找不到圖片: {args.input}")
        sys.exit(1)

    print(f"=== 自動標註 ===")
    print(f"圖片數量: {len(images)}")
    print(f"輸出目錄: {args.output}")
    print(f"OCR: {'ON' if args.ocr else 'OFF'}")
    print()

    results = []
    for i, img_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] {Path(img_path).name}")
        try:
            result = annotate_single(img_path, args.output, use_ocr=args.ocr)
            results.append(result)
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append({"image": os.path.basename(img_path), "error": str(e)})

    # 批次摘要
    print(f"\n{'='*50}")
    print(f"完成: {sum(1 for r in results if 'error' not in r)}/{len(results)}")
    total_rooms = sum(r.get("rooms", 0) for r in results)
    total_pub = sum(r.get("public", 0) for r in results)
    total_pri = sum(r.get("private", 0) for r in results)
    print(f"共偵測 {total_rooms} 個空間 (公共={total_pub}, 私有={total_pri})")

    # 寫入批次摘要 JSON
    summary_path = os.path.join(args.output, "_batch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"摘要: {summary_path}")


if __name__ == "__main__":
    main()
