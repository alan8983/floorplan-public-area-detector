#!/usr/bin/env python3
"""Main pipeline — CLI entry point.

Usage (from repo root):
    python src/pipeline.py samples/sample1_input_residential_3F.jpg -o output/
    python src/pipeline.py samples/sample1_input_residential_3F.jpg -o output/ --ocr
    python src/pipeline.py samples/sample1_input_residential_3F.jpg --analyze-only
"""

import argparse
import os
import sys
import time

# Allow running as `python src/pipeline.py` from repo root
sys.path.insert(0, os.path.dirname(__file__))

import cv2

from preprocessing import load_and_binarize, image_stats
from wall_detection import detect_walls, close_wall_gaps
from segmentation import segment_rooms
from ocr_classify import PUBLIC_TYPES, ocr_extract, match_keywords, classify_rooms
from eraser import erase_private_areas
from visualize import draw_classification, draw_zones


def run_pipeline(input_path: str, output_dir: str, use_ocr: bool = False,
                 analyze_only: bool = False, use_ml_detect: bool = False):
    os.makedirs(output_dir, exist_ok=True)
    t0 = time.time()

    # ── Phase 1: Preprocessing ──
    print(f"[Phase 1] Loading {input_path} ...")
    img, gray, binary = load_and_binarize(input_path)
    h, w = img.shape[:2]
    stats = image_stats(gray)
    print(f"  {stats['dimensions']}, white={stats['white_ratio']:.1%}, black={stats['black_ratio']:.1%}")

    # ── Phase 2A: Wall detection ──
    print("\n[Phase 2A] Wall detection ...")
    wall_data = detect_walls(binary)
    thick_walls = wall_data["thick_walls"]
    bounds = wall_data["building_bounds"]
    print(f"  Building bounds: ({bounds[2]},{bounds[0]}) to ({bounds[3]},{bounds[1]})")
    print(f"  Thick wall px: {cv2.countNonZero(thick_walls)}")
    print(f"  Total wall px: {cv2.countNonZero(wall_data['walls'])}")

    # ── Phase 2B: Gap closing + segmentation ──
    if use_ml_detect:
        # ML detection slot (future: YOLO object detection)
        print("\n[Phase 2B] ML detection mode (not yet implemented) ...")
        print("  ⚠ ML detection module not available, falling back to CV pipeline")

    print("\n[Phase 2B] Gap closing + room segmentation ...")
    walls_closed = close_wall_gaps(wall_data["walls"], wall_data["building_bounds"])
    rooms, labels = segment_rooms(walls_closed, binary)

    # Per-stage quality metrics (Phase 2B)
    bt, bb, bl, br = bounds
    building_area = max((bb - bt) * (br - bl), 1)
    segmented_area = sum(r["area"] for r in rooms)
    coverage = segmented_area / building_area
    largest_rel_area = max((r["rel_area"] for r in rooms), default=0)
    avg_solidity = sum(r["solidity"] for r in rooms) / max(len(rooms), 1)

    print(f"  Rooms detected: {len(rooms)}")
    print(f"  Coverage: {coverage:.1%} of building interior")
    print(f"  Largest room: {largest_rel_area:.4f} rel_area" +
          (" (⚠ likely merged)" if largest_rel_area > 0.04 else ""))
    print(f"  Avg solidity: {avg_solidity:.2f}")
    if coverage < 0.60:
        print("  ⚠ Low coverage: segmentation may be incomplete")

    # ── Phase 3: Classification ──
    matched_labels = []
    if use_ocr:
        print("\n[Phase 3] OCR extraction ...")
        texts = ocr_extract(binary)
        print(f"  OCR text blocks: {len(texts)}")
        matched_labels = match_keywords(texts)
        print(f"  Keyword matches: {len(matched_labels)}")
        for m in matched_labels:
            pub = "★" if m["is_public"] else " "
            print(f"    {pub} '{m['text']}' -> {m['type']} ({m['keyword']})")

    print(f"\n[Phase 3] Classification ({'OCR+geometry' if use_ocr else 'geometry only'}) ...")
    classify_rooms(rooms, bounds, h, w, matched_labels)

    n_pub = sum(1 for r in rooms if r["type"] in PUBLIC_TYPES)
    n_priv = sum(1 for r in rooms if r["type"] not in PUBLIC_TYPES and r["type"] != "annotation")
    n_ocr = sum(1 for r in rooms if r.get("reason", "").startswith("OCR"))
    n_geo = sum(1 for r in rooms if r.get("reason", "").startswith("geo"))
    print(f"  Public: {n_pub}, Private: {n_priv}")
    print(f"  Classification: {n_ocr} OCR hits, {n_geo} geometry fallback")
    for i, r in enumerate(rooms):
        p = "★" if r["type"] in PUBLIC_TYPES else " "
        zh = r.get("type_zh", r["type"])
        print(f"  {p}{i+1:2d}. {zh:10s} area={r['rel_area']:.4f} "
              f"asp={r['aspect_ratio']:.2f} pos=({r['rel_x']:.2f},{r['rel_y']:.2f}) "
              f"reason={r.get('reason', '?')}")

    if analyze_only:
        elapsed = time.time() - t0
        print(f"\nDone (analyze-only). {elapsed:.1f}s")
        return

    # ── Phase 4: Generate outputs ──
    print("\n[Phase 4] Generating outputs ...")

    vis_class = draw_classification(img, rooms, labels)
    cv2.imwrite(os.path.join(output_dir, "classification.png"), vis_class)

    vis_zones = draw_zones(img, rooms, labels)
    cv2.imwrite(os.path.join(output_dir, "zones.png"), vis_zones)

    erased = erase_private_areas(img, binary, rooms, labels, thick_walls)
    cv2.imwrite(os.path.join(output_dir, "erased.png"), erased)

    cv2.imwrite(os.path.join(output_dir, "walls_thick.png"), thick_walls)
    cv2.imwrite(os.path.join(output_dir, "walls_closed.png"), walls_closed)

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"DONE in {elapsed:.1f}s")
    print(f"  Rooms: {len(rooms)} ({n_pub} public, {n_priv} private)")
    print(f"  Output: {output_dir}/")
    for fname in ["classification.png", "zones.png", "erased.png"]:
        print(f"    {fname}")


def main():
    parser = argparse.ArgumentParser(description="Floor Plan Public Area Detector")
    parser.add_argument("input", help="Path to floor plan image")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    parser.add_argument("--ocr", action="store_true", help="Enable Tesseract OCR")
    parser.add_argument("--analyze-only", action="store_true", help="Analyze only, no output images")
    parser.add_argument("--ml-detect", action="store_true", help="Use ML detection (future, not yet implemented)")
    args = parser.parse_args()
    run_pipeline(args.input, args.output, use_ocr=args.ocr,
                 analyze_only=args.analyze_only, use_ml_detect=args.ml_detect)


if __name__ == "__main__":
    main()
