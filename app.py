"""Streamlit Web UI — 建築平面圖公共區域辨識系統

啟動: streamlit run app.py
"""

import os
import glob

import streamlit as st
import pandas as pd

from src.pipeline_ui import run_pipeline_ui

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
    run_clicked = st.button("▶ 開始辨識", type="primary", width="stretch")

    # ── 指標區（pipeline 執行後填入） ──
    metrics_placeholder = st.empty()


# ─────────────────────────────────────────────
# Main Area
# ─────────────────────────────────────────────
st.title("建築平面圖公共區域辨識")

# 初始狀態：顯示選擇的圖片預覽
if image_path and not run_clicked and "result" not in st.session_state:
    st.image(image_path, caption="選擇的平面圖", width="stretch")
    st.info("👈 點擊左側「開始辨識」執行 pipeline")

# ── 執行 Pipeline ──
if run_clicked:
    if not image_path:
        st.warning("⚠️ 請先上傳圖檔或選擇範例")
    else:
        with st.spinner("🔄 辨識中，請稍候..."):
            result = run_pipeline_ui(image_path, use_ocr=use_ocr)
        st.session_state["result"] = result
        st.session_state["image_path"] = image_path

# ── 顯示結果 ──
if "result" in st.session_state:
    result = st.session_state["result"]

    # 錯誤處理
    if result["error"]:
        st.error(f"❌ Pipeline 執行失敗")
        st.code(result["error"], language="text")
    else:
        images = result["images"]
        rooms = result["rooms"]
        metrics = result["metrics"]

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

        # ── Tabs: 各階段輸出 ──
        tab_original, tab_class, tab_zones, tab_erased, tab_debug = st.tabs(
            ["🖼️ 原圖", "🏷️ 分類", "🟢 公私區", "✂️ 擦除", "🔧 Debug"]
        )

        with tab_original:
            st.image(images["original"], caption="原始平面圖", width="stretch")

        with tab_class:
            st.image(images["classification"], caption="空間分類結果", width="stretch")

        with tab_zones:
            st.image(images["zones"], caption="公共區域 (綠) vs 私有區域 (粉)", width="stretch")

        with tab_erased:
            st.image(images["erased"], caption="擦除結果 — 僅保留公共區域", width="stretch")

        with tab_debug:
            debug_col1, debug_col2 = st.columns(2)
            with debug_col1:
                st.image(images["walls_thick"], caption="厚牆偵測", width="stretch")
            with debug_col2:
                st.image(images["walls_closed"], caption="間隙封閉後牆體", width="stretch")

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

            # 以顏色標記公共區域列
            def highlight_public(row):
                if row["公共"] == "★":
                    return ["background-color: #e8f5e9"] * len(row)
                return [""] * len(row)

            styled = df.style.apply(highlight_public, axis=1).set_properties(
                **{"text-align": "center"}, subset=["#", "公共", "面積比", "長寬比"]
            )
            st.dataframe(styled, width="stretch", hide_index=True)
        else:
            st.info("未偵測到任何空間")
