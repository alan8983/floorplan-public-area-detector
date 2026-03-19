"""Streamlit Web UI — 建築平面圖公共區域辨識系統

啟動: streamlit run app.py
"""

import os
import glob

import streamlit as st
import pandas as pd

from src.pipeline_ui import run_pipeline_ui
from src.annotation_tab import render_annotation_tab
from src.evaluation_tab import render_evaluation_tab

# ── 公共類型（用於表格標記） ──
PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}

SAMPLES_DIR = "samples"


# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="平面圖公共區域辨識",
    page_icon="🏢",
    layout="wide",
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 整體字體 */
    .block-container { padding-top: 2rem; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #4CAF50;
    }

    /* 表格公共區域 highlight */
    .public-row { background-color: #e8f5e9 !important; }

    /* Sidebar 分隔線 */
    .sidebar-divider {
        border-top: 1px solid #e0e0e0;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helper: 取得 samples/ 下所有圖檔
# ─────────────────────────────────────────────
def get_sample_files() -> list[str]:
    """遞迴掃描 samples/ 下所有 jpg/png 檔案。"""
    if not os.path.isdir(SAMPLES_DIR):
        return []
    patterns = ["**/*.jpg", "**/*.jpeg", "**/*.png"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(SAMPLES_DIR, pat), recursive=True))
    return sorted(set(files))


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🏢 平面圖辨識系統")
    st.caption("上傳建築平面圖，自動辨識公共區域")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # ── 圖檔來源 ──
    st.subheader("📂 圖檔來源")
    input_mode = st.radio(
        "選擇輸入方式",
        ["上傳圖檔", "選擇範例"],
        horizontal=True,
        label_visibility="collapsed",
    )

    image_path = None

    if input_mode == "上傳圖檔":
        uploaded = st.file_uploader(
            "上傳平面圖",
            type=["jpg", "jpeg", "png"],
            label_visibility="collapsed",
        )
        if uploaded is not None:
            # 存到暫存檔
            tmp_path = os.path.join("output", f"_upload_{uploaded.name}")
            os.makedirs("output", exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(uploaded.getvalue())
            image_path = tmp_path
    else:
        samples = get_sample_files()
        if samples:
            image_path = st.selectbox(
                "選擇範例圖檔",
                samples,
                format_func=lambda x: os.path.relpath(x, SAMPLES_DIR),
                label_visibility="collapsed",
            )
        else:
            st.info("samples/ 目錄中無可用範例")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # ── 參數設定 ──
    st.subheader("⚙️ 參數設定")
    use_ocr = st.checkbox("啟用 OCR 文字辨識", value=False,
                          help="使用 Tesseract OCR 輔助分類（需安裝 tesseract-ocr）")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # ── 執行 ──
    run_clicked = st.button("▶ 開始辨識", type="primary", use_container_width=True)

    # ── 指標區（pipeline 執行後填入） ──
    metrics_placeholder = st.empty()


# ─────────────────────────────────────────────
# Main Area
# ─────────────────────────────────────────────
st.title("建築平面圖公共區域辨識")

# ── 執行 Pipeline ──
if run_clicked:
    if not image_path:
        st.warning("⚠️ 請先上傳圖檔或選擇範例")
    else:
        with st.spinner("🔄 辨識中，請稍候..."):
            result = run_pipeline_ui(image_path, use_ocr=use_ocr)
        st.session_state["result"] = result
        st.session_state["image_path"] = image_path

# ── 取得當前 pipeline result（可能為 None） ──
pipeline_result = st.session_state.get("result", None)
current_image = image_path  # 用於標註 Tab（不需要 pipeline）

# ── Tabs: 永遠顯示，不需要先跑 pipeline ──
tab_pipeline, tab_annotate, tab_eval = st.tabs(
    ["🔬 辨識結果", "✏️ 標註編輯", "📊 評估"]
)

with tab_pipeline:
    if pipeline_result is None:
        if image_path:
            st.image(image_path, caption="選擇的平面圖", use_container_width=True)
            st.info("👈 點擊左側「開始辨識」執行 pipeline")
        else:
            st.info("👈 請先上傳圖檔或選擇範例")
    elif pipeline_result.get("error"):
        st.error("❌ Pipeline 執行失敗")
        st.code(pipeline_result["error"], language="text")
    else:
        images = pipeline_result["images"]
        rooms = pipeline_result["rooms"]
        metrics = pipeline_result["metrics"]

        # ── Sidebar: 品質指標 ──
        with metrics_placeholder.container():
            st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
            st.subheader("📊 辨識結果")

            col1, col2 = st.columns(2)
            col1.metric("房間數", metrics["room_count"])
            col2.metric("覆蓋率", f"{metrics['coverage']:.0%}")

            col3, col4 = st.columns(2)
            col3.metric("公共區域", metrics["n_public"])
            col4.metric("私有區域", metrics["n_private"])

            st.metric("處理時間", f"{metrics['elapsed']:.1f} 秒")
            st.caption(f"圖片尺寸: {metrics['dimensions']}")

            if metrics["coverage"] < 0.60:
                st.warning("⚠️ 覆蓋率偏低，分割可能不完整")

        # ── Pipeline 子 tabs ──
        sub_original, sub_class, sub_zones, sub_erased, sub_debug = st.tabs(
            ["🖼️ 原圖", "🏷️ 分類", "🟢 公私區", "✂️ 擦除", "🔧 Debug"]
        )

        with sub_original:
            st.image(images["original"], caption="原始平面圖", use_container_width=True)

        with sub_class:
            st.image(images["classification"], caption="空間分類結果", use_container_width=True)

        with sub_zones:
            st.image(images["zones"], caption="公共區域 (綠) vs 私有區域 (粉)", use_container_width=True)

        with sub_erased:
            st.image(images["erased"], caption="擦除結果 — 僅保留公共區域", use_container_width=True)

        with sub_debug:
            debug_col1, debug_col2 = st.columns(2)
            with debug_col1:
                st.image(images["walls_thick"], caption="厚牆偵測", use_container_width=True)
            with debug_col2:
                st.image(images["walls_closed"], caption="間隙封閉後牆體", use_container_width=True)

        # ── Room 分類表格 ──
        st.subheader("📋 空間分類明細")

        if rooms:
            table_data = []
            for i, r in enumerate(rooms):
                is_pub = r["type"] in PUBLIC_TYPES
                table_data.append({
                    "#": i + 1,
                    "公共": "★" if is_pub else "",
                    "類型": r.get("type_zh", r["type"]),
                    "面積比": f"{r['rel_area']:.4f}",
                    "長寬比": f"{r['aspect_ratio']:.2f}",
                    "位置 (x,y)": f"({r['rel_x']:.2f}, {r['rel_y']:.2f})",
                    "分類原因": r.get("reason", "—"),
                })

            df = pd.DataFrame(table_data)

            def highlight_public(row):
                if row["公共"] == "★":
                    return ["background-color: #e8f5e9"] * len(row)
                return [""] * len(row)

            styled = df.style.apply(highlight_public, axis=1).set_properties(
                **{"text-align": "center"}, subset=["#", "公共", "面積比", "長寬比"]
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("未偵測到任何空間")

with tab_annotate:
    render_annotation_tab(pipeline_result, current_image)

with tab_eval:
    render_evaluation_tab(pipeline_result, current_image)
