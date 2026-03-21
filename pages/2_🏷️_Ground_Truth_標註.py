"""Ground Truth 標註工具 — fabric.js 自訂元件版

支援縮放/平移、左鍵畫框與選取、右鍵刪除、OCR 輔助層。
五種類型：stairwell / elevator / corridor / mechanical / private
"""

import os
import json
import glob
from datetime import datetime

import streamlit as st
from PIL import Image

from components.gt_annotator import (
    gt_annotator, migrate_legacy_types, ROOM_TYPES, PUBLIC_TYPES,
)

# ── 常數 ──
SAMPLES_DIR = "samples"

TYPE_ZH = {t["id"]: t["label_zh"] for t in ROOM_TYPES}
TYPE_COLORS = {t["id"]: t["color"] for t in ROOM_TYPES}

st.set_page_config(page_title="Ground Truth 標註", page_icon="🏷️", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 0.5rem; max-width: 100%; }
    .gt-legend { display: inline-block; width: 14px; height: 14px;
                 border-radius: 3px; margin-right: 4px; vertical-align: middle; }
    h1 { font-size: 1.5rem !important; margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────
# Helper functions
# ─────────────────────────────────────
def get_sample_files() -> list[str]:
    """遞迴掃描 samples/ 下所有圖檔。"""
    if not os.path.isdir(SAMPLES_DIR):
        return []
    patterns = ["**/*.jpg", "**/*.jpeg", "**/*.png"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(SAMPLES_DIR, pat), recursive=True))
    files = [f for f in files if "_annotated" not in f and "_gt_" not in f]
    return sorted(set(files))


def gt_path_for_image(image_path: str) -> str:
    base = os.path.splitext(image_path)[0]
    return base + "_ground_truth.json"


def find_nearby_gt(image_path: str) -> str | None:
    direct = gt_path_for_image(image_path)
    if os.path.exists(direct):
        return direct
    directory = os.path.dirname(image_path)
    fallback = os.path.join(directory, "ground_truth.json")
    if os.path.exists(fallback):
        return fallback
    stem = os.path.splitext(os.path.basename(image_path))[0]
    for suffix in ["_input", "_residential", "_3F", "_4F"]:
        stem = stem.replace(suffix, "")
    subdir_gt = os.path.join(directory, stem, "ground_truth.json")
    if os.path.exists(subdir_gt):
        return subdir_gt
    return None


def load_existing_gt(gt_file: str) -> list[dict]:
    if not os.path.exists(gt_file):
        return []
    try:
        with open(gt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict) and "annotations" in data:
            entries = data["annotations"]
        else:
            entries = []
        return migrate_legacy_types(entries)
    except (json.JSONDecodeError, KeyError):
        return []


def save_gt(gt_file: str, gt_entries: list[dict], image_path: str):
    os.makedirs(os.path.dirname(gt_file) if os.path.dirname(gt_file) else ".", exist_ok=True)
    output = {
        "image": os.path.basename(image_path),
        "created": datetime.now().isoformat(),
        "num_rooms": len(gt_entries),
        "num_public": sum(1 for e in gt_entries if e.get("is_public", False)),
        "num_private": sum(1 for e in gt_entries if not e.get("is_public", False)),
        "annotations": gt_entries,
    }
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


@st.cache_data(show_spinner="正在執行 OCR...")
def run_ocr(image_path: str) -> list[dict]:
    """對圖片執行 OCR，回傳文字塊清單。"""
    try:
        from src.preprocessing import load_and_binarize
        from src.ocr_classify import ocr_extract
        _, _, binary = load_and_binarize(image_path)
        return ocr_extract(binary)
    except Exception as e:
        st.warning(f"OCR 執行失敗: {e}")
        return []


# ─────────────────────────────────────
# Sidebar
# ─────────────────────────────────────
with st.sidebar:
    st.header("📂 選擇圖檔")
    samples = get_sample_files()
    if not samples:
        st.warning("samples/ 目錄中無可用圖檔")
        st.stop()

    selected_image = st.selectbox(
        "平面圖",
        samples,
        format_func=lambda x: os.path.relpath(x, SAMPLES_DIR),
    )

    st.divider()

    # GT 狀態
    existing_gt_path = find_nearby_gt(selected_image)
    gt_save_path = gt_path_for_image(selected_image)

    if existing_gt_path:
        existing_gt = load_existing_gt(existing_gt_path)
        st.success(f"✅ 已有 GT ({len(existing_gt)} rooms)")
        n_pub = sum(1 for e in existing_gt if e.get("is_public", False))
        c1, c2 = st.columns(2)
        c1.metric("公共", n_pub)
        c2.metric("私有", len(existing_gt) - n_pub)
    else:
        st.info("🆕 尚無 GT")
        existing_gt = []

    st.divider()

    # 類型圖例
    st.subheader("類型圖例")
    for t in ROOM_TYPES:
        icon = "🔴" if t["is_public"] else "🔵"
        st.markdown(
            f'<span class="gt-legend" style="background:{t["color"]}"></span>'
            f' {icon} {t["label_zh"]} ({t["id"]})',
            unsafe_allow_html=True,
        )

    st.divider()

    # OCR 控制
    show_ocr = st.checkbox("顯示 OCR 文字", value=True)

    # 顯示設定
    comp_height = st.slider("標註區高度", 500, 1200, 850, 50)


# ─────────────────────────────────────
# Main area
# ─────────────────────────────────────
st.title("🏷️ Ground Truth 標註")

if selected_image:
    img = Image.open(selected_image)
    img_w, img_h = img.size
    st.caption(f"📐 {os.path.basename(selected_image)} — {img_w} × {img_h} px")

    # OCR
    ocr_blocks = run_ocr(selected_image) if show_ocr else []

    # ── 標註元件（含儲存功能）──
    gt_annotator(
        image_path=selected_image,
        image_width=img_w,
        image_height=img_h,
        annotations=existing_gt,
        ocr_blocks=ocr_blocks,
        component_height=comp_height,
        key=f"gt_{os.path.basename(selected_image)}",
        save_path=gt_save_path,
    )

    st.caption(f"儲存路徑: `{gt_save_path}` — 點擊 canvas 工具列的 **[S] 儲存** 或按 Ctrl+S")


# ── 批次進度 ──
st.divider()
with st.expander("📊 GT 標註進度", expanded=False):
    import pandas as pd
    rows = []
    for s in get_sample_files():
        gt_file = find_nearby_gt(s)
        if gt_file:
            gt_data = load_existing_gt(gt_file)
            n = len(gt_data)
            n_p = sum(1 for e in gt_data if e.get("is_public", False))
            rows.append({"圖檔": os.path.relpath(s, SAMPLES_DIR), "狀態": "✅", "房間": n, "公共": n_p, "私有": n - n_p})
        else:
            rows.append({"圖檔": os.path.relpath(s, SAMPLES_DIR), "狀態": "⬜", "房間": 0, "公共": 0, "私有": 0})
    df = pd.DataFrame(rows)
    n_done = sum(1 for r in rows if r["狀態"] == "✅")
    st.metric("進度", f"{n_done} / {len(rows)}")
    st.dataframe(df, hide_index=True, use_container_width=True)
