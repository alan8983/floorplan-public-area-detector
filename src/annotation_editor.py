#!/usr/bin/env python3
"""標註編輯器 — OpenCV GUI 工具，用於校對 auto_annotate 產出的 ground truth。

功能：
  - 點選 bbox → 修改類型（循環切換 / 按數字鍵指定）
  - 右鍵點選 bbox → 刪除
  - 拖曳畫新的 bbox → 指定類型
  - 存檔覆蓋回 JSON

操作說明：
  滑鼠：
    左鍵單擊 bbox     → 選取（黃色高亮）
    左鍵拖曳空白處     → 畫新 bbox
    右鍵單擊 bbox     → 刪除（需確認按 Y）

  鍵盤（選取狀態下）：
    0 = stairwell      1 = elevator      2 = corridor
    3 = lobby          4 = mechanical    5 = private
    Tab                → 循環切換類型
    Delete / Backspace → 刪除選取的 bbox

  全域：
    S / Ctrl+S         → 存檔
    Z / Ctrl+Z         → 復原（最多 50 步）
    N / →              → 下一張圖
    P / ←              → 上一張圖
    Q / Esc            → 離開

用法：
    python src/annotation_editor.py samples/annotations/tku_biz_1F_gt_draft.json

    # 批次模式（載入目錄下所有 JSON，可翻頁）
    python src/annotation_editor.py samples/annotations/
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

# ── 類別定義 ──
TYPES = ["stairwell", "elevator", "corridor", "lobby", "mechanical", "private"]
TYPE_ZH = {
    "stairwell": "樓梯間", "elevator": "電梯", "corridor": "走廊",
    "lobby": "梯廳/門廳", "mechanical": "機電空間", "private": "私有空間",
    "living_room": "客廳", "kitchen": "廚房", "bedroom": "臥室",
    "bathroom": "浴室", "balcony": "陽台", "storage": "儲藏室",
    "entrance": "玄關", "private_large": "私有空間(大)",
}
PUBLIC_TYPES = {"stairwell", "elevator", "corridor", "lobby", "mechanical"}

# BGR 顏色
COLORS = {
    "stairwell": (83, 168, 52), "elevator": (244, 133, 66),
    "corridor": (4, 188, 251), "lobby": (188, 71, 171),
    "mechanical": (193, 172, 0), "private": (0, 0, 200),
}
COLOR_SELECTED = (0, 255, 255)  # 黃色
COLOR_DRAWING = (255, 128, 0)   # 橘色

MAX_UNDO = 50
WINDOW_NAME = "Annotation Editor"


class AnnotationEditor:
    def __init__(self, json_files: list[str], images_dir: str = None):
        self.json_files = json_files
        self.images_dir = images_dir
        self.current_idx = 0

        # 編輯狀態
        self.data = None
        self.annotations = []
        self.img_orig = None
        self.img_h = 0
        self.img_w = 0
        self.selected = -1  # 選取的 bbox index
        self.undo_stack = []
        self.modified = False

        # 顯示狀態
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # 拖曳狀態
        self.drawing = False
        self.drag_start = None
        self.drag_end = None

    def load_current(self):
        """載入當前 JSON + 對應圖片。"""
        json_path = self.json_files[self.current_idx]
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.annotations = self.data.get("annotations", [])
        self.selected = -1
        self.undo_stack = []
        self.modified = False

        # 載入原圖
        image_name = self.data["image"]
        img_path = self._find_image(image_name)
        if img_path and os.path.exists(img_path):
            self.img_orig = cv2.imread(img_path)
        else:
            # 產生空白圖
            w, h = self.data.get("image_size", [1500, 1000])
            self.img_orig = np.ones((h, w, 3), np.uint8) * 200
            cv2.putText(self.img_orig, f"Image not found: {image_name}",
                        (50, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        self.img_h, self.img_w = self.img_orig.shape[:2]
        self._fit_window()

    def _find_image(self, image_name: str) -> str:
        """搜尋原圖路徑。"""
        # 同目錄
        json_dir = os.path.dirname(self.json_files[self.current_idx])
        candidate = os.path.join(json_dir, image_name)
        if os.path.exists(candidate):
            return candidate
        # images_dir
        if self.images_dir:
            for root, _, files in os.walk(self.images_dir):
                if image_name in files:
                    return os.path.join(root, image_name)
        return None

    def _fit_window(self):
        """計算縮放比例以適應螢幕。"""
        screen_w, screen_h = 1600, 900
        self.scale = min(screen_w / self.img_w, screen_h / self.img_h, 1.0)

    def _push_undo(self):
        """存入復原堆疊。"""
        if len(self.undo_stack) >= MAX_UNDO:
            self.undo_stack.pop(0)
        self.undo_stack.append(copy.deepcopy(self.annotations))

    def _undo(self):
        if self.undo_stack:
            self.annotations = self.undo_stack.pop()
            self.selected = -1
            self.modified = True

    def _screen_to_img(self, sx, sy):
        """螢幕座標 → 圖片座標。"""
        ix = int(sx / self.scale)
        iy = int(sy / self.scale)
        return ix, iy

    def _hit_test(self, ix, iy) -> int:
        """點擊測試：回傳被點到的 bbox index，-1 表示沒有。"""
        for i, ann in enumerate(self.annotations):
            x, y, w, h = ann["bbox"]
            if x <= ix <= x + w and y <= iy <= y + h:
                return i
        return -1

    def render(self) -> np.ndarray:
        """繪製當前畫面。"""
        vis = self.img_orig.copy()

        for i, ann in enumerate(self.annotations):
            x, y, w, h = ann["bbox"]
            is_pub = ann.get("is_public", ann["type"] in PUBLIC_TYPES)
            color = COLORS.get(ann["type"], COLORS["private"])

            # 半透明填充
            overlay = vis.copy()
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
            vis = cv2.addWeighted(vis, 0.75, overlay, 0.25, 0)

            # 外框
            thick = 3 if i == self.selected else 2
            draw_color = COLOR_SELECTED if i == self.selected else color
            cv2.rectangle(vis, (x, y), (x + w, y + h), draw_color, thick)

            # 標籤
            tag = TYPE_ZH.get(ann["type"], ann["type"])
            label = f"[{i}] {tag}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            fs = max(0.35, min(self.img_h, self.img_w) / 4000)
            (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
            cv2.rectangle(vis, (x, y - th - 6), (x + tw + 4, y), (255, 255, 255), -1)
            cv2.putText(vis, label, (x + 2, y - 4), font, fs, draw_color, 1, cv2.LINE_AA)

        # 正在畫的 bbox
        if self.drawing and self.drag_start and self.drag_end:
            x1, y1 = self.drag_start
            x2, y2 = self.drag_end
            cv2.rectangle(vis, (x1, y1), (x2, y2), COLOR_DRAWING, 2)

        # HUD
        hud_lines = [
            f"[{self.current_idx+1}/{len(self.json_files)}] {self.data['image']}",
            f"Annotations: {len(self.annotations)}  {'*MODIFIED*' if self.modified else ''}",
            "Keys: 0-5=type  Tab=cycle  Del=delete  S=save  Z=undo  N/P=nav  Q=quit",
        ]
        if self.selected >= 0:
            ann = self.annotations[self.selected]
            hud_lines.append(
                f"Selected [{self.selected}]: {ann['type']} "
                f"bbox={ann['bbox']} is_public={ann.get('is_public', '?')}")

        for j, line in enumerate(hud_lines):
            y_pos = 20 + j * 22
            cv2.putText(vis, line, (8, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(vis, line, (8, y_pos), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # 縮放
        if self.scale != 1.0:
            new_w = int(self.img_w * self.scale)
            new_h = int(self.img_h * self.scale)
            vis = cv2.resize(vis, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return vis

    def _mouse_callback(self, event, x, y, flags, param):
        ix, iy = self._screen_to_img(x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            hit = self._hit_test(ix, iy)
            if hit >= 0:
                self.selected = hit
            else:
                # 開始拖曳畫新 bbox
                self.drawing = True
                self.drag_start = (ix, iy)
                self.drag_end = (ix, iy)
                self.selected = -1

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.drag_end = (ix, iy)

        elif event == cv2.EVENT_LBUTTONUP:
            if self.drawing:
                self.drawing = False
                if self.drag_start and self.drag_end:
                    x1, y1 = self.drag_start
                    x2, y2 = self.drag_end
                    bx = min(x1, x2)
                    by = min(y1, y2)
                    bw = abs(x2 - x1)
                    bh = abs(y2 - y1)
                    # 忽略太小的拖曳（可能是誤觸）
                    if bw > 10 and bh > 10:
                        self._push_undo()
                        new_ann = {
                            "bbox": [bx, by, bw, bh],
                            "type": "private",
                            "type_zh": "私有空間",
                            "is_public": False,
                            "confidence": "manual",
                            "area": bw * bh,
                            "aspect_ratio": round(bw / max(bh, 1), 3),
                            "solidity": 1.0,
                        }
                        self.annotations.append(new_ann)
                        self.selected = len(self.annotations) - 1
                        self.modified = True
                self.drag_start = None
                self.drag_end = None

        elif event == cv2.EVENT_RBUTTONDOWN:
            hit = self._hit_test(ix, iy)
            if hit >= 0:
                self._push_undo()
                self.annotations.pop(hit)
                self.selected = -1
                self.modified = True

    def _set_type(self, type_name: str):
        """修改選取 bbox 的類型。"""
        if self.selected < 0 or self.selected >= len(self.annotations):
            return
        self._push_undo()
        ann = self.annotations[self.selected]
        ann["type"] = type_name
        ann["type_zh"] = TYPE_ZH.get(type_name, type_name)
        ann["is_public"] = type_name in PUBLIC_TYPES
        ann["confidence"] = "manual"
        self.modified = True

    def _cycle_type(self):
        """循環切換選取 bbox 的類型。"""
        if self.selected < 0:
            return
        current = self.annotations[self.selected]["type"]
        try:
            idx = TYPES.index(current)
        except ValueError:
            idx = -1
        next_type = TYPES[(idx + 1) % len(TYPES)]
        self._set_type(next_type)

    def save(self):
        """存檔覆蓋回 JSON。"""
        json_path = self.json_files[self.current_idx]
        self.data["annotations"] = self.annotations
        self.data["num_rooms"] = len(self.annotations)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        self.modified = False
        print(f"  [SAVED] {json_path} ({len(self.annotations)} annotations)")

    def _confirm_discard(self) -> bool:
        """確認放棄修改。"""
        if not self.modified:
            return True
        print("  [WARNING] 有未存檔的修改。按 S 存檔，按任意鍵放棄。")
        key = cv2.waitKey(0) & 0xFF
        if key == ord('s') or key == ord('S'):
            self.save()
        return True

    def run(self):
        """主迴圈。"""
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WINDOW_NAME, self._mouse_callback)

        self.load_current()

        while True:
            vis = self.render()
            cv2.imshow(WINDOW_NAME, vis)
            key = cv2.waitKey(30) & 0xFF

            if key == 255:  # 無按鍵
                continue

            # 數字鍵 0-5：指定類型
            if ord('0') <= key <= ord('5'):
                idx = key - ord('0')
                if idx < len(TYPES):
                    self._set_type(TYPES[idx])

            elif key == 9:  # Tab
                self._cycle_type()

            elif key in (8, 255, 0):  # Backspace / Delete
                pass  # 某些平台的 delete 碼不同
            elif key == 46 or key == 8:  # Delete key
                if self.selected >= 0:
                    self._push_undo()
                    self.annotations.pop(self.selected)
                    self.selected = -1
                    self.modified = True

            elif key == ord('s') or key == ord('S'):
                self.save()

            elif key == ord('z') or key == ord('Z'):
                self._undo()

            elif key == ord('n') or key == ord('N') or key == 83:  # → arrow
                if self.current_idx < len(self.json_files) - 1:
                    self._confirm_discard()
                    self.current_idx += 1
                    self.load_current()

            elif key == ord('p') or key == ord('P') or key == 81:  # ← arrow
                if self.current_idx > 0:
                    self._confirm_discard()
                    self.current_idx -= 1
                    self.load_current()

            elif key == ord('q') or key == ord('Q') or key == 27:  # Esc
                self._confirm_discard()
                break

        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description="標註編輯器 — OpenCV GUI 校對 ground truth")
    parser.add_argument("input", help="JSON 檔案或包含 *_gt_draft.json 的目錄")
    parser.add_argument("--images-dir", default="samples",
                        help="原圖搜尋目錄 (預設: samples/)")
    args = parser.parse_args()

    p = Path(args.input)
    if p.is_file() and p.suffix == ".json":
        json_files = [str(p)]
    elif p.is_dir():
        json_files = sorted(str(f) for f in p.glob("*_gt_draft.json"))
    else:
        print(f"[ERROR] 無效輸入: {args.input}")
        sys.exit(1)

    if not json_files:
        print(f"[ERROR] 找不到 *_gt_draft.json: {args.input}")
        sys.exit(1)

    print(f"=== 標註編輯器 ===")
    print(f"JSON 檔案: {len(json_files)}")
    print(f"原圖搜尋: {args.images_dir}")
    print()
    print("操作：左鍵=選取/畫框  右鍵=刪除  0-5=類型  Tab=循環  S=存  Z=復原  N/P=翻頁  Q=離開")
    print()

    editor = AnnotationEditor(json_files, images_dir=args.images_dir)
    editor.run()


if __name__ == "__main__":
    main()
