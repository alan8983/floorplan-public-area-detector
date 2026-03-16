"""Phase 1: Image Preprocessing — binarization, grayscale conversion."""

import cv2
import numpy as np


def load_and_binarize(image_path: str) -> tuple:
    """Load image and produce Otsu-binarized version.

    Returns:
        (img_color, gray, binary) where binary is inverted (ink=white).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return img, gray, binary


def image_stats(gray: np.ndarray) -> dict:
    """Compute basic image statistics for quality assessment."""
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    total = hist.sum()
    return {
        "white_ratio": float(hist[200:].sum() / total),
        "black_ratio": float(hist[:50].sum() / total),
        "dimensions": f"{gray.shape[1]}x{gray.shape[0]}",
    }
