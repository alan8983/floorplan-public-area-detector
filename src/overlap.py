"""重疊解衝突模組 — 公區優先策略。

GT 標註允許重疊（方便手動標註不規則區域），此模組負責在
評估/YOLO 匯出時自動解衝突。

規則：
    1. 公區（stairwell, elevator, corridor, mechanical）優先
    2. 私區與公區重疊部分歸公區
    3. 公區之間重疊：保留兩者（YOLO 支援同類重疊）
    4. 私區剩餘面積 < 原面積 10% 時整個丟棄
"""

import numpy as np

PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "mechanical"}

# 私區被裁剪後，剩餘面積低於原面積此比例時丟棄
_MIN_REMAIN_RATIO = 0.10


def _bbox_to_slice(bbox: list) -> tuple:
    """[x, y, w, h] → (x1, y1, x2, y2)"""
    x, y, w, h = bbox
    return int(x), int(y), int(x + w), int(y + h)


def _bbox_overlap(a: list, b: list) -> float:
    """計算 a 被 b 覆蓋的比例 (overlap_area / area_a)。"""
    ax1, ay1, ax2, ay2 = _bbox_to_slice(a)
    bx1, by1, bx2, by2 = _bbox_to_slice(b)

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    return inter / max(area_a, 1)


def resolve_overlaps(
    annotations: list[dict],
    img_w: int = 0,
    img_h: int = 0,
) -> dict:
    """解衝突：公區優先，私區被公區裁剪。

    Args:
        annotations: GT 標註列表，每個含 bbox=[x,y,w,h], type, is_public
        img_w, img_h: 圖片尺寸（用於像素級 mask 計算，0 則僅做 bbox 級）

    Returns:
        {
            "resolved": 解衝突後的標註列表,
            "dropped": 被丟棄的私區列表,
            "stats": {
                "total_input": 輸入標註數,
                "total_output": 輸出標註數,
                "public_count": 公區數,
                "private_count": 私區數,
                "dropped_count": 丟棄數,
                "overlap_pairs": 重疊對數,
            }
        }
    """
    public_annots = [a for a in annotations if a.get("type", "private") in PUBLIC_TYPES]
    private_annots = [a for a in annotations if a.get("type", "private") not in PUBLIC_TYPES]

    resolved = []
    dropped = []
    overlap_pairs = 0

    # 公區全部保留
    for a in public_annots:
        resolved.append({**a, "is_public": True})

    # 私區逐一檢查與公區的重疊
    for priv in private_annots:
        priv_bbox = priv["bbox"]

        # 檢查此私區與所有公區的重疊
        has_overlap = False
        for pub in public_annots:
            overlap_ratio = _bbox_overlap(priv_bbox, pub["bbox"])
            if overlap_ratio > 0.01:  # > 1% 才算重疊
                has_overlap = True
                overlap_pairs += 1

        if not has_overlap:
            # 無重疊，直接保留
            resolved.append({**priv, "is_public": False})
            continue

        # 有重疊 → 用像素 mask 計算剩餘區域
        if img_w > 0 and img_h > 0:
            clipped = _clip_private_with_mask(priv_bbox, public_annots, img_w, img_h)
        else:
            clipped = _clip_private_bbox_only(priv_bbox, public_annots)

        if clipped is None:
            dropped.append(priv)
        else:
            resolved.append({
                **priv,
                "bbox": clipped,
                "is_public": False,
                "_clipped": True,  # 標記為被裁剪過
            })

    stats = {
        "total_input": len(annotations),
        "total_output": len(resolved),
        "public_count": len(public_annots),
        "private_count": len(private_annots),
        "dropped_count": len(dropped),
        "overlap_pairs": overlap_pairs,
    }

    return {"resolved": resolved, "dropped": dropped, "stats": stats}


def _clip_private_with_mask(
    priv_bbox: list,
    public_annots: list[dict],
    img_w: int,
    img_h: int,
) -> list | None:
    """用像素 mask 精確裁剪私區，回傳剩餘部分的 bbox。"""
    px1, py1, px2, py2 = _bbox_to_slice(priv_bbox)

    # Clamp to image bounds
    px1, py1 = max(0, px1), max(0, py1)
    px2, py2 = min(img_w, px2), min(img_h, py2)

    orig_area = (px2 - px1) * (py2 - py1)
    if orig_area <= 0:
        return None

    # 建立私區的 mask（局部座標）
    mask = np.ones((py2 - py1, px2 - px1), dtype=np.uint8)

    # 從 mask 中扣除所有公區重疊部分
    for pub in public_annots:
        bx1, by1, bx2, by2 = _bbox_to_slice(pub["bbox"])
        # 轉換為局部座標
        lx1 = max(0, bx1 - px1)
        ly1 = max(0, by1 - py1)
        lx2 = min(px2 - px1, bx2 - px1)
        ly2 = min(py2 - py1, by2 - py1)
        if lx2 > lx1 and ly2 > ly1:
            mask[ly1:ly2, lx1:lx2] = 0

    remain = int(mask.sum())
    if remain < orig_area * _MIN_REMAIN_RATIO:
        return None  # 剩餘太少，丟棄

    # 找剩餘部分的 bounding box
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return None

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    # 轉回全域座標
    new_bbox = [
        int(px1 + cmin),
        int(py1 + rmin),
        int(cmax - cmin + 1),
        int(rmax - rmin + 1),
    ]
    return new_bbox


def _clip_private_bbox_only(
    priv_bbox: list,
    public_annots: list[dict],
) -> list | None:
    """純 bbox 級裁剪（不需圖片尺寸，精度較低）。"""
    px1, py1, px2, py2 = _bbox_to_slice(priv_bbox)
    orig_area = (px2 - px1) * (py2 - py1)
    if orig_area <= 0:
        return None

    # 計算所有公區覆蓋的總面積比例
    total_overlap = 0
    for pub in public_annots:
        bx1, by1, bx2, by2 = _bbox_to_slice(pub["bbox"])
        ix1, iy1 = max(px1, bx1), max(py1, by1)
        ix2, iy2 = min(px2, bx2), min(py2, by2)
        if ix2 > ix1 and iy2 > iy1:
            total_overlap += (ix2 - ix1) * (iy2 - iy1)

    remain_ratio = 1 - total_overlap / orig_area
    if remain_ratio < _MIN_REMAIN_RATIO:
        return None  # 幾乎全被公區覆蓋

    # bbox 級無法精確裁剪，保留原 bbox
    return priv_bbox


def print_overlap_report(result: dict) -> None:
    """印出解衝突報告。"""
    s = result["stats"]
    print(f"  輸入: {s['total_input']} 標註 ({s['public_count']} 公 + {s['private_count']} 私)")
    print(f"  重疊: {s['overlap_pairs']} 對")
    print(f"  輸出: {s['total_output']} 標註 (丟棄 {s['dropped_count']} 個被完全覆蓋的私區)")
    if result["dropped"]:
        for d in result["dropped"]:
            print(f"    - 丟棄: {d['type']} bbox={d['bbox']}")
