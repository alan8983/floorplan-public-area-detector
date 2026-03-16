"""Phase 3: OCR Text Recognition + Room Classification.

Classification priority:
  1. OCR keyword match (highest confidence)
  2. Geometric feature rules (fallback)
"""

import cv2
import numpy as np

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# ──────────────────────────────────────────────
# Keyword dictionaries
# ──────────────────────────────────────────────

PUBLIC_KEYWORDS = {
    "樓梯": "stairwell", "梯間": "stairwell", "安全梯": "stairwell",
    "ST": "stairwell", "STAIR": "stairwell",
    "電梯": "elevator", "EV": "elevator", "EL": "elevator",
    "走廊": "corridor", "走道": "corridor", "通道": "corridor",
    "大廳": "lobby", "門廳": "lobby", "梯廳": "lobby",
    "HALL": "lobby", "LOBBY": "lobby",
    "機電": "mechanical", "機械": "mechanical", "機電空間": "mechanical",
}

PRIVATE_KEYWORDS = {
    "客廳": "living_room", "餐廳": "kitchen", "廚房": "kitchen",
    "臥室": "bedroom", "主臥": "bedroom", "臥": "bedroom",
    "浴室": "bathroom", "廁所": "bathroom", "衛浴": "bathroom",
    "陽台": "balcony", "陽臺": "balcony",
    "儲藏": "storage", "玄關": "entrance",
    "廚": "kitchen",
}

ANNOTATION_KEYWORDS = {
    "地界線": "annotation", "建築線": "annotation",
    "地界": "annotation", "平面圖": "annotation",
    "計入": "annotation", "面積": "annotation",
}

ALL_KEYWORDS = {**PUBLIC_KEYWORDS, **PRIVATE_KEYWORDS, **ANNOTATION_KEYWORDS}

PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}

TYPE_LABELS_ZH = {
    "stairwell": "樓梯間", "elevator": "電梯", "corridor": "走廊",
    "lobby": "梯廳/門廳", "mechanical": "機電空間",
    "living_room": "客廳", "kitchen": "餐廳/廚房", "bedroom": "臥室",
    "bathroom": "浴室", "balcony": "陽台", "storage": "儲藏室",
    "entrance": "玄關", "private_large": "私有空間(大)",
    "private": "私有空間", "annotation": "標註",
}


# ──────────────────────────────────────────────
# OCR extraction
# ──────────────────────────────────────────────

def ocr_extract(binary: np.ndarray) -> list[dict]:
    """Run Tesseract OCR on the floor plan and return text blocks with positions.

    Args:
        binary: Inverted binary image (ink=white).

    Returns:
        List of dicts with keys: text, conf, cx, cy, x, y, w, h
    """
    if not HAS_TESSERACT:
        return []

    # Tesseract prefers white-bg black-text
    ocr_img = cv2.bitwise_not(binary)
    config = r"--oem 3 --psm 11 -l chi_tra+eng"
    data = pytesseract.image_to_data(ocr_img, config=config, output_type=pytesseract.Output.DICT)

    texts = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if text and conf > 20:
            x, y = data["left"][i], data["top"][i]
            tw, th = data["width"][i], data["height"][i]
            texts.append({
                "text": text, "conf": conf,
                "x": x, "y": y, "w": tw, "h": th,
                "cx": x + tw // 2, "cy": y + th // 2,
            })
    return texts


def match_keywords(texts: list[dict]) -> list[dict]:
    """Match OCR texts to room-type keywords."""
    matched = []
    for t in texts:
        txt = t["text"]
        for keyword, room_type in ALL_KEYWORDS.items():
            if keyword in txt or txt in keyword:
                matched.append({
                    "text": txt, "keyword": keyword, "type": room_type,
                    "is_public": keyword in PUBLIC_KEYWORDS,
                    "cx": t["cx"], "cy": t["cy"], "conf": t["conf"],
                })
                break
    return matched


