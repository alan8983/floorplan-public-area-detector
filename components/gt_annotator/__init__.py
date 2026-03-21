"""GT Annotator — fabric.js 標註元件（使用 st.components.v1.html + 檔案通訊）。"""

import os
import json
import base64
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

import streamlit as st
import streamlit.components.v1 as components

# 加載重疊解衝突模組
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
from overlap import resolve_overlaps


# ── 儲存 API 端點（輕量 HTTP server，在背景執行）──
def _git_commit_push(file_path: str) -> str:
    """Git add + commit + push a ground truth file. Returns status message."""
    import subprocess
    try:
        # Make path relative to repo root
        repo_root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        rel_path = os.path.relpath(file_path, repo_root).replace('\\', '/')

        # git add
        subprocess.check_call(
            ['git', 'add', rel_path],
            cwd=repo_root, stderr=subprocess.DEVNULL
        )

        # Check if there are staged changes
        diff = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            cwd=repo_root, capture_output=True, text=True
        )
        if not diff.stdout.strip():
            return "no_change"

        # git commit
        filename = os.path.basename(file_path)
        commit_msg = f"gt: add/update {filename}"
        subprocess.check_call(
            ['git', 'commit', '-m', commit_msg],
            cwd=repo_root, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
        )

        # git push (best-effort, don't fail if offline; -u to auto-set upstream)
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_root, text=True
        ).strip()
        push_result = subprocess.run(
            ['git', 'push', '-u', 'origin', branch],
            cwd=repo_root, capture_output=True, text=True, timeout=15
        )
        if push_result.returncode == 0:
            return "pushed"
        else:
            return "committed"  # committed locally but push failed
    except subprocess.TimeoutExpired:
        return "committed"  # push timed out
    except Exception as e:
        return f"error: {e}"


class _SaveHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/gt_save':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                req = json.loads(body)
                save_path = req.get('path', '').replace('\\', '/')
                data = req.get('data', '')
                if save_path and data:
                    os.makedirs(os.path.dirname(save_path) or '.', exist_ok=True)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(data)

                    # 重疊分析
                    gt_data = json.loads(data)
                    annots = gt_data.get("annotations", [])
                    overlap_result = resolve_overlaps(annots)
                    overlap_stats = overlap_result["stats"]

                    # Auto git commit + push in background
                    git_status = _git_commit_push(save_path)

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "ok": True,
                        "git": git_status,
                        "overlap": overlap_stats,
                    }).encode())
                    return
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(str(e).encode())
                return
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs


_SAVE_PORT = 8504
_save_server_started = False


def _start_save_server():
    global _save_server_started
    if _save_server_started:
        return
    _save_server_started = True
    server = HTTPServer(('127.0.0.1', _SAVE_PORT), _SaveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

# ── 類型定義 ──
ROOM_TYPES = [
    {"id": "stairwell",   "label_zh": "樓梯間",  "color": "#DC3232", "is_public": True},
    {"id": "elevator",    "label_zh": "電梯",    "color": "#F5821E", "is_public": True},
    {"id": "corridor",    "label_zh": "走廊",    "color": "#C8A028", "is_public": True},
    {"id": "mechanical",  "label_zh": "機電空間", "color": "#2E7D32", "is_public": True},
    {"id": "private",     "label_zh": "私有空間", "color": "#5078B4", "is_public": False},
]

PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "mechanical"}

_LEGACY_TYPE_MAP = {
    "lobby": "corridor",
    "bedroom": "private", "living_room": "private", "kitchen": "private",
    "bathroom": "private", "balcony": "private", "storage": "private",
    "private_large": "private", "entrance": "private",
}

_FRONTEND_DIR = Path(__file__).parent / "frontend"


def migrate_legacy_types(annotations: list[dict]) -> list[dict]:
    """將舊版 11 類型遷移為新版 5 類型。"""
    for a in annotations:
        old_type = a.get("type", "private")
        if old_type in _LEGACY_TYPE_MAP:
            a["type"] = _LEGACY_TYPE_MAP[old_type]
        a["is_public"] = a["type"] in PUBLIC_TYPES
    return annotations


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _read_fabric_js() -> str:
    """讀取 fabric.min.js 內容。"""
    js_path = _FRONTEND_DIR / "fabric.min.js"
    with open(js_path, "r", encoding="utf-8") as f:
        return f.read()


