"""Phase 2B: Room Segmentation — flood-fill to find enclosed spaces."""

import cv2
import numpy as np


# Minimum / maximum room area as fraction of total image area.
MIN_ROOM_AREA_RATIO = 0.002
MAX_ROOM_AREA_RATIO = 0.20


def segment_rooms(walls_closed: np.ndarray, binary: np.ndarray) -> tuple:
    """Segment a floor plan into individual rooms using closed wall mask.

    Args:
        walls_closed: Wall mask after gap closing.
        binary: Original binarized image (for content density calculation).

    Returns:
        (rooms, labels) where:
            rooms: list of dicts with room features
            labels: pixel-level label array (same shape as input)
    """
    h, w = walls_closed.shape[:2]
    img_area = h * w

    # Invert: enclosed spaces become white
    inv = cv2.bitwise_not(walls_closed)

    # Flood-fill exterior from all edges
    flood = inv.copy()
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    for x in range(0, w, 2):
        if flood[0, x] == 255:
            cv2.floodFill(flood, flood_mask, (x, 0), 128)
        if flood[h - 1, x] == 255:
            cv2.floodFill(flood, flood_mask, (x, h - 1), 128)
    for y in range(0, h, 2):
        if flood[y, 0] == 255:
            cv2.floodFill(flood, flood_mask, (0, y), 128)
        if flood[y, w - 1] == 255:
            cv2.floodFill(flood, flood_mask, (w - 1, y), 128)

    # Interior spaces only
    interior = np.where(flood == 255, 255, 0).astype(np.uint8)
    interior = cv2.morphologyEx(interior, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    # Connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(interior, connectivity=4)

    min_area = img_area * MIN_ROOM_AREA_RATIO
    max_area = img_area * MAX_ROOM_AREA_RATIO

    rooms = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if not (min_area < area < max_area):
            continue

        rx = int(stats[i, cv2.CC_STAT_LEFT])
        ry = int(stats[i, cv2.CC_STAT_TOP])
        rw = int(stats[i, cv2.CC_STAT_WIDTH])
        rh = int(stats[i, cv2.CC_STAT_HEIGHT])
        cx, cy = float(centroids[i][0]), float(centroids[i][1])

        # Shape features
        mask_i = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_i, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        solidity = 0.0
        if contours:
            hull = cv2.convexHull(contours[0])
            hull_area = cv2.contourArea(hull)
            solidity = area / max(hull_area, 1)

        # Content density (original ink inside this room)
        content = cv2.bitwise_and(binary, mask_i)
        content_ratio = cv2.countNonZero(content) / max(area, 1)

        rooms.append({
            "label": i,
            "area": area,
            "bbox": (rx, ry, rw, rh),
            "centroid": (cx, cy),
            "aspect_ratio": round(rw / max(rh, 1), 2),
            "solidity": round(solidity, 2),
            "content_ratio": round(content_ratio, 3),
            "rel_x": round(cx / w, 3),
            "rel_y": round(cy / h, 3),
            "rel_area": round(area / img_area, 4),
        })

    rooms.sort(key=lambda r: r["area"], reverse=True)
    return rooms, labels
