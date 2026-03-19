"""Pipeline UI wrapper — 回傳結構化 dict 供 Streamlit 消費。

不改動原 run_pipeline()，獨立包裝一層。
所有圖片統一轉為 RGB，灰階 mask 轉為 3-channel。
"""

import os
import sys
import time
import traceback

import cv2
import numpy as np

# 確保 src/ 下的模組可被 import
sys.path.insert(0, os.path.dirname(__file__))

from preprocessing import load_and_binarize, image_stats
from wall_detection import detect_walls, close_wall_gaps
from segmentation import segment_rooms
from ocr_classify import PUBLIC_TYPES, ocr_extract, match_keywords, classify_rooms
from eraser import erase_private_areas
from visualize import draw_classification, draw_zones


def _to_rgb(img: np.ndarray) -> np.ndarray:
    """BGR → RGB，灰階 → 3-channel RGB。"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def run_pipeline_ui(image_path: str, use_ocr: bool = False) -> dict:
    """執行完整 pipeline，回傳結構化結果。

    Args:
        image_path: 圖檔路徑
        use_ocr: 是否啟用 OCR 分類

    Returns:
        dict with keys:
            images: dict of name → RGB np.ndarray
            rooms: list[dict]
            metrics: dict
            error: str or None
    """
    try:
        return _run_pipeline_core(image_path, use_ocr)
    except Exception as e:
        return {
            "images": {},
            "rooms": [],
            "metrics": {},
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        }


def _run_pipeline_core(image_path: str, use_ocr: bool) -> dict:
    """實際 pipeline 邏輯（無 try/except，由外層包裝）。"""
    t0 = time.time()

    # ── Phase 1: Preprocessing ──
    img, gray, binary = load_and_binarize(image_path)
    h, w = img.shape[:2]

    # ── Phase 2A: Wall detection ──
    wall_data = detect_walls(binary)
    thick_walls = wall_data["thick_walls"]
    bounds = wall_data["building_bounds"]

    # ── Phase 2B: Gap closing + segmentation ──
    walls_closed = close_wall_gaps(wall_data["walls"], bounds)
    rooms, labels = segment_rooms(walls_closed, binary)

    # 品質指標
    bt, bb, bl, br = bounds
    building_area = max((bb - bt) * (br - bl), 1)
    segmented_area = sum(r["area"] for r in rooms)
    coverage = segmented_area / building_area
    largest_rel_area = max((r["rel_area"] for r in rooms), default=0)
    avg_solidity = sum(r["solidity"] for r in rooms) / max(len(rooms), 1)

    # ── Phase 3: Classification ──
    matched_labels = []
    if use_ocr:
        texts = ocr_extract(binary)
        matched_labels = match_keywords(texts)

    classify_rooms(rooms, bounds, h, w, matched_labels)

    n_pub = sum(1 for r in rooms if r["type"] in PUBLIC_TYPES)
    n_priv = sum(1 for r in rooms if r["type"] not in PUBLIC_TYPES and r["type"] != "annotation")

    # ── Phase 4: Generate visualizations ──
    vis_class = draw_classification(img, rooms, labels)
    vis_zones = draw_zones(img, rooms, labels)
    erased = erase_private_areas(img, binary, rooms, labels, thick_walls)

    elapsed = time.time() - t0

    # 所有圖片統一轉 RGB
    images = {
        "original": _to_rgb(img),
        "walls_thick": _to_rgb(thick_walls),
        "walls_closed": _to_rgb(walls_closed),
        "classification": _to_rgb(vis_class),
        "zones": _to_rgb(vis_zones),
        "erased": _to_rgb(erased),
    }

    metrics = {
        "room_count": len(rooms),
        "coverage": coverage,
        "avg_solidity": avg_solidity,
        "largest_rel_area": largest_rel_area,
        "n_public": n_pub,
        "n_private": n_priv,
        "elapsed": elapsed,
        "dimensions": f"{w}x{h}",
    }

    return {
        "images": images,
        "rooms": rooms,
        "metrics": metrics,
        "error": None,
    }
