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

TYPE_ZH = {
    "stairwell": "樓梯間", "elevator": "電梯", "corridor": "走廊",
    "lobby": "梯廳/門廳", "mechanical": "機電空間", "bedroom": "臥室",
    "living_room": "客廳", "kitchen": "廚房", "bathroom": "浴室",
    "balcony": "陽台", "storage": "儲藏室",
}

TYPE_COLORS = {
    "stairwell": "#34A853", "elevator": "#4285F4", "corridor": "#FBBC04",
    "lobby": "#AB47BC", "mechanical": "#00ACC1", "bedroom": "#FF7043",
    "living_room": "#8D6E63", "kitchen": "#FF8A65", "bathroom": "#78909C",
    "balcony": "#AED581", "storage": "#BDBDBD",
}

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

    /* 空間分類明細卡片 */
    .room-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .room-card-public {
        border-left: 4px solid #34A853;
        background: #f6fef7;
    }
    .room-card-private {
        border-left: 4px solid #e0e0e0;
        background: #fafafa;
    }
    .room-type-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 600;
        color: white;
    }
    .room-detail {
        color: #666;
        font-size: 0.85em;
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

        # ── Room 分類明細 ──
        st.subheader("📋 空間分類明細")

        if rooms:
            # ── 摘要指標列 ──
            summary_cols = st.columns(5)
            summary_cols[0].metric("總房間", len(rooms))
            summary_cols[1].metric("公共區域", metrics["n_public"])
            summary_cols[2].metric("私有空間", metrics["n_private"])
            summary_cols[3].metric("覆蓋率", f"{metrics['coverage']:.0%}")
            avg_iou = sum(r.get("solidity", 0) for r in rooms) / len(rooms) if rooms else 0
            summary_cols[4].metric("平均 Solidity", f"{avg_iou:.2f}")

            st.divider()

            # ── 切換：表格 vs 卡片 ──
            view_mode = st.radio("顯示模式", ["📊 表格", "🃏 卡片"],
                                 horizontal=True, label_visibility="collapsed")

            if view_mode == "📊 表格":
                # ── 改良版表格 ──
                table_data = []
                for i, r in enumerate(rooms):
                    is_pub = r["type"] in PUBLIC_TYPES
                    rtype = r["type"]
                    type_zh = TYPE_ZH.get(rtype, r.get("type_zh", rtype))
                    table_data.append({
                        "#": i + 1,
                        "屬性": "🟢 公共" if is_pub else "🔴 私有",
                        "類型": type_zh,
                        "類型(EN)": rtype,
                        "面積比": r["rel_area"],
                        "長寬比": r["aspect_ratio"],
                        "Solidity": r.get("solidity", 0),
                        "位置 X": f"{r['rel_x']:.2f}",
                        "位置 Y": f"{r['rel_y']:.2f}",
                        "分類原因": r.get("reason", "—"),
                    })

                df = pd.DataFrame(table_data)

                # 以顏色標記公共區域列
                def highlight_public(row):
                    if "公共" in str(row["屬性"]):
                        return ["background-color: #e8f5e9"] * len(row)
                    return [""] * len(row)

                styled = (
                    df.style
                    .apply(highlight_public, axis=1)
                    .format({
                        "面積比": "{:.4f}",
                        "長寬比": "{:.2f}",
                        "Solidity": "{:.2f}",
                    })
                    .set_properties(**{"text-align": "center"},
                                    subset=["#", "屬性", "面積比", "長寬比", "Solidity", "位置 X", "位置 Y"])
                    .set_properties(**{"font-size": "0.9em"})
                )
                st.dataframe(styled, use_container_width=True, hide_index=True,
                             height=min(40 * len(rooms) + 50, 600))

            else:
                # ── 卡片模式 ──
                # 先顯示公共，再顯示私有
                sorted_rooms = sorted(enumerate(rooms),
                                      key=lambda x: (0 if x[1]["type"] in PUBLIC_TYPES else 1,
                                                     x[0]))
                for idx, r in sorted_rooms:
                    is_pub = r["type"] in PUBLIC_TYPES
                    rtype = r["type"]
                    type_zh = TYPE_ZH.get(rtype, r.get("type_zh", rtype))
                    color = TYPE_COLORS.get(rtype, "#999")
                    card_class = "room-card-public" if is_pub else "room-card-private"
                    pub_label = "公共" if is_pub else "私有"

                    bbox = r.get("bbox", (0, 0, 0, 0))
                    reason = r.get("reason", "—")

                    st.markdown(f"""
                    <div class="room-card {card_class}">
                        <div style="min-width:32px;text-align:center;font-weight:bold;color:#999">
                            {idx + 1}
                        </div>
                        <div>
                            <span class="room-type-badge" style="background:{color}">
                                {type_zh}
                            </span>
                            <span style="margin-left:8px;color:#888;font-size:0.8em">
                                {pub_label}
                            </span>
                        </div>
                        <div class="room-detail">
                            面積比: {r['rel_area']:.4f} &nbsp;|&nbsp;
                            長寬比: {r['aspect_ratio']:.2f} &nbsp;|&nbsp;
                            Solidity: {r.get('solidity', 0):.2f}
                        </div>
                        <div class="room-detail">
                            位置: ({r['rel_x']:.2f}, {r['rel_y']:.2f})
                        </div>
                        <div class="room-detail" style="flex:1">
                            📎 {reason}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("未偵測到任何空間")

with tab_annotate:
    render_annotation_tab(pipeline_result, current_image)

with tab_eval:
    render_evaluation_tab(pipeline_result, current_image)
