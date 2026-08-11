"""스텝 캡처: 클릭할 때마다 클릭한 창을 자동 캡처하고 번호 배지를 찍어,
단계별 매뉴얼 이미지를 자동으로 만들어 준다 (Snagit Step Capture의 HWP 사용자용 버전).

동작 흐름
1. 시작하면 화면 위쪽에 작은 조작 바가 뜨고, 전역 마우스 훅이 클릭을 감시한다.
2. 사용자가 어딘가를 클릭하면 잠시 뒤(메뉴가 열리는 시간을 기다렸다가) 그 창을 캡처한다.
3. '완료'를 누르면 캡처들을 세로로 이어붙인 매뉴얼 이미지가 편집 창으로 열린다.
"""
from __future__ import annotations

import ctypes
import os
import queue
import threading
from ctypes import wintypes
from typing import TYPE_CHECKING

import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageGrab

from ui import FONT, pill_button
from windowpick import window_rect_at

if TYPE_CHECKING:
    from app import CaptureApp

WH_MOUSE_LL, WM_LBUTTONDOWN, WM_QUIT = 14, 0x0201, 0x0012


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", _POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class ClickListener(threading.Thread):
    """전역 왼쪽 클릭 좌표를 큐로 보내는 저수준 마우스 훅. 콜백은 즉시 반환해 시스템을 느리게 하지 않는다."""
    daemon = True

    def __init__(self, clicks: queue.Queue):
        super().__init__(name="HwpCaptureStepHook")
        self.clicks = clicks
        self.thread_id = None
        self.ready = threading.Event()

    def run(self):
        user32 = ctypes.windll.user32
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        @HOOKPROC
        def proc(code, wparam, lparam):
            if code >= 0 and wparam == WM_LBUTTONDOWN:
                info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                self.clicks.put((info.pt.x, info.pt.y))
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._proc = proc  # 가비지 컬렉션되지 않게 참조를 붙잡아 둔다.
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            pass
        if hook:
            user32.UnhookWindowsHookEx(ctypes.c_void_p(hook))

    def stop(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


class StepCaptureSession:
    def __init__(self, app: "CaptureApp"):
        self.app = app
        self.steps: list[Image.Image] = []
        self.active = True
        app.root.withdraw()

        # 화면 위 가운데의 작은 조작 바
        self.bar = tk.Toplevel(app.root)
        self.bar.overrideredirect(True); self.bar.attributes("-topmost", True)
        self.bar.configure(bg="#e7e3db")
        body = tk.Frame(self.bar, bg="#ffffff"); body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(body, text="● 스텝 캡처", bg="#ffffff", fg="#e5484d", font=(FONT, 10, "bold")).pack(side="left", padx=(14, 6), pady=9)
        self.count_label = tk.Label(body, text="클릭하면 자동으로 캡처됩니다 · 0단계", bg="#ffffff", fg="#57554f", font=(FONT, 10))
        self.count_label.pack(side="left", padx=(0, 12))
        pill_button(body, "완료", self.finish, primary=True, font_size=9, height=30, width=70).pack(side="left", padx=(0, 5), pady=6)
        pill_button(body, "취소", self.cancel, font_size=9, height=30, width=64).pack(side="left", padx=(0, 12))
        self.bar.update_idletasks()
        width = self.bar.winfo_reqwidth()
        self.bar.geometry(f"+{(self.bar.winfo_screenwidth() - width) // 2}+16")

        self.clicks: queue.Queue = queue.Queue()
        self.listener = ClickListener(self.clicks)
        self.listener.start(); self.listener.ready.wait(1.5)
        self.app.root.after(60, self.poll)

    def bar_rect(self):
        return (self.bar.winfo_rootx(), self.bar.winfo_rooty(),
                self.bar.winfo_rootx() + self.bar.winfo_width(), self.bar.winfo_rooty() + self.bar.winfo_height())

    def poll(self):
        if not self.active:
            return
        while True:
            try:
                x, y = self.clicks.get_nowait()
            except queue.Empty:
                break
            left, top, right, bottom = self.bar_rect()
            if left <= x < right and top <= y < bottom:
                continue  # 조작 바 클릭은 캡처하지 않는다.
            # 클릭 효과(메뉴 열림 등)가 화면에 나타난 뒤 캡처되도록 잠시 기다린다.
            self.app.root.after(220, lambda cx=x, cy=y: self.capture_step(cx, cy))
        self.app.root.after(60, self.poll)

    def capture_step(self, x, y):
        if not self.active:
            return
        rect = window_rect_at(x, y)
        if rect is None:
            # 창을 못 찾으면 클릭 주변 900x560 영역을 캡처한다.
            rect = (x - 450, y - 180, x + 450, y + 380)
        try:
            image = ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")
        except OSError:
            return
        self._draw_badge(image, x - rect[0], y - rect[1], len(self.steps) + 1)
        self.steps.append(image)
        self.count_label.config(text=f"클릭하면 자동으로 캡처됩니다 · {len(self.steps)}단계")

    @staticmethod
    def _draw_badge(image, x, y, number):
        """클릭 지점에 빨간 번호 배지를 그린다."""
        draw = ImageDraw.Draw(image)
        radius = 24
        x = max(radius, min(image.width - radius, x))
        y = max(radius, min(image.height - radius, y))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="#e5484d", outline="white", width=3)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 26)
        except OSError:
            font = ImageFont.load_default()
        text = str(number)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((x - (box[2] - box[0]) / 2 - box[0], y - (box[3] - box[1]) / 2 - box[1]), text, fill="white", font=font)

    def stitch(self):
        """캡처한 단계들을 같은 폭으로 맞춰 세로로 이어붙인다."""
        width = min(1400, max(step.width for step in self.steps))
        gap, pieces = 24, []
        for step in self.steps:
            height = max(1, round(step.height * width / step.width))
            pieces.append(step.resize((width, height), Image.Resampling.LANCZOS))
        total = sum(piece.height for piece in pieces) + gap * (len(pieces) - 1)
        combined = Image.new("RGB", (width, total), "white")
        offset = 0
        for index, piece in enumerate(pieces):
            combined.paste(piece, (0, offset))
            offset += piece.height
            if index < len(pieces) - 1:
                ImageDraw.Draw(combined).line((0, offset + gap // 2, width, offset + gap // 2), fill="#e7e3db", width=2)
                offset += gap
        return combined

    def _teardown(self):
        self.active = False
        self.listener.stop()
        self.bar.destroy()
        self.app.step_session = None

    def finish(self):
        steps = self.steps
        self._teardown()
        if not steps:
            self.app.toast("스텝 캡처", "캡처된 단계가 없습니다.")
            return
        from editor import CaptureEditor  # 순환 import 방지
        combined = self.stitch() if len(steps) > 1 else steps[0]
        CaptureEditor(self.app, combined)

    def cancel(self):
        self._teardown()
        self.app.toast("스텝 캡처 취소", "캡처한 단계를 버렸습니다.")
