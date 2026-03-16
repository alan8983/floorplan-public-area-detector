"""Phase 4: Selective Erasure — white-out private spaces, keep public areas."""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ocr_classify import PUBLIC_TYPES


def _put_cjk_text(img: np.ndarray, text: str, position: tuple,
                   font_size: int = 20, color: tuple = (170, 170, 170)):
    """Draw CJK text on an OpenCV image using Pillow."""
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # Try common CJK fonts; fall back to default
    font = None
    font_candidates = [
        "NotoSansCJK-Regular.ttc",
        "NotoSansTC-Regular.otf",
        "msjh.ttc",        # Windows 微軟正黑體
        "msyh.ttc",        # Windows 微軟雅黑
        "SimHei.ttf",      # Windows 黑體
        "arial.ttf",       # fallback
    ]
    for fname in font_candidates:
        try:
            font = ImageFont.truetype(fname, font_size)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    draw.text(position, text, font=font, fill=color)
    result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    np.copyto(img, result)


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

    # Step 3: Restore original content around public rooms (dynamic margin)
    for r in rooms:
        if r["type"] in PUBLIC_TYPES:
            room_mask = (labels == r["label"]).astype(np.uint8) * 255
            # Dynamic margin based on room size: larger rooms get larger margin
            room_area = r["area"]
            margin = max(8, min(20, int(room_area ** 0.25)))
            dilated = cv2.dilate(room_mask, np.ones((margin, margin), np.uint8))
            restore = cv2.bitwise_and(binary, dilated)
            erased[restore > 0] = (0, 0, 0)

    # Step 4: Add '非申報範圍' labels in large erased areas (CJK text)
    for r in rooms:
        if r["type"] in ("private_large", "bedroom", "private") and r["rel_area"] > 0.01:
            cx, cy = int(r["centroid"][0]), int(r["centroid"][1])
            _put_cjk_text(erased, "非申報範圍", (cx - 50, cy - 10),
                          font_size=18, color=(170, 170, 170))

    return erased
