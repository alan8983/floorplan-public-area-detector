"""評估儀表板 Tab — 比對 pipeline 輸出 vs ground truth。

顯示：
  - 指標卡片（分類準確度、公共/私有準確度、偵測率、IoU）
  - 逐房間比較表（pipeline vs ground truth，不一致以紅色標示）
"""

import os
import sys

import streamlit as st
import pandas as pd

# 確保 src/ 下的模組可被 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from evaluate import load_ground_truth, match_rooms_to_gt

# ── 公共類型 ──
PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}

TYPE_ZH = {
    "stairwell": "樓梯間", "elevator": "電梯", "corridor": "走廊",
    "lobby": "梯廳/門廳", "mechanical": "機電空間", "private": "私有空間",
    "kitchen": "廚房", "living_room": "客廳", "bedroom": "臥室",
    "bathroom": "浴室", "balcony": "陽台", "storage": "儲藏室",
    "entrance": "玄關", "dining_room": "餐廳", "annotation": "標註",
}


def _compute_metrics(rooms: list[dict], gt_entries: list[dict]) -> dict:
    """計算評估指標（沿用 evaluate.py 邏輯）。"""
    matches = match_rooms_to_gt(rooms, gt_entries)

    matched_ious = [m["iou"] for m in matches if m["pred"] is not None]
    mean_iou = sum(matched_ious) / max(len(matched_ious), 1)
    detection_rate = len(matched_ious) / max(len(gt_entries), 1)

    type_correct = 0
    pub_correct = 0
    pub_recall_tp = 0  # true positives for public recall
    pub_recall_fn = 0  # false negatives for public recall
    matched_count = 0

    for m in matches:
        gt = m["gt"]
        pred = m["pred"]
        gt_pub = gt.get("is_public", gt["type"] in PUBLIC_TYPES)

        if pred is None:
            if gt_pub:
                pub_recall_fn += 1
            continue

        matched_count += 1
        gt_type = gt["type"]
        pred_type = pred.get("type", "unknown")

        if gt_type == pred_type:
            type_correct += 1

        pred_pub = pred_type in PUBLIC_TYPES
        if gt_pub == pred_pub:
            pub_correct += 1

        if gt_pub and pred_pub:
            pub_recall_tp += 1
        elif gt_pub and not pred_pub:
            pub_recall_fn += 1

    type_accuracy = type_correct / max(matched_count, 1)
    pub_accuracy = pub_correct / max(matched_count, 1)
    pub_recall = pub_recall_tp / max(pub_recall_tp + pub_recall_fn, 1)

    return {
        "gt_count": len(gt_entries),
        "detected_count": len(rooms),
        "matched_count": matched_count,
        "detection_rate": detection_rate,
        "mean_iou": mean_iou,
        "type_accuracy": type_accuracy,
        "pub_priv_accuracy": pub_accuracy,
        "pub_recall": pub_recall,
        "per_room": matches,
    }


def _compute_metrics_from_annotations(
    rooms: list[dict], annotations: list[dict]
) -> dict:
    """從 session_state annotations 計算指標（格式與 ground truth 相同）。"""
    return _compute_metrics(rooms, annotations)


def render_evaluation_tab(
    pipeline_result: dict | None,
    image_path: str | None,
):
    """渲染評估儀表板 Tab。"""

    if image_path is None:
        st.info("👈 請先選擇圖片")
        return

    if pipeline_result is None or pipeline_result.get("error"):
        st.info("請先在「辨識結果」Tab 執行 pipeline")
        return

    rooms = pipeline_result.get("rooms", [])
    if not rooms:
        st.warning("Pipeline 未偵測到任何房間，無法評估")
        return

    # ── 取得 ground truth ──
    # 優先使用 session_state 中的標註（可能已被使用者修改）
    gt_entries = st.session_state.get("annotations", [])

    if not gt_entries:
        st.warning("⚠️ 尚未建立 Ground Truth")
        st.info("請前往「標註編輯」Tab，使用「自動標註」產生 draft 標註，校對後儲存。")
        return

    # ── 計算指標 ──
    metrics = _compute_metrics_from_annotations(rooms, gt_entries)

    # ── 指標卡片 ──
    st.subheader("📊 評估指標")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("分類準確度", f"{metrics['type_accuracy']:.0%}")
    col2.metric("公共/私有準確度", f"{metrics['pub_priv_accuracy']:.0%}")
    col3.metric("公共區域召回率", f"{metrics['pub_recall']:.0%}")
    col4.metric("平均 IoU", f"{metrics['mean_iou']:.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Ground Truth 數", metrics["gt_count"])
    col6.metric("Pipeline 偵測數", metrics["detected_count"])
    col7.metric("成功配對數", metrics["matched_count"])
    col8.metric("偵測率", f"{metrics['detection_rate']:.0%}")

    # ── 逐房間比較表 ──
    st.subheader("📋 逐房間比較")

    table_data = []
    for i, m in enumerate(metrics["per_room"]):
        gt = m["gt"]
        pred = m["pred"]
        gt_type = gt["type"]
        gt_type_zh = TYPE_ZH.get(gt_type, gt_type)
        gt_pub = "公共" if gt.get("is_public", gt_type in PUBLIC_TYPES) else "私有"

        if pred is not None:
            pred_type = pred.get("type", "unknown")
            pred_type_zh = TYPE_ZH.get(pred_type, pred_type)
            pred_pub = "公共" if pred_type in PUBLIC_TYPES else "私有"
            type_match = "✅" if gt_type == pred_type else "❌"
            pub_match = "✅" if gt_pub == pred_pub else "❌"
            iou = f"{m['iou']:.2f}"
        else:
            pred_type_zh = "（未偵測）"
            pred_pub = "—"
            type_match = "❌"
            pub_match = "❌"
            iou = f"{m['iou']:.2f}"

        table_data.append({
            "#": i + 1,
            "GT 類型": gt_type_zh,
            "GT 公/私": gt_pub,
            "Pipeline 類型": pred_type_zh,
            "Pipeline 公/私": pred_pub,
            "類型一致": type_match,
            "公私一致": pub_match,
            "IoU": iou,
            "備註": gt.get("note", ""),
        })

    df = pd.DataFrame(table_data)

    # 不一致列以紅色標示
    def highlight_mismatch(row):
        if row["類型一致"] == "❌" or row["公私一致"] == "❌":
            return ["background-color: #ffebee"] * len(row)
        return ["background-color: #e8f5e9"] * len(row)

    styled = df.style.apply(highlight_mismatch, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)

    # ── 摘要 ──
    n_type_wrong = sum(1 for m in metrics["per_room"]
                       if m["pred"] is not None and m["gt"]["type"] != m["pred"].get("type"))
    n_unmatched = sum(1 for m in metrics["per_room"] if m["pred"] is None)

    if n_type_wrong == 0 and n_unmatched == 0:
        st.success("🎉 所有房間分類正確！")
    else:
        if n_type_wrong > 0:
            st.warning(f"⚠️ {n_type_wrong} 個房間分類不一致")
        if n_unmatched > 0:
            st.warning(f"⚠️ {n_unmatched} 個 ground truth 房間未被偵測到")