def _build_html(
    image_b64: str,
    image_width: int,
    image_height: int,
    annotations: list[dict],
    ocr_blocks: list[dict],
    component_height: int,
    session_key: str,
    image_filename: str = "",
    save_path: str = "",
) -> str:
    """建立完整的 HTML 字串，內嵌 fabric.js 和所有資料。"""

    fabric_js = _read_fabric_js()
    annotations_json = json.dumps(annotations, ensure_ascii=False)
    ocr_json = json.dumps(ocr_blocks, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ height: 100%; width: 100%; background: #1e1e1e; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}

  #toolbar {{
    position: absolute; top: 0; left: 0; right: 0; z-index: 100; height: 38px;
    background: rgba(30,30,30,0.95); backdrop-filter: blur(8px);
    display: flex; align-items: center; gap: 8px;
    padding: 6px 12px; border-bottom: 1px solid #444;
    font-size: 13px; color: #ccc;
  }}
  #toolbar .sep {{ width: 1px; height: 20px; background: #555; }}
  #toolbar .info {{ color: #999; font-size: 12px; }}

  .type-btn {{
    padding: 4px 10px; border: 2px solid; border-radius: 4px;
    cursor: pointer; font-size: 12px; font-weight: 600;
    background: transparent; color: #eee; transition: all 0.15s;
  }}
  .type-btn:hover {{ filter: brightness(1.3); }}
  .type-btn.active {{ filter: brightness(1.5); box-shadow: 0 0 8px currentColor; }}

  .kbd {{ background: #333; border: 1px solid #555; border-radius: 3px;
         padding: 1px 5px; font-size: 11px; color: #aaa; font-family: monospace; }}

  #canvas-wrap {{ position: absolute; top: 38px; left: 0; right: 0; bottom: 24px; }}

  #type-popup {{
    position: absolute; z-index: 200; display: none;
    background: rgba(30,30,30,0.95); backdrop-filter: blur(8px);
    border: 1px solid #555; border-radius: 8px; padding: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  }}
  #type-popup .popup-btn {{
    display: block; width: 100%; padding: 6px 14px; margin: 2px 0;
    border: none; border-radius: 4px; cursor: pointer;
    font-size: 13px; font-weight: 600; text-align: left;
    color: #fff; transition: filter 0.1s;
  }}
  #type-popup .popup-btn:hover {{ filter: brightness(1.4); }}

  #status-bar {{
    position: absolute; bottom: 0; left: 0; right: 0; z-index: 100; height: 24px;
    background: rgba(30,30,30,0.9); padding: 4px 12px;
    font-size: 12px; color: #888; display: flex; gap: 16px;
  }}

  #ocr-toggle {{
    padding: 3px 8px; border: 1px solid #666; border-radius: 4px;
    background: transparent; color: #aaa; cursor: pointer; font-size: 12px;
  }}
  #ocr-toggle.on {{ background: rgba(46,125,50,0.3); border-color: #2E7D32; color: #4CAF50; }}

  #save-indicator {{
    position: absolute; top: 44px; right: 12px; z-index: 150;
    background: rgba(76,175,80,0.9); color: #fff; padding: 6px 12px;
    border-radius: 4px; font-size: 13px; display: none;
  }}
</style>
</head>
<body>

<div id="toolbar">
  <span style="font-weight:700; color:#fff;">GT</span>
  <div class="sep"></div>
  <button class="type-btn" data-type="stairwell" style="border-color:#DC3232;color:#DC3232;">
    <span class="kbd">1</span> 樓梯間
  </button>
  <button class="type-btn" data-type="elevator" style="border-color:#F5821E;color:#F5821E;">
    <span class="kbd">2</span> 電梯
  </button>
  <button class="type-btn" data-type="corridor" style="border-color:#C8A028;color:#C8A028;">
    <span class="kbd">3</span> 走廊
  </button>
  <button class="type-btn" data-type="mechanical" style="border-color:#2E7D32;color:#2E7D32;">
    <span class="kbd">4</span> 機電
  </button>
  <button class="type-btn" data-type="private" style="border-color:#5078B4;color:#5078B4;">
    <span class="kbd">5</span> 私有
  </button>
  <div class="sep"></div>
  <button id="ocr-toggle" class="on">OCR</button>
  <div class="sep"></div>
  <button id="save-btn" style="padding:4px 12px;border:2px solid #4CAF50;border-radius:4px;
    background:rgba(76,175,80,0.15);color:#4CAF50;cursor:pointer;font-size:12px;font-weight:700;">
    <span class="kbd">S</span> 儲存
  </button>
  <div class="sep"></div>
  <span class="info" id="zoom-info">100%</span>
  <span class="info" id="count-info">0 rooms</span>
