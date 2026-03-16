"""Visualization helpers — overlays, zone maps, debug images."""

import cv2
import numpy as np

from ocr_classify import PUBLIC_TYPES

COLORS = {
    "stairwell": (52, 168, 83), "elevator": (66, 133, 244),
    "corridor": (251, 188, 4), "lobby": (171, 71, 188),
    "mechanical": (0, 172, 193), "living_room": (215, 200, 200),
    "kitchen": (225, 215, 200), "bedroom": (200, 210, 225),
    "bathroom": (200, 225, 215), "balcony": (225, 225, 210),
    "private_large": (215, 210, 220), "private": (220, 220, 220),
    "annotation": (245, 245, 245),
}


def draw_classification(img: np.ndarray, rooms: list[dict], labels: np.ndarray) -> np.ndarray:
    """Draw room classification overlay with labels."""
    vis = img.copy()
    for r in rooms:
        if r["type"] == "annotation":
            continue
        mask = labels == r["label"]
        ov = vis.copy()
        ov[mask] = COLORS.get(r["type"], (220, 220, 220))
        alpha = 0.55 if r["type"] in PUBLIC_TYPES else 0.3
        vis = cv2.addWeighted(vis, 1 - alpha, ov, alpha, 0)
        cx, cy = int(r["centroid"][0]), int(r["centroid"][1])
        lbl = r.get("type_zh", r["type"])
        f = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(lbl, f, 0.5, 1)
        cv2.rectangle(vis, (cx - tw // 2 - 3, cy - th - 4), (cx + tw // 2 + 3, cy + 4), (255, 255, 255), -1)
        c = (0, 140, 0) if r["type"] in PUBLIC_TYPES else (120, 120, 120)
        cv2.putText(vis, lbl, (cx - tw // 2, cy), f, 0.5, c, 1, cv2.LINE_AA)
    return vis


def draw_zones(img: np.ndarray, rooms: list[dict], labels: np.ndarray) -> np.ndarray:
    """Draw public (green) vs private (pink) zone overlay."""
    h, w = img.shape[:2]
    vis = img.copy()
    pub = np.zeros((h, w), np.uint8)
    priv = np.zeros((h, w), np.uint8)
    for r in rooms:
        m = (labels == r["label"]).astype(np.uint8) * 255
        if r["type"] in PUBLIC_TYPES:
            pub = cv2.bitwise_or(pub, m)
        elif r["type"] != "annotation":
            priv = cv2.bitwise_or(priv, m)
    ov = vis.copy(); ov[pub > 0] = (60, 190, 110)
    vis = cv2.addWeighted(vis, 0.4, ov, 0.6, 0)
    ov = vis.copy(); ov[priv > 0] = (200, 180, 200)
    vis = cv2.addWeighted(vis, 0.55, ov, 0.45, 0)
    # Legend
    cv2.rectangle(vis, (10, h - 90), (350, h - 10), (255, 255, 255), -1)
    cv2.rectangle(vis, (10, h - 90), (350, h - 10), (0, 0, 0), 1)
    cv2.rectangle(vis, (20, h - 78), (45, h - 60), (60, 190, 110), -1)
    cv2.putText(vis, "PUBLIC (keep)", (55, h - 62), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.rectangle(vis, (20, h - 48), (45, h - 30), (200, 180, 200), -1)
    cv2.putText(vis, "PRIVATE (erase)", (55, h - 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return vis
