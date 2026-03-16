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

# Door gap closing parameters (for ~3000px wide images at 1:100 scale).
# Standard single door ~80-90cm = 80-90px at 1:100.
SINGLE_DOOR_GAP = 90

# 8 endpoint kernels for morphological hit-or-miss transform.
# Each detects wall pixels with exactly one neighbor in a specific direction.
_ENDPOINT_KERNELS = []
for _base in [
    np.array([[0, 0, 0], [0, 1, 0], [0, 1, 0]], np.uint8),  # top endpoint
    np.array([[0, 0, 0], [0, 1, 0], [0, 0, 1]], np.uint8),  # top-left endpoint
]:
    for _rot in range(4):
        _ENDPOINT_KERNELS.append(np.rot90(_base, _rot))


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


# ──────────────────────────────────────────────
# Gap closing
# ──────────────────────────────────────────────

def _find_wall_endpoints(walls: np.ndarray) -> np.ndarray:
    """Find wall endpoint pixels using morphological hit-or-miss transform.

    Endpoints are wall pixels that have exactly one wall neighbor,
    indicating the end of a wall segment (potential door gap location).
    """
    # Skeletonize the wall mask to get 1px-wide lines
    skeleton = _morphological_skeleton(walls)

    endpoints = np.zeros_like(walls)
    for kernel in _ENDPOINT_KERNELS:
        hit = cv2.morphologyEx(skeleton, cv2.MORPH_HITMISS, kernel)
        endpoints = cv2.bitwise_or(endpoints, hit)

    return endpoints


def _morphological_skeleton(binary: np.ndarray) -> np.ndarray:
    """Compute morphological skeleton (no opencv-contrib needed)."""
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    skel = np.zeros_like(binary)
    temp = binary.copy()

    while True:
        eroded = cv2.erode(temp, element)
        opened = cv2.dilate(eroded, element)
        diff = cv2.subtract(temp, opened)
        skel = cv2.bitwise_or(skel, diff)
        temp = eroded.copy()
        if cv2.countNonZero(temp) == 0:
            break

    return skel


def _bridge_gaps_at_endpoints(walls: np.ndarray, max_gap: int = SINGLE_DOOR_GAP) -> np.ndarray:
    """Bridge wall gaps only near detected endpoints (door-width gaps).

    This avoids over-closing parallel walls (e.g., between adjacent bathrooms)
    by restricting large closing kernels to areas near wall endpoints.
    """
    endpoints = _find_wall_endpoints(walls)

    # Dilate endpoints to create "bridge zones" where closing is allowed
    bridge_zone = cv2.dilate(endpoints, np.ones((max_gap, max_gap), np.uint8))

    # Apply large directional closing on the full wall mask
    closed_h = cv2.morphologyEx(
        walls, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max_gap, 3))
    )
    closed_v = cv2.morphologyEx(
        walls, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, max_gap))
    )

    # Only keep new wall pixels that fall within bridge zones
    new_h = cv2.subtract(closed_h, walls)
    new_v = cv2.subtract(closed_v, walls)
    bridged = cv2.bitwise_or(
        cv2.bitwise_and(new_h, bridge_zone),
        cv2.bitwise_and(new_v, bridge_zone),
    )

    return cv2.bitwise_or(walls, bridged)


def _connect_walls_to_boundary(walls: np.ndarray, building_bounds: tuple) -> np.ndarray:
    """Connect wall segments near the building boundary to the boundary itself.

    Fixes edge rooms (balconies, etc.) that leak to exterior through small
    gaps between walls and the building outline.
    """
    bt, bb, bl, br = building_bounds
    h, w = walls.shape[:2]
    result = walls.copy()

    # Draw building boundary rectangle on the wall mask
    cv2.rectangle(result, (bl, bt), (br, bb), 255, thickness=2)

    # Close small gaps in narrow strips along each boundary edge
    margin = 15
    strips = [
        (max(bt - margin, 0), min(bt + margin, h), bl, br),  # top
        (max(bb - margin, 0), min(bb + margin, h), bl, br),  # bottom
        (bt, bb, max(bl - margin, 0), min(bl + margin, w)),   # left
        (bt, bb, max(br - margin, 0), min(br + margin, w)),   # right
    ]
    for y1, y2, x1, x2 in strips:
        if y2 <= y1 or x2 <= x1:
            continue
        roi = result[y1:y2, x1:x2]
        result[y1:y2, x1:x2] = cv2.morphologyEx(
            roi, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)
        )

    return result


def _close_wall_gaps_legacy(walls: np.ndarray) -> np.ndarray:
    """Original v3 gap closing (preserved for A/B comparison).

    Uses fixed 25px directional closing — under-closes doors (~80-90px gaps).
    """
    wc = cv2.dilate(walls, np.ones((5, 5), np.uint8), iterations=1)
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)))
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)))
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    wc = cv2.morphologyEx(wc, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return wc


def close_wall_gaps(walls: np.ndarray, building_bounds: tuple = None) -> np.ndarray:
    """Close door-width gaps and corner disconnections in the wall mask.

    Uses endpoint-targeted bridging to close door-width gaps (~80-90px)
    without merging parallel thin walls (e.g., between adjacent bathrooms).

    Args:
        walls: Combined wall mask from detect_walls().
        building_bounds: (top, bottom, left, right) of building footprint.
            If provided, also connects walls to the boundary.
    """
    # 0. Connect walls to building boundary (fixes edge room leakage)
    if building_bounds is not None:
        wc = _connect_walls_to_boundary(walls, building_bounds)
    else:
        wc = walls.copy()

    # 1. Dilate to connect at corners/intersections (unchanged from v3)
    wc = cv2.dilate(wc, np.ones((5, 5), np.uint8), iterations=1)

    # 2. Small diagonal/corner gaps (unchanged from v3)
    wc = cv2.morphologyEx(wc, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    # 3. Targeted door-gap bridging at wall endpoints (NEW in v5)
    wc = _bridge_gaps_at_endpoints(wc, max_gap=SINGLE_DOOR_GAP)

    # 4. Remove tiny wall fragments (unchanged from v3)
    wc = cv2.morphologyEx(wc, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    return wc
