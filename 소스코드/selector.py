from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

import tkinter as tk

if TYPE_CHECKING:
    from app import CaptureApp


class ScreenSelector(tk.Toplevel):
    def __init__(self, app: "CaptureApp"):
        super().__init__(app.root)
        self.app, self.start, self.rectangle = app, None, None
        color = {"빨강": "#ef4444", "초록": "#22c55e", "파랑": "#3b82f6", "노랑": "#facc15"}[app.settings["guide_color"]]
        # -fullscreen은 주 모니터만 덮으므로, 모든 모니터를 합친 가상 화면 크기로 창을 만든다.
        user32 = ctypes.windll.user32
        self.origin = (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77))  # SM_X/YVIRTUALSCREEN
        width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)  # SM_CX/CYVIRTUALSCREEN
        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{self.origin[0]}+{self.origin[1]}")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.28 if app.settings["show_overlay"] else 0.03)
        self.configure(cursor="crosshair", bg="#111827")
        self.canvas = tk.Canvas(self, bg="#111827", highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.color = color
        self.canvas.bind("<ButtonPress-1>", self.begin); self.canvas.bind("<B1-Motion>", self.draw); self.canvas.bind("<ButtonRelease-1>", self.finish)
        self.bind("<Escape>", lambda _event: self.destroy()); self.focus_force()

    def begin(self, event):
        self.start = (event.x_root, event.y_root)
        self.rectangle = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline=self.color, width=3)

    def draw(self, event):
        if self.rectangle:
            # 캔버스 좌표 = 화면 좌표 - 가상 화면 원점 (모니터가 주 모니터 왼쪽/위에 있으면 원점이 음수다.)
            x, y = self.start[0] - self.origin[0], self.start[1] - self.origin[1]
            self.canvas.coords(self.rectangle, x, y, event.x, event.y)

    def finish(self, event):
        if not self.start: return
        x, y = self.start; left, top = min(x, event.x_root), min(y, event.y_root); right, bottom = max(x, event.x_root), max(y, event.y_root)
        self.destroy()
        if right - left > 3 and bottom - top > 3: self.app.root.after(120, lambda: self.app.capture((left, top, right, bottom)))
