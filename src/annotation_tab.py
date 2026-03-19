"""標註編輯 Tab — 完整 Ground Truth 編輯器。

功能：
  - 使用 streamlit-image-annotation 的 detection() 元件
  - 在平面圖上畫新 bbox、調整邊界、刪除、修改分類
  - 獨立於 pipeline：可直接載圖標註，不需要先跑 pipeline
  - 儲存/載入 ground truth JSON
"""

import json
import os
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from streamlit_image_annotation import detection

# ── 類別定義 ──
PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}

LABEL_LIST = [
    "stairwell",    # 0: 樓梯間
    "elevator",     # 1: 電梯
    "corridor",     # 2: 走廊
    "lobby",        # 3: 梯廳/門廳
    "mechanical",   # 4: 機電空間
    "private",      # 5: 私有空間
]

TYPE_ZH = {
    "stairwell": "樓梯間", "elevator": "電梯", "corridor": "走廊",
    "lobby": "梯廳/門廳", "mechanical": "機電空間", "private": "私有空間",
    "kitchen": "廚房", "living_room": "客廳", "bedroom": "臥室",
    "bathroom": "浴室", "balcony": "陽台", "storage": "儲藏室",
    "entrance": "玄關", "dining_room": "餐廳",
}

# detection() 顯示尺寸
DISPLAY_WIDTH = 900
DISPLAY_HEIGHT = 1000


def _init_session_state():
    """初始化 annotation tab 需要的 session state。"""
    if "annotations" not in st.session_state:
        st.session_state.annotations = []
    if "ann_modified" not in st.session_state:
        st.session_state.ann_modified = False
    if "ann_image_path" not in st.session_state:
        st.session_state.ann_image_path = None


def _rooms_to_annotations(rooms: list[dict]) -> list[dict]:
    """將 pipeline rooms 轉為 annotation 格式。"""
    annotations = []
    for r in rooms:
        bbox = list(r["bbox"])  # [x, y, w, h]
        rtype = r.get("type", "private")
        # 將細分類型映射到 LABEL_LIST 中的 6 大類
        if rtype not in LABEL_LIST:
            if rtype in PUBLIC_TYPES:
                rtype = "mechanical"  # fallback public
            else:
                rtype = "private"  # fallback private
        is_public = rtype in PUBLIC_TYPES
        annotations.append({
            "bbox": bbox,
            "type": rtype,
            "is_public": is_public,
            "note": r.get("reason", ""),
        })
    return annotations


def _load_ground_truth(image_path: str) -> list[dict] | None:
    """嘗試載入對應圖片的 ground_truth.json。"""
    parent = Path(image_path).parent
    gt_path = parent / "ground_truth.json"
    if gt_path.exists():
        with open(gt_path, "r", encoding="utf-8") as f:
            return json.load(f)

    stem = Path(image_path).stem
    gt_path2 = parent / f"{stem}_ground_truth.json"
    if gt_path2.exists():
        with open(gt_path2, "r", encoding="utf-8") as f:
            return json.load(f)

    return None


def _save_ground_truth(image_path: str, annotations: list[dict]) -> str:
    """儲存 ground truth JSON，回傳儲存路徑。"""
    parent = Path(image_path).parent
    gt_path = parent / "ground_truth.json"
    os.makedirs(parent, exist_ok=True)

    clean = []
    for ann in annotations:
        clean.append({
            "bbox": ann["bbox"],
            "type": ann["type"],
            "is_public": ann.get("is_public", ann["type"] in PUBLIC_TYPES),
            "note": ann.get("note", ""),
        })

    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    return str(gt_path)


def _annotations_to_detection_args(annotations: list[dict]) -> tuple[list, list]:
    """將 annotations 轉為 detection() 需要的 bboxes + labels。"""
    bboxes = []
    labels = []
    for ann in annotations:
        bboxes.append(ann["bbox"])
        rtype = ann["type"]
        if rtype in LABEL_LIST:
            labels.append(LABEL_LIST.index(rtype))
        else:
            labels.append(LABEL_LIST.index("private"))  # fallback
    return bboxes, labels


def _detection_result_to_annotations(result: list[dict]) -> list[dict]:
    """將 detection() 回傳值轉為 annotations 格式。"""
    annotations = []
    for item in result:
        bbox = item["bbox"]
        label = item.get("label", "private")
        if label not in LABEL_LIST:
            label = "private"
        annotations.append({
            "bbox": bbox,
            "type": label,
            "is_public": label in PUBLIC_TYPES,
            "note": "",
        })
    return annotations


