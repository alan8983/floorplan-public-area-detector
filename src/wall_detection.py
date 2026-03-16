"""Phase 2A: Wall Detection — extract structural and partition walls.

Key insight (from v2 failure): walls MUST be extracted from the original
binary image. Pre-filtering text/annotations before wall detection will
remove thin partition walls along with dimension lines.

Strategy: use building footprint (derived from thick walls) to separate
dimension lines (outside footprint) from partition walls (inside footprint).
"""

import cv2
import numpy as np


# Morphological opening lengths for wall detection (pixels).
WALL_LENGTHS = [20, 30, 50, 80]

# Minimum thickness (px) to qualify as a structural/exterior wall.
THICK_WALL_MIN = 3

# Margin (px) inside building footprint for thin wall filtering.
FOOTPRINT_MARGIN = 20


def detect_walls(binary: np.ndarray) -> dict:
    """Detect walls from a binarized floor plan image.

    Args:
        binary: Inverted binary image (ink pixels = 255).

    Returns:
        dict with keys:
            thick_walls:     structural / exterior wall mask
            thin_walls:      partition wall mask (inside building only)
            walls:           combined wall mask
            building_bounds: (top, bottom, left, right) of building footprint
    """
    h, w = binary.shape[:2]

    # Horizontal walls (multi-scale)
    walls_h = np.zeros_like(binary)
    for length in WALL_LENGTHS:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (length, 1))
        walls_h = cv2.bitwise_or(walls_h, cv2.morphologyEx(binary, cv2.MORPH_OPEN, k))

    # Vertical walls (multi-scale)
    walls_v = np.zeros_like(binary)
    for length in WALL_LENGTHS:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, length))
        walls_v = cv2.bitwise_or(walls_v, cv2.morphologyEx(binary, cv2.MORPH_OPEN, k))

    walls_raw = cv2.bitwise_or(walls_h, walls_v)

    # Thick walls: survive perpendicular erosion of THICK_WALL_MIN px
    kv = np.ones((THICK_WALL_MIN, 1), np.uint8)
    walls_h_thick = cv2.dilate(cv2.erode(walls_h, kv), kv)

    kh = np.ones((1, THICK_WALL_MIN), np.uint8)
    walls_v_thick = cv2.dilate(cv2.erode(walls_v, kh), kh)

    thick_walls = cv2.bitwise_or(walls_h_thick, walls_v_thick)

    # Building footprint from thick wall coordinates (P2/P98)
    coords = np.where(thick_walls > 0)
    if len(coords[0]) > 100:
        bt = max(int(np.percentile(coords[0], 2)), 0)
        bb = min(int(np.percentile(coords[0], 98)), h)
        bl = max(int(np.percentile(coords[1], 2)), 0)
        br = min(int(np.percentile(coords[1], 98)), w)
    else:
        bt, bb = int(h * 0.1), int(h * 0.9)
        bl, br = int(w * 0.1), int(w * 0.9)

    bounds = (bt, bb, bl, br)

    # Thin walls only inside building footprint
    thin_walls = cv2.subtract(walls_raw, thick_walls)
    bldg_mask = np.zeros_like(binary)
    m = FOOTPRINT_MARGIN
    bldg_mask[bt + m : bb - m, bl + m : br - m] = 255
    thin_interior = cv2.bitwise_and(thin_walls, bldg_mask)

    walls = cv2.bitwise_or(thick_walls, thin_interior)

    return {
        "thick_walls": thick_walls,
        "thin_walls": thin_interior,
        "walls": walls,
        "building_bounds": bounds,
    }


def close_wall_gaps(walls: np.ndarray) -> np.ndarray:
    """Close door-width gaps and corner disconnections in the wall mask.

    Uses directional closing to bridge gaps without merging parallel walls.
    """
    # 1. Dilate to connect at corners/intersections
    wc = cv2.dilate(walls, np.ones((5, 5), np.uint8), iterations=1)

    # 2. Directional closing (bridge door-width gaps ~25px)
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)))
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)))

    # 3. Small diagonal/corner gaps
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    # 4. Remove tiny wall fragments
    wc = cv2.morphologyEx(wc, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    return wc