# ──────────────────────────────────────────────
# Classification
# ──────────────────────────────────────────────

def _find_ocr_in_room(room: dict, matched_labels: list[dict], margin: int = 30) -> list[dict]:
    """Find OCR labels that fall inside or near a room bbox."""
    rx, ry, rw, rh = room["bbox"]
    return [
        m for m in matched_labels
        if rx - margin <= m["cx"] <= rx + rw + margin
        and ry - margin <= m["cy"] <= ry + rh + margin
    ]


def classify_rooms(
    rooms: list[dict],
    building_bounds: tuple,
    img_h: int,
    img_w: int,
    matched_labels: list[dict] | None = None,
) -> list[dict]:
    """Classify each room as public or private.

    Mutates rooms in-place by adding keys: type, type_zh, reason.

    Args:
        rooms: Room dicts from segmentation.
        building_bounds: (top, bottom, left, right) of building footprint.
        img_h, img_w: Image dimensions.
        matched_labels: OCR keyword matches (optional).

    Returns:
        The same rooms list (mutated).
    """
    bt, bb, bl, br = building_bounds
    matched_labels = matched_labels or []

    for r in rooms:
        a = r["rel_area"]
        asp = r["aspect_ratio"]
        sol = r["solidity"]
        con = r["content_ratio"]
        rx, ry = r["rel_x"], r["rel_y"]

        # --- OCR-first classification ---
        ocr_hits = _find_ocr_in_room(r, matched_labels)
        if ocr_hits:
            public_hits = [h for h in ocr_hits if h["is_public"]]
            private_hits = [h for h in ocr_hits if not h["is_public"] and h["type"] != "annotation"]
            if public_hits:
                best = max(public_hits, key=lambda x: x["conf"])
                r["type"] = best["type"]
                r["type_zh"] = TYPE_LABELS_ZH.get(best["type"], best["type"])
                r["reason"] = f"OCR:'{best['text']}'"
                continue
            if private_hits:
                best = max(private_hits, key=lambda x: x["conf"])
                r["type"] = best["type"]
                r["type_zh"] = TYPE_LABELS_ZH.get(best["type"], best["type"])
                r["reason"] = f"OCR:'{best['text']}'"
                continue

        # --- Geometric fallback (v5: position-independent) ---
        rbt, rbb = bt / img_h, bb / img_h

        # Annotation: extreme aspect ratio near building margins
        if ry < rbt + 0.02 or ry > rbb - 0.02:
            if asp > 4 or asp < 0.25:
                _set(r, "annotation"); continue

        # Corridor: very elongated, inside building
        if (asp > 3.5 or asp < 0.28) and a < 0.02:
            if rbt + 0.05 < ry < rbb - 0.05:
                _set(r, "corridor", "geo:elongated"); continue

        # Stairwell: high content density (tread lines) + medium size
        if 0.003 < a < 0.03 and con > 0.12 and 0.3 < asp < 3.0:
            _set(r, "stairwell", "geo:high_content"); continue

        # Elevator: very small, roughly square
        if a < 0.006 and 0.4 < asp < 2.5:
            _set(r, "elevator", "geo:small_square"); continue

        # Mechanical: small, high solidity (enclosed box)
        if 0.003 < a < 0.012 and sol > 0.7:
            _set(r, "mechanical", "geo:small_solid"); continue

        # Lobby: medium size, high solidity (open space)
        if 0.008 < a < 0.04 and sol > 0.5:
            _set(r, "lobby", "geo:medium_solid"); continue

        # Large room → private
        if a > 0.025:
            _set(r, "private_large", "geo:large"); continue

        # Default: private
        _set(r, "private", "geo:default")

    return rooms


def _set(r: dict, type_en: str, reason: str = "geo:margin"):
    r["type"] = type_en
    r["type_zh"] = TYPE_LABELS_ZH.get(type_en, type_en)
    r["reason"] = reason
