"""창 캡처: 마우스 아래 창을 자동 인식해 파란 테두리로 보여 주고, 클릭 한 번으로 캡처한다."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import TYPE_CHECKING

import tkinter as tk

if TYPE_CHECKING:
    from app import CaptureApp

DWMWA_EXTENDED_FRAME_BOUNDS = 9   # 그림자를 뺀 실제 창 테두리
DWMWA_CLOAKED = 14                # 보이지 않게 숨겨진 UWP 창 표시


def visible_window_rects(exclude_pid: int) -> list[tuple[int, int, int, int]]:
    """화면에 보이는 최상위 창들의 사각형을 Z순서(위부터)로 돌려준다."""
    user32 = ctypes.windll.user32
    try:
        dwmapi = ctypes.windll.dwmapi
    except OSError:
        dwmapi = None
    rects: list[tuple[int, int, int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == exclude_pid:
            return True  # 우리 프로그램 창(오버레이 포함)은 후보에서 뺀다.
        if dwmapi is not None:
            cloaked = wintypes.DWORD()
            if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
                return True
        rect = wintypes.RECT()
        got = False
        if dwmapi is not None:
            got = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)) == 0
        if not got and not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        if rect.right - rect.left < 40 or rect.bottom - rect.top < 40:
            return True
        rects.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    user32.EnumWindows(callback, 0)
    return rects


def window_rect_at(x: int, y: int, exclude_pid: int | None = None) -> tuple[int, int, int, int] | None:
    """지정한 화면 좌표를 포함하는 가장 위의 창 사각형."""
    for rect in visible_window_rects(exclude_pid if exclude_pid is not None else os.getpid()):
        if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
            return rect
    return None


class WindowPicker(tk.Toplevel):
    def __init__(self, app: "CaptureApp"):
        super().__init__(app.root)
        self.app = app
        user32 = ctypes.windll.user32
        self.origin = (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77))
        width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        self.overrideredirect(True)
        self.geometry(f"{width}x{height}+{self.origin[0]}+{self.origin[1]}")
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.25)
        self.configure(bg="#111827", cursor="hand2")
        self.canvas = tk.Canvas(self, bg="#111827", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # 오버레이를 띄우기 전에 창 목록을 한 번 읽어 두고 마우스 이동마다 조회한다.
        self.windows = visible_window_rects(os.getpid())
        self.target = None
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Button-1>", self._pick)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.focus_force()

    def _hover(self, event):
        x, y = event.x_root, event.y_root
        target = None
        for rect in self.windows:
            if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                target = rect
                break
        if target == self.target:
            return
        self.target = target
        self.canvas.delete("all")
        if target:
            left, top = target[0] - self.origin[0], target[1] - self.origin[1]
            right, bottom = target[2] - self.origin[0], target[3] - self.origin[1]
            self.canvas.create_rectangle(left, top, right, bottom, outline="#3478f6", width=4, fill="#3478f6", stipple="gray12")
            self.canvas.create_text(left + 12, top + 12, anchor="nw", fill="#ffffff",
                                    text=f"{target[2]-target[0]} × {target[3]-target[1]}  ·  클릭하면 캡처", font=("맑은 고딕", 11, "bold"))

    def _pick(self, _event):
        target = self.target
        self.destroy()
        if target:
            self.app.root.after(150, lambda: self.app.capture(target))
