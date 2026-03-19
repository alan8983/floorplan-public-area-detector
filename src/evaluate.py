#!/usr/bin/env python3
"""Evaluation script — compare pipeline output with ground truth.

Usage:
    python src/evaluate.py output/ samples/sample1/ground_truth.json

Ground truth JSON format:
    [
        {"bbox": [x, y, w, h], "type": "stairwell", "is_public": true},
        {"bbox": [x, y, w, h], "type": "bedroom", "is_public": false},
        ...
    ]

YOLO format conversion:
    Ground truth bbox [x, y, w, h] (pixels) can be converted to YOLO format:
        class_id  center_x/img_w  center_y/img_h  w/img_w  h/img_h
    Example: bbox [100, 200, 80, 60] on 3105x3601 image:
        0  0.0451  0.0639  0.0258  0.0167
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import cv2
import numpy as np

from preprocessing import load_and_binarize
from wall_detection import detect_walls, close_wall_gaps
from segmentation import segment_rooms
from ocr_classify import PUBLIC_TYPES, classify_rooms, ocr_extract, match_keywords


def load_ground_truth(gt_path: str) -> list[dict]:
    """Load ground truth annotations from JSON file."""
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def bbox_iou(bbox_a: list, bbox_b: list) -> float:
    """Compute IoU between two bounding boxes [x, y, w, h]."""
    ax, ay, aw, ah = bbox_a
    bx, by, bw, bh = bbox_b

    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1)


def match_rooms_to_gt(rooms: list[dict], gt_entries: list[dict], iou_threshold: float = 0.3) -> list[dict]:
    """Match detected rooms to ground truth entries by IoU.

    Returns list of dicts with: gt, pred, iou (or gt with pred=None if unmatched).
    """
    matches = []
    used_rooms = set()

    for gt in gt_entries:
        gt_bbox = gt["bbox"]
        best_iou = 0.0
        best_room = None
        best_idx = -1

        for i, r in enumerate(rooms):
            if i in used_rooms:
                continue
            iou = bbox_iou(gt_bbox, list(r["bbox"]))
            if iou > best_iou:
                best_iou = iou
                best_room = r
                best_idx = i

        if best_iou >= iou_threshold and best_room is not None:
            used_rooms.add(best_idx)
            matches.append({"gt": gt, "pred": best_room, "iou": best_iou})
        else:
            matches.append({"gt": gt, "pred": None, "iou": best_iou})

    return matches


def evaluate(rooms: list[dict], gt_path: str) -> dict:
    """Run evaluation and return metrics dict."""
    gt_entries = load_ground_truth(gt_path)

    matches = match_rooms_to_gt(rooms, gt_entries)

    # Segmentation IoU
    ious = [m["iou"] for m in matches]
    matched_ious = [m["iou"] for m in matches if m["pred"] is not None]
    mean_iou = sum(matched_ious) / max(len(matched_ious), 1)
    detection_rate = len(matched_ious) / max(len(gt_entries), 1)

    # Classification accuracy (for matched rooms)
    type_correct = 0
    pub_correct = 0
    matched_count = 0
    for m in matches:
        if m["pred"] is None:
            continue
        matched_count += 1
        gt_type = m["gt"]["type"]
        pred_type = m["pred"].get("type", "unknown")
        if gt_type == pred_type:
            type_correct += 1
        gt_pub = m["gt"]["is_public"]
        pred_pub = pred_type in PUBLIC_TYPES
        if gt_pub == pred_pub:
            pub_correct += 1

    type_accuracy = type_correct / max(matched_count, 1)
    pub_accuracy = pub_correct / max(matched_count, 1)

    return {
        "gt_count": len(gt_entries),
        "detected_count": len(rooms),
        "matched_count": matched_count,
        "detection_rate": detection_rate,
        "mean_iou": mean_iou,
        "type_accuracy": type_accuracy,
        "pub_priv_accuracy": pub_accuracy,
        "per_room": matches,
    }


def run_evaluation(image_path: str, gt_path: str, use_ocr: bool = False):
    """Run full pipeline + evaluation on a single image."""
    # Run pipeline
    img, gray, binary = load_and_binarize(image_path)
    h, w = img.shape[:2]
    wall_data = detect_walls(binary)
    bounds = wall_data["building_bounds"]
    walls_closed = close_wall_gaps(wall_data["walls"], wall_data["building_bounds"])
    rooms, labels = segment_rooms(walls_closed, binary)

    matched_labels = []
    if use_ocr:
        texts = ocr_extract(binary)
        matched_labels = match_keywords(texts)

    classify_rooms(rooms, bounds, h, w, matched_labels)

    # Evaluate
    metrics = evaluate(rooms, gt_path)
    return metrics


def print_metrics(metrics: dict):
    """Print evaluation metrics."""
    print(f"\n{'='*50}")
    print("EVALUATION RESULTS")
    print(f"{'='*50}")
    print(f"  Ground truth rooms: {metrics['gt_count']}")
    print(f"  Detected rooms:     {metrics['detected_count']}")
    print(f"  Matched rooms:      {metrics['matched_count']}")
    print(f"  Detection rate:     {metrics['detection_rate']:.1%}")
    print(f"  Mean IoU:           {metrics['mean_iou']:.3f}")
    print(f"  Type accuracy:      {metrics['type_accuracy']:.1%}")
    print(f"  Public/Private acc: {metrics['pub_priv_accuracy']:.1%}")

    print(f"\n  Per-room details:")
    for m in metrics["per_room"]:
        gt = m["gt"]
        pred = m["pred"]
        iou = m["iou"]
        if pred:
            match = "✓" if gt["type"] == pred.get("type") else "✗"
            print(f"    {match} GT:{gt['type']:15s} → Pred:{pred.get('type', '?'):15s} IoU={iou:.2f}")
        else:
            print(f"    ✗ GT:{gt['type']:15s} → (unmatched) IoU={iou:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate pipeline against ground truth")
    parser.add_argument("image", help="Path to floor plan image")
    parser.add_argument("ground_truth", help="Path to ground truth JSON file")
    parser.add_argument("--ocr", action="store_true", help="Enable Tesseract OCR")
    args = parser.parse_args()

    if not os.path.exists(args.ground_truth):
        print(f"Error: ground truth file not found: {args.ground_truth}", file=sys.stderr)
        sys.exit(1)

    metrics = run_evaluation(args.image, args.ground_truth, use_ocr=args.ocr)
    print_metrics(metrics)


if __name__ == "__main__":
    main()
