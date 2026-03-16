"""Phase 4: Selective Erasure — white-out private spaces, keep public areas."""

import cv2
import numpy as np

from ocr_classify import PUBLIC_TYPES


def erase_private_areas(
    img: np.ndarray,
    binary: np.ndarray,
    rooms: list[dict],
    labels: np.ndarray,
    thick_walls: np.ndarray,
) -> np.ndarray:
    """Erase private spaces from the floor plan image.

    - Private rooms: fill with white
    - Structural walls: redraw on top (always visible)
    - Public room surroundings: restore original content
    - Large erased areas: label '非申報範圍'

    Args:
        img: Original color image.
        binary: Inverted binary image.
        rooms: Classified room dicts (must have 'type' key).
        labels: Pixel-level room label array.
        thick_walls: Structural wall mask.

    Returns:
        Erased image (copy of original with private areas blanked).
    """
    erased = img.copy()

    # Step 1: White out all private / non-public rooms
    for r in rooms:
        if r["type"] not in PUBLIC_TYPES and r["type"] != "annotation":
            mask = labels == r["label"]
            erased[mask] = (255, 255, 255)

    # Step 2: Redraw structural walls (always visible)
    erased[thick_walls > 0] = (0, 0, 0)

    # Step 3: Restore original content around public rooms
    for r in rooms:
        if r["type"] in PUBLIC_TYPES:
            room_mask = (labels == r["label"]).astype(np.uint8) * 255
            dilated = cv2.dilate(room_mask, np.ones((12, 12), np.uint8))
            restore = cv2.bitwise_and(binary, dilated)
            erased[restore > 0] = (0, 0, 0)

    # Step 4: Add '非申報範圍' labels in large erased areas
    for r in rooms:
        if r["type"] in ("private_large", "bedroom", "private") and r["rel_area"] > 0.01:
            cx, cy = int(r["centroid"][0]), int(r["centroid"][1])
            cv2.putText(
                erased, "Non-filing",
                (cx - 60, cy), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (170, 170, 170), 1, cv2.LINE_AA,
            )

    return erased
