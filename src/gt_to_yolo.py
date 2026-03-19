#!/usr/bin/env python3
"""Ground Truth JSON → YOLO 格式轉換工具。

輸出目錄結構：
    yolo_dataset/
    ├── images/          # 原圖的 symlink 或複製
    ├── labels/          # YOLO .txt 標註檔
    └── classes.txt      # 類別名稱

YOLO 格式（每行）：
    class_id  center_x  center_y  width  height
    （全部為 0~1 歸一化座標）

Class mapping:
    0 = stairwell   (樓梯間)
    1 = elevator     (電梯)
    2 = corridor     (走廊)
    3 = lobby        (梯廳/門廳)
    4 = mechanical   (機電空間)
    5 = private      (私有空間)

用法：
    # 單檔轉換
    python src/gt_to_yolo.py samples/annotations/tku_biz_1F_gt_draft.json -o yolo_dataset/

    # 批次（整個目錄的所有 *_gt_draft.json）
    python src/gt_to_yolo.py samples/annotations/ -o yolo_dataset/

    # 指定圖片來源目錄（用於複製原圖）
    python src/gt_to_yolo.py samples/annotations/ -o yolo_dataset/ --images-dir samples/
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# ── 類別定義 ──
CLASS_MAP = {
    "stairwell": 0,
    "elevator": 1,
    "corridor": 2,
    "lobby": 3,
    "mechanical": 4,
}

# 所有非公共類型統一歸為 private (5)
PRIVATE_CLASS_ID = 5

CLASS_NAMES = ["stairwell", "elevator", "corridor", "lobby", "mechanical", "private"]


def type_to_class_id(room_type: str) -> int:
    """將房間類型映射到 YOLO class_id。"""
    return CLASS_MAP.get(room_type, PRIVATE_CLASS_ID)


def bbox_to_yolo(bbox: list, img_w: int, img_h: int) -> tuple:
    """將 [x, y, w, h] (像素) 轉為 YOLO 歸一化格式。

    Returns:
        (center_x, center_y, width, height) — 全部 0~1
    """
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    # clamp to [0, 1]
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    nw = max(0.0, min(1.0, nw))
    nh = max(0.0, min(1.0, nh))
    return cx, cy, nw, nh


def convert_single(json_path: str, images_dir: str, labels_dir: str,
                   source_images_dir: str = None) -> dict:
    """轉換單一 JSON 檔為 YOLO 格式。

    Returns:
        {"image": 檔名, "labels": 標註數, "copied_image": bool}
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_name = data["image"]
    img_w, img_h = data["image_size"]
    stem = Path(image_name).stem
    annotations = data.get("annotations", [])

    # 寫 YOLO .txt
    label_path = os.path.join(labels_dir, f"{stem}.txt")
    with open(label_path, "w") as f:
        for ann in annotations:
            class_id = type_to_class_id(ann["type"])
            cx, cy, nw, nh = bbox_to_yolo(ann["bbox"], img_w, img_h)
            f.write(f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

    # 複製原圖到 images/
    copied = False
    if source_images_dir:
        # 在 source_images_dir 下遞迴搜尋
        for root, _, files in os.walk(source_images_dir):
            if image_name in files:
                src = os.path.join(root, image_name)
                dst = os.path.join(images_dir, image_name)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    copied = True
                break

    return {
        "image": image_name,
        "labels": len(annotations),
        "copied_image": copied,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ground Truth JSON → YOLO 格式轉換")
    parser.add_argument("input", help="JSON 檔案或包含 *_gt_draft.json 的目錄")
    parser.add_argument("-o", "--output", default="yolo_dataset",
                        help="YOLO 資料集輸出目錄 (預設: yolo_dataset/)")
    parser.add_argument("--images-dir", default=None,
                        help="原圖來源目錄（用於複製到 images/）")
    args = parser.parse_args()

    # 收集 JSON 檔
    p = Path(args.input)
    if p.is_file() and p.suffix == ".json":
        json_files = [str(p)]
    elif p.is_dir():
        json_files = sorted(str(f) for f in p.glob("*_gt_draft.json"))
    else:
        print(f"[ERROR] 無效輸入: {args.input}")
        sys.exit(1)

    if not json_files:
        print(f"[ERROR] 找不到 *_gt_draft.json: {args.input}")
        sys.exit(1)

    # 建立目錄
    images_dir = os.path.join(args.output, "images")
    labels_dir = os.path.join(args.output, "labels")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)

    # classes.txt
    classes_path = os.path.join(args.output, "classes.txt")
    with open(classes_path, "w") as f:
        for name in CLASS_NAMES:
            f.write(f"{name}\n")

    # data.yaml（YOLO 訓練用）
    yaml_path = os.path.join(args.output, "data.yaml")
    with open(yaml_path, "w") as f:
        f.write(f"path: {os.path.abspath(args.output)}\n")
        f.write("train: images\n")
        f.write("val: images\n")
        f.write(f"nc: {len(CLASS_NAMES)}\n")
        f.write(f"names: {CLASS_NAMES}\n")

    print(f"=== JSON → YOLO 轉換 ===")
    print(f"JSON 檔案: {len(json_files)}")
    print(f"輸出目錄: {args.output}")
    print(f"類別: {CLASS_NAMES}")
    print()

    total_labels = 0
    total_images = 0
    for i, jf in enumerate(json_files, 1):
        print(f"[{i}/{len(json_files)}] {Path(jf).name}")
        try:
            result = convert_single(jf, images_dir, labels_dir, args.images_dir)
            total_labels += result["labels"]
            if result["copied_image"]:
                total_images += 1
            print(f"  → {result['labels']} labels"
                  f"{', image copied' if result['copied_image'] else ''}")
        except Exception as e:
            print(f"  [FAIL] {e}")

    print(f"\n{'='*50}")
    print(f"完成: {len(json_files)} 檔案, {total_labels} 標註")
    print(f"圖片複製: {total_images}")
    print(f"輸出:")
    print(f"  {labels_dir}/  ({len(json_files)} .txt)")
    print(f"  {images_dir}/  ({total_images} images)")
    print(f"  {classes_path}")
    print(f"  {yaml_path}")


if __name__ == "__main__":
    main()
