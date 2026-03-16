"""Phase 2B: Room Segmentation — flood-fill to find enclosed spaces."""

import cv2
import numpy as np


# Minimum / maximum room area as fraction of total image area.
MIN_ROOM_AREA_RATIO = 0.002
MAX_ROOM_AREA_RATIO = 0.20

# Over-merge detection thresholds.
SPLIT_AREA_THRESHOLD = 0.04      # rooms > 4% of image are likely merged
SPLIT_SOLIDITY_THRESHOLD = 0.65  # low solidity suggests non-convex merged shape


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

    # Post-segmentation: try to split over-merged rooms
    split_occurred = False
    for r in rooms:
        if r["rel_area"] > SPLIT_AREA_THRESHOLD and r["solidity"] < SPLIT_SOLIDITY_THRESHOLD:
            mask_i = (labels == r["label"]).astype(np.uint8) * 255
            split_mask = _try_split_merged_room(mask_i)
            if split_mask is not None:
                interior[labels == r["label"]] = 0
                interior = cv2.bitwise_or(interior, split_mask)
                split_occurred = True

    if split_occurred:
        # Re-run connected components after splitting
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(interior, connectivity=4)
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
            mask_i = (labels == i).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_i, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            solidity = 0.0
            if contours:
                hull = cv2.convexHull(contours[0])
                hull_area = cv2.contourArea(hull)
                solidity = area / max(hull_area, 1)
            content = cv2.bitwise_and(binary, mask_i)
            content_ratio = cv2.countNonZero(content) / max(area, 1)
            rooms.append({
                "label": i, "area": area,
                "bbox": (rx, ry, rw, rh), "centroid": (cx, cy),
                "aspect_ratio": round(rw / max(rh, 1), 2),
                "solidity": round(solidity, 2),
                "content_ratio": round(content_ratio, 3),
                "rel_x": round(cx / w, 3), "rel_y": round(cy / h, 3),
                "rel_area": round(area / img_area, 4),
            })
        rooms.sort(key=lambda r: r["area"], reverse=True)

    return rooms, labels


def _try_split_merged_room(mask: np.ndarray) -> np.ndarray | None:
    """Try to split a room mask that appears to be two merged rooms.

    Finds the narrowest cross-section (the merge point / door gap)
    by analyzing projection profiles, and inserts a cut line there.

    Returns modified mask if a split was found, None otherwise.
    """
    # Project mask onto X and Y axes
    proj_y = np.sum(mask, axis=1).astype(float)  # horizontal projection
    proj_x = np.sum(mask, axis=0).astype(float)  # vertical projection

    for proj, axis in [(proj_y, 0), (proj_x, 1)]:
        if proj.max() == 0:
            continue

        # Find local minima (narrow passages) using simple scan
        cut_pos = _find_best_cut(proj)
        if cut_pos is not None:
            result = mask.copy()
            if axis == 0:  # cut horizontal line
                result[cut_pos - 1:cut_pos + 2, :] = 0
            else:          # cut vertical line
                result[:, cut_pos - 1:cut_pos + 2] = 0
            # Verify the cut actually splits into 2+ components
            n_after = cv2.connectedComponents(result)[0] - 1
            if n_after >= 2:
                return result

    return None


def _find_best_cut(proj: np.ndarray, min_distance: int = 50) -> int | None:
    """Find the best cut position in a 1D projection profile.

    Looks for the deepest local minimum that is narrow enough
    relative to the maximum width to indicate a merge point.
    """
    max_val = proj.max()
    if max_val == 0:
        return None

    # Find non-zero range
    nonzero = np.where(proj > 0)[0]
    if len(nonzero) < min_distance * 2:
        return None
    start, end = nonzero[0], nonzero[-1]

    # Search for local minima in the interior (skip edges)
    search_start = start + min_distance
    search_end = end - min_distance
    if search_start >= search_end:
        return None

    region = proj[search_start:search_end]
    if len(region) == 0:
        return None

    # Smooth to avoid noise
    kernel_size = min(15, len(region) // 2 * 2 + 1)
    if kernel_size >= 3:
        smoothed = np.convolve(region, np.ones(kernel_size) / kernel_size, mode='same')
    else:
        smoothed = region

    # Find the deepest valley
    min_idx = np.argmin(smoothed)
    min_val = smoothed[min_idx]

    # Only cut if the minimum is significantly narrower than the max
    if min_val < max_val * 0.3:
        return int(search_start + min_idx)

    return None