def render_annotation_tab(pipeline_result: dict | None, image_path: str | None):
    """渲染標註編輯 Tab — 完整 Ground Truth 編輯器。"""
    _init_session_state()

    if image_path is None:
        st.info("👈 請先選擇圖片")
        return

    # ── 當圖片切換時，重新載入標註 ──
    if st.session_state.ann_image_path != image_path:
        st.session_state.ann_image_path = image_path
        st.session_state.ann_modified = False
        gt = _load_ground_truth(image_path)
        if gt is not None:
            st.session_state.annotations = gt
            st.info(f"✅ 已載入既有 ground truth（{len(gt)} 個標註）")
        else:
            st.session_state.annotations = []

    annotations = st.session_state.annotations

    # ── 工具列 ──
    tool_col1, tool_col2, tool_col3, tool_col4, tool_col5 = st.columns([1, 1, 1, 1, 2])

    with tool_col1:
        if st.button("📝 空白標註", help="清除所有標註，從零開始"):
            st.session_state.annotations = []
            st.session_state.ann_modified = True
            st.rerun()

    with tool_col2:
        if st.button("🤖 從 Pipeline 載入", help="載入 pipeline 偵測結果作為初始標註"):
            if pipeline_result and not pipeline_result.get("error") and pipeline_result.get("rooms"):
                st.session_state.annotations = _rooms_to_annotations(pipeline_result["rooms"])
                st.session_state.ann_modified = True
                st.rerun()
            else:
                st.warning("請先在「辨識結果」Tab 執行 pipeline")

    with tool_col3:
        gt = _load_ground_truth(image_path)
        if gt is not None:
            if st.button("📂 載入既存 GT"):
                st.session_state.annotations = gt
                st.session_state.ann_modified = False
                st.rerun()

    with tool_col4:
        if st.button("💾 儲存 GT", type="primary"):
            current_anns = st.session_state.annotations
            if current_anns:
                save_path = _save_ground_truth(image_path, current_anns)
                st.session_state.ann_modified = False
                st.success(f"已儲存至 {save_path}")
            else:
                st.warning("無標註可儲存")

    with tool_col5:
        if st.session_state.ann_modified:
            st.warning("⚠️ 有未儲存的修改")

    # ── 使用說明 ──
    with st.expander("📖 操作說明", expanded=False):
        st.markdown("""
        - **畫新框**: 在圖片上拖曳即可畫出新的 bounding box
        - **選擇類型**: 畫完後在彈出的選單中選擇房間類型
        - **調整大小**: 拖曳既有框的邊角可調整大小
        - **刪除**: 點選框後按 Delete 鍵刪除
        - **類型說明**: stairwell=樓梯間, elevator=電梯, corridor=走廊, lobby=梯廳, mechanical=機電, private=私有
        """)

    # ── detection 元件 ──
    bboxes, labels = _annotations_to_detection_args(annotations)

    # 計算顯示尺寸（保持比例）
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        st.error("無法載入圖片")
        return
    orig_h, orig_w = img_bgr.shape[:2]
    aspect = orig_h / orig_w
    display_w = min(DISPLAY_WIDTH, orig_w)
    display_h = int(display_w * aspect)
    if display_h > DISPLAY_HEIGHT:
        display_h = DISPLAY_HEIGHT
        display_w = int(display_h / aspect)

    result = detection(
        image_path=image_path,
        label_list=LABEL_LIST,
        bboxes=bboxes,
        labels=labels,
        height=display_h,
        width=display_w,
        key="annotation_detection",
    )

    # ── 同步 detection 結果 → session_state ──
    if result is not None and isinstance(result, list):
        new_annotations = _detection_result_to_annotations(result)
        # 檢查是否有變化
        if len(new_annotations) != len(annotations):
            st.session_state.annotations = new_annotations
            st.session_state.ann_modified = True
        else:
            changed = False
            for new, old in zip(new_annotations, annotations):
                if new["bbox"] != old["bbox"] or new["type"] != old["type"]:
                    changed = True
                    break
            if changed:
                # 保留原有的 note
                for i, new in enumerate(new_annotations):
                    if i < len(annotations):
                        new["note"] = annotations[i].get("note", "")
                st.session_state.annotations = new_annotations
                st.session_state.ann_modified = True

    # ── 統計摘要 ──
    current_anns = st.session_state.annotations
    if current_anns:
        st.markdown("---")
        n_pub = sum(1 for a in current_anns if a.get("is_public"))
        n_priv = len(current_anns) - n_pub
        stat_cols = st.columns(4)
        stat_cols[0].metric("總標註", len(current_anns))
        stat_cols[1].metric("公共區域", n_pub)
        stat_cols[2].metric("私有區域", n_priv)
        stat_cols[3].metric("公共比例", f"{n_pub/max(len(current_anns),1):.0%}")

        # 標註列表
        with st.expander(f"📋 標註列表（{len(current_anns)} 個）", expanded=False):
            for i, ann in enumerate(current_anns):
                rtype = ann["type"]
                label = TYPE_ZH.get(rtype, rtype)
                icon = "🟢" if ann.get("is_public") else "🔴"
                x, y, w, h = ann["bbox"]
                st.caption(f"{i+1}. {icon} {label} — ({x},{y}) {w}×{h}")
    else:
        st.info("尚無標註。使用上方工具列的按鈕載入標註，或直接在圖片上畫框。")