</div>

<div id="canvas-wrap">
  <canvas id="c"></canvas>
</div>

<div id="type-popup">
  <button class="popup-btn" data-type="stairwell" style="background:#DC3232;">1 樓梯間</button>
  <button class="popup-btn" data-type="elevator" style="background:#F5821E;">2 電梯</button>
  <button class="popup-btn" data-type="corridor" style="background:#C8A028;">3 走廊</button>
  <button class="popup-btn" data-type="mechanical" style="background:#2E7D32;">4 機電</button>
  <button class="popup-btn" data-type="private" style="background:#5078B4;">5 私有</button>
</div>

<div id="status-bar">
  <span id="mouse-pos">--</span>
  <span>左鍵=畫框/移動 | 右鍵=刪除 | 中鍵拖曳=平移 | 滾輪=縮放 | 1-5=類型 | Ctrl+S=儲存</span>
</div>

<div id="save-indicator">已同步</div>

<script>{fabric_js}</script>
<script>
(function() {{
  // ── Config ──
  const TYPES = {{
    stairwell:  {{ label: '樓梯間', border: '#DC3232', fill: 'rgba(220,50,50,0.20)' }},
    elevator:   {{ label: '電梯',   border: '#F5821E', fill: 'rgba(245,130,30,0.20)' }},
    corridor:   {{ label: '走廊',   border: '#C8A028', fill: 'rgba(200,160,40,0.20)' }},
    mechanical: {{ label: '機電',   border: '#2E7D32', fill: 'rgba(46,125,50,0.20)' }},
    private:    {{ label: '私有',   border: '#5078B4', fill: 'rgba(80,120,180,0.20)' }},
  }};
  const TYPE_KEYS = Object.keys(TYPES);
  const SESSION_KEY = '{session_key}';
  const IMG_W = {image_width};
  const IMG_H = {image_height};
  const IMG_FILENAME = '{image_filename}';
  const SAVE_PATH = '{save_path}';

  let canvas = null;
  window._gtCanvas = null; // debug access
  let isDrawing = false, drawStart = null, drawRect = null;
  let isPanning = false, panStart = null;
  let currentType = 'private';
  let ocrVisible = true;
  let ocrObjects = [];

  function updateTypeButtons() {{
    document.querySelectorAll('.type-btn').forEach(btn => {{
      btn.classList.toggle('active', btn.dataset.type === currentType);
    }});
  }}

  function createAnnotRect(x, y, w, h, type, addToCanvas) {{
    const cfg = TYPES[type] || TYPES.private;
    const rect = new fabric.Rect({{
      left: x, top: y, width: w, height: h,
      fill: cfg.fill, stroke: cfg.border, strokeWidth: 2,
      cornerColor: cfg.border, cornerSize: 8, transparentCorners: false,
      borderColor: cfg.border, borderScaleFactor: 2,
      hasRotatingPoint: false, lockRotation: true,
      annotationType: type, isAnnotation: true,
    }});
    const label = new fabric.Text(cfg.label, {{
      left: x + 4, top: y + 2,
      fontSize: 14, fill: cfg.border, fontWeight: 'bold',
      fontFamily: 'sans-serif',
      selectable: false, evented: false, isLabel: true,
    }});
    rect._label = label;
    if (addToCanvas !== false) {{
      canvas.add(rect);
      canvas.add(label);
    }}
    return rect;
  }}

  function updateLabel(rect) {{
    if (!rect._label) return;
    rect._label.set({{ left: rect.left + 4, top: rect.top + 2 }});
    rect._label.setCoords();
  }}

  function setRectType(rect, type) {{
    const cfg = TYPES[type] || TYPES.private;
    rect.set({{
      fill: cfg.fill, stroke: cfg.border,
      cornerColor: cfg.border, borderColor: cfg.border,
      annotationType: type,
    }});
    if (rect._label) rect._label.set({{ fill: cfg.border, text: cfg.label }});
    canvas.renderAll();
  }}

  function collectAnnotations() {{
    const annotations = [];
    canvas.getObjects('rect').forEach(rect => {{
      if (!rect.isAnnotation) return;
      const type = rect.annotationType || 'private';
      annotations.push({{
        bbox: [Math.round(rect.left), Math.round(rect.top),
               Math.round(rect.width * rect.scaleX), Math.round(rect.height * rect.scaleY)],
        type: type,
        is_public: type !== 'private',
        note: ''
      }});
    }});
    return annotations;
  }}

  function syncAnnotations() {{
    const annotations = collectAnnotations();
    document.getElementById('count-info').textContent = annotations.length + ' rooms';
    // Store in localStorage for Python to read
    localStorage.setItem('gt_annotations_' + SESSION_KEY, JSON.stringify(annotations));
    // Also store in a hidden textarea for Streamlit to access
    let ta = document.getElementById('gt-data-output');
    if (!ta) {{
      ta = document.createElement('textarea');
      ta.id = 'gt-data-output';
      ta.style.display = 'none';
      document.body.appendChild(ta);
    }}
    ta.value = JSON.stringify(annotations);

    // Post message to parent (Streamlit iframe)
    window.parent.postMessage({{
      type: 'gt_annotations',
      key: SESSION_KEY,
      annotations: annotations
    }}, '*');
  }}

  function showTypePopup(rect) {{
    const popup = document.getElementById('type-popup');
    const vpt = canvas.viewportTransform;
    const zoom = canvas.getZoom();
    const cx = rect.left * zoom + vpt[4] + (rect.width * rect.scaleX * zoom) / 2;
    const cy = rect.top * zoom + vpt[5] + 38;
    popup.style.left = Math.min(cx, window.innerWidth - 160) + 'px';
    popup.style.top = Math.min(cy, window.innerHeight - 200) + 'px';
    popup.style.display = 'block';
    popup._targetRect = rect;
  }}
  function hideTypePopup() {{
    document.getElementById('type-popup').style.display = 'none';
  }}

  function renderOCR(blocks) {{
    ocrObjects.forEach(o => canvas.remove(o));
    ocrObjects = [];
    if (!blocks || !blocks.length) return;
    blocks.forEach(b => {{
      const r = new fabric.Rect({{
        left: b.x, top: b.y, width: b.w, height: b.h,
        fill: 'rgba(76,175,80,0.08)', stroke: 'rgba(76,175,80,0.5)',
        strokeWidth: 1, strokeDashArray: [3, 2],
        selectable: false, evented: false, isOCR: true,
      }});
      const t = new fabric.Text(b.text || '', {{
        left: b.x + 2, top: b.y + 1,
        fontSize: Math.min(12, Math.max(8, b.h - 2)),
        fill: 'rgba(76,175,80,0.7)',
        fontFamily: 'sans-serif', fontWeight: '500',
        selectable: false, evented: false, isOCR: true,
      }});
      ocrObjects.push(r, t);
      if (ocrVisible) {{ canvas.add(r); canvas.add(t); }}
    }});
    canvas.renderAll();
  }}

  function toggleOCR() {{
    ocrVisible = !ocrVisible;
    document.getElementById('ocr-toggle').classList.toggle('on', ocrVisible);
    ocrObjects.forEach(o => {{
      if (ocrVisible) canvas.add(o); else canvas.remove(o);
    }});
    canvas.renderAll();
  }}

  // ── Init ──
  function init() {{
    const TOOLBAR_H = 38, STATUS_H = 24;
    const totalH = {component_height};
    const canvasW = window.innerWidth || document.documentElement.clientWidth;
    const canvasH = totalH - TOOLBAR_H - STATUS_H;

    canvas = new fabric.Canvas('c', {{
      width: canvasW, height: canvasH,
      backgroundColor: '#2a2a2a',
      selection: false,
      preserveObjectStacking: true,
      fireRightClick: true,
      fireMiddleClick: true,
      stopContextMenu: true,
    }});
    window._gtCanvas = canvas;

    // Suppress middle-click auto-scroll (browser default)
    canvas.upperCanvasEl.addEventListener('auxclick', e => e.preventDefault());
    canvas.upperCanvasEl.addEventListener('mousedown', e => {{
      if (e.button === 1) e.preventDefault();
    }});

    // Load background image
    const imgSrc = 'data:image/jpeg;base64,{image_b64}';
    fabric.Image.fromURL(imgSrc, function(img) {{
      img.set({{ left: 0, top: 0, selectable: false, evented: false }});
      canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));

      // Fit to view — align top-left, no wasted space
      const fitZoom = Math.min(canvasW / IMG_W, canvasH / IMG_H, 1) * 0.98;
      const tx = (canvasW - IMG_W * fitZoom) / 2; // center horizontally
      const ty = 4; // align to top with small padding
      canvas.setViewportTransform([fitZoom, 0, 0, fitZoom, tx, ty]);
      canvas.requestRenderAll();
      document.getElementById('zoom-info').textContent = Math.round(fitZoom * 100) + '%';

      // Load annotations
      const initAnnotations = {annotations_json};
      initAnnotations.forEach(a => {{
        const [x, y, w, h] = a.bbox;
        createAnnotRect(x, y, w, h, a.type || 'private');
      }});

      // Load OCR
      const ocrBlocks = {ocr_json};
      renderOCR(ocrBlocks);

      syncAnnotations();
      canvas.renderAll();
    }});

    setupEvents();
  }}

  function setupEvents() {{
    // Zoom
    canvas.on('mouse:wheel', opt => {{
      const delta = opt.e.deltaY;
      let zoom = canvas.getZoom();
      zoom *= 0.999 ** delta;
      zoom = Math.max(0.1, Math.min(zoom, 8));
      canvas.zoomToPoint({{ x: opt.e.offsetX, y: opt.e.offsetY }}, zoom);
      document.getElementById('zoom-info').textContent = Math.round(zoom * 100) + '%';
      opt.e.preventDefault();
      opt.e.stopPropagation();
    }});

    // Mouse down
    canvas.on('mouse:down', opt => {{
      const e = opt.e;
      const imgPointer = canvas.getPointer(e);
      hideTypePopup();

      // Right click = delete
      if (e.button === 2) {{
        // Use opt.target (fabric's hit-test respects viewportTransform)
        const target = opt.target;
        if (target && target.isAnnotation) {{
          if (target._label) canvas.remove(target._label);
          canvas.remove(target);
          canvas.discardActiveObject();
          canvas.renderAll();
          syncAnnotations();
        }}
        return;
      }}

      // Middle button (scroll wheel) = pan
      if (e.button === 1) {{
        e.preventDefault();
        isPanning = true;
        panStart = {{ x: e.clientX, y: e.clientY }};
        canvas.defaultCursor = 'grab';
        canvas.upperCanvasEl.style.cursor = 'grab';
        return;
      }}

      // Alt + left = pan (keep as fallback)
      if (e.altKey) {{
        isPanning = true;
        panStart = {{ x: e.clientX, y: e.clientY }};
        canvas.defaultCursor = 'grab';
        canvas.upperCanvasEl.style.cursor = 'grab';
        return;
      }}

      // Click existing rect = select
      if (opt.target && opt.target.isAnnotation) {{
        currentType = opt.target.annotationType || 'private';
        updateTypeButtons();
        return;
      }}

      // Click empty = draw
      if (!opt.target || opt.target.isOCR || opt.target.isLabel) {{
        isDrawing = true;
        drawStart = imgPointer;
        const cfg = TYPES[currentType] || TYPES.private;
        drawRect = new fabric.Rect({{
          left: imgPointer.x, top: imgPointer.y, width: 1, height: 1,
          fill: cfg.fill, stroke: cfg.border, strokeWidth: 2,
          strokeDashArray: [6, 3],
          selectable: false, evented: false, isTemp: true,
        }});
        canvas.add(drawRect);
      }}
    }});

    // Mouse move
    canvas.on('mouse:move', opt => {{
      const e = opt.e;
      const imgPointer = canvas.getPointer(e);
      if (imgPointer.x >= 0 && imgPointer.y >= 0) {{
        document.getElementById('mouse-pos').textContent =
          Math.round(imgPointer.x) + ', ' + Math.round(imgPointer.y) + ' px';
      }}
      if (isPanning) {{
        const dx = e.clientX - panStart.x;
        const dy = e.clientY - panStart.y;
        canvas.relativePan(new fabric.Point(dx, dy));
        panStart = {{ x: e.clientX, y: e.clientY }};
        return;
      }}
      if (isDrawing && drawRect && drawStart) {{
        const x = Math.min(drawStart.x, imgPointer.x);
        const y = Math.min(drawStart.y, imgPointer.y);
        const w = Math.abs(imgPointer.x - drawStart.x);
        const h = Math.abs(imgPointer.y - drawStart.y);
        drawRect.set({{ left: x, top: y, width: w, height: h }});
        canvas.renderAll();
      }}
    }});

    // Mouse up
    canvas.on('mouse:up', opt => {{
      if (isPanning) {{
        isPanning = false;
        canvas.defaultCursor = 'default';
        canvas.upperCanvasEl.style.cursor = 'default';
        return;
      }}
      if (isDrawing && drawRect) {{
        isDrawing = false;
        const w = drawRect.width, h = drawRect.height;
        canvas.remove(drawRect);
        if (w > 5 && h > 5) {{
          const rect = createAnnotRect(drawRect.left, drawRect.top, w, h, currentType);
          canvas.setActiveObject(rect);
          showTypePopup(rect);
          syncAnnotations();
        }}
        drawRect = null;
        drawStart = null;
      }}
    }});

    // Object modified
    canvas.on('object:modified', opt => {{
      if (opt.target && opt.target.isAnnotation) {{
        const t = opt.target;
        t.set({{
          width: Math.round(t.width * t.scaleX),
          height: Math.round(t.height * t.scaleY),
          left: Math.round(t.left), top: Math.round(t.top),
          scaleX: 1, scaleY: 1,
        }});
        t.setCoords();
        updateLabel(t);
        canvas.renderAll();
        syncAnnotations();
      }}
    }});

    canvas.on('object:moving', opt => {{
      if (opt.target && opt.target.isAnnotation) updateLabel(opt.target);
    }});
    canvas.on('object:scaling', opt => {{
      if (opt.target && opt.target.isAnnotation) updateLabel(opt.target);
    }});

    // Keyboard
    document.addEventListener('keydown', e => {{
      if (e.key >= '1' && e.key <= '5') {{
        currentType = TYPE_KEYS[parseInt(e.key) - 1];
        updateTypeButtons();
        const active = canvas.getActiveObject();
        if (active && active.isAnnotation) {{
          setRectType(active, currentType);
          syncAnnotations();
        }}
        return;
      }}
      if (e.key === 'Delete' || e.key === 'Backspace') {{
        const active = canvas.getActiveObject();
        if (active && active.isAnnotation) {{
          if (active._label) canvas.remove(active._label);
          canvas.remove(active);
          canvas.renderAll();
          syncAnnotations();
        }}
      }}
      if (e.key === 'Escape') {{
        canvas.discardActiveObject();
        hideTypePopup();
        canvas.renderAll();
      }}
      if (e.key === 's' && (e.ctrlKey || e.metaKey)) {{
        e.preventDefault();
        saveGT();
      }}
    }});

    // Type popup buttons
    document.querySelectorAll('#type-popup .popup-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const popup = document.getElementById('type-popup');
        const rect = popup._targetRect;
        if (rect) {{
          setRectType(rect, btn.dataset.type);
          currentType = btn.dataset.type;
          updateTypeButtons();
          syncAnnotations();
        }}
        hideTypePopup();
      }});
    }});

    // Toolbar type buttons
    document.querySelectorAll('.type-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        currentType = btn.dataset.type;
        updateTypeButtons();
        const active = canvas.getActiveObject();
        if (active && active.isAnnotation) {{
          setRectType(active, currentType);
          syncAnnotations();
        }}
      }});
    }});

    // OCR toggle
    document.getElementById('ocr-toggle').addEventListener('click', toggleOCR);

    // Save button
    document.getElementById('save-btn').addEventListener('click', saveGT);
  }}

  function saveGT() {{
    const annotations = collectAnnotations();
    if (annotations.length === 0) {{
      showSaveIndicator('⚠ 無標註可儲存', '#F5821E');
      return;
    }}
    const now = new Date().toISOString();
    const gt = {{
      image: IMG_FILENAME,
      created: now,
      num_rooms: annotations.length,
      num_public: annotations.filter(a => a.is_public).length,
      num_private: annotations.filter(a => !a.is_public).length,
      annotations: annotations,
    }};
    const jsonStr = JSON.stringify(gt, null, 2);

    // POST to save endpoint (local HTTP server on port {_SAVE_PORT})
    showSaveIndicator('儲存中...', '#F5821E', 10000);
    fetch('http://127.0.0.1:{_SAVE_PORT}/gt_save', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ path: SAVE_PATH, data: jsonStr }}),
    }}).then(r => r.json()).then(res => {{
      const n = annotations.length;
      const ov = res.overlap || {{}};
      let overlapMsg = '';
      if (ov.overlap_pairs > 0) {{
        overlapMsg = ' | ' + ov.overlap_pairs + ' 重疊';
        if (ov.dropped_count > 0) overlapMsg += ', ' + ov.dropped_count + ' 將被裁剪';
      }}
      if (res.git === 'pushed') {{
        showSaveIndicator('已推送 GitHub (' + n + ' rooms' + overlapMsg + ')', '#4CAF50');
      }} else if (res.git === 'committed') {{
        showSaveIndicator('已 commit（push 失敗）(' + n + ' rooms' + overlapMsg + ')', '#F5821E');
      }} else if (res.git === 'no_change') {{
        showSaveIndicator('無變更 (' + n + ' rooms)', '#888');
      }} else {{
        showSaveIndicator('已存本地 (' + n + ' rooms' + overlapMsg + ')', '#4CAF50');
      }}
    }}).catch(() => {{
      // Fallback: download as file
      downloadJSON(jsonStr);
    }});
  }}

  function downloadJSON(jsonStr) {{
    const blob = new Blob([jsonStr], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = IMG_FILENAME.replace(/\\.[^.]+$/, '') + '_ground_truth.json';
    a.click();
    URL.revokeObjectURL(url);
    showSaveIndicator('已下載 JSON', '#F5821E');
  }}

  function showSaveIndicator(msg, color, duration) {{
    const el = document.getElementById('save-indicator');
    el.textContent = msg;
    el.style.background = 'rgba(' + (color === '#4CAF50' ? '76,175,80' : color === '#F5821E' ? '245,130,30' : '136,136,136') + ',0.9)';
    el.style.display = 'block';
    if (el._timer) clearTimeout(el._timer);
    el._timer = setTimeout(() => {{ el.style.display = 'none'; }}, duration || 3000);
  }}

  updateTypeButtons();
  init();
}})();
</script>
</body>
</html>"""


def gt_annotator(
    image_path: str,
    image_width: int,
    image_height: int,
    annotations: list[dict] | None = None,
    ocr_blocks: list[dict] | None = None,
    component_height: int = 800,
    key: str | None = None,
    save_path: str = "",
) -> None:
    """渲染 GT 標註元件。

    使用 st.components.v1.html() 內嵌 fabric.js canvas。
    儲存功能由 canvas 內的 Save 按鈕處理（下載 JSON 或 POST 到 /gt_save）。
    """
    session_key = key or "gt_default"
    _start_save_server()
    image_b64 = _image_to_base64(image_path)
    image_filename = os.path.basename(image_path)

    html_content = _build_html(
        image_b64=image_b64,
        image_width=image_width,
        image_height=image_height,
        annotations=annotations or [],
        ocr_blocks=ocr_blocks or [],
        component_height=component_height,
        session_key=session_key,
        image_filename=image_filename,
        save_path=save_path.replace('\\', '/'),
    )

    # Render the HTML component
    components.html(html_content, height=component_height, scrolling=False)
