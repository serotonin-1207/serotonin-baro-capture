"""캡처를 항상-위 플로팅 창으로 화면에 붙여두는 '화면 고정' 기능 (Snipaste 스타일).

드래그로 이동, 마우스 휠로 크기 조절, 더블클릭/Esc로 닫기, 우클릭 메뉴 제공.
문서를 만들면서 참고 자료를 옆에 붙여둘 때 쓴다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk

from PIL import Image, ImageTk

if TYPE_CHECKING:
    from app import CaptureApp


class PinnedImage(tk.Toplevel):
    def __init__(self, app: "CaptureApp", image: Image.Image):
        super().__init__(app.root)
        self.app, self.original = app, image.convert("RGB")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # 화면의 절반을 넘으면 알맞게 줄여서 시작한다.
        max_w, max_h = round(self.winfo_screenwidth() * 0.55), round(self.winfo_screenheight() * 0.55)
        self.scale = min(1.0, max_w / image.width, max_h / image.height)
        self.photo = None
        self.label = tk.Label(self, bd=0, highlightthickness=2, highlightbackground="#3478f6", cursor="fleur")
        self.label.pack()
        self.render()
        # 마우스 근처에 띄우되 화면 밖으로 나가지 않게 한다.
        x = min(self.winfo_pointerx() + 16, self.winfo_screenwidth() - round(image.width * self.scale) - 16)
        y = min(self.winfo_pointery() + 16, self.winfo_screenheight() - round(image.height * self.scale) - 60)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._drag_start = None
        self.label.bind("<ButtonPress-1>", self._drag_begin)
        self.label.bind("<B1-Motion>", self._drag_move)
        self.label.bind("<MouseWheel>", self._wheel)
        self.label.bind("<Double-Button-1>", lambda _e: self.destroy())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.label.bind("<Button-3>", self._show_menu)

        self.menu = tk.Menu(self, tearoff=False, font=("맑은 고딕", 10))
        self.menu.add_command(label="📋 클립보드 복사", command=self._copy)
        self.menu.add_command(label="💾 저장", command=self._save)
        self.menu.add_command(label="✎ 편집으로 열기", command=self._edit)
        self.menu.add_command(label="↺ 원본 크기", command=self._reset_size)
        self.menu.add_separator()
        self.menu.add_command(label="✕ 닫기 (더블클릭)", command=self.destroy)

    def render(self):
        width = max(60, round(self.original.width * self.scale))
        height = max(40, round(self.original.height * self.scale))
        self.photo = ImageTk.PhotoImage(self.original.resize((width, height), Image.Resampling.LANCZOS))
        self.label.configure(image=self.photo)

    def _drag_begin(self, event):
        self._drag_start = (event.x, event.y)

    def _drag_move(self, event):
        if self._drag_start:
            x = self.winfo_x() + event.x - self._drag_start[0]
            y = self.winfo_y() + event.y - self._drag_start[1]
            self.geometry(f"+{x}+{y}")

    def _wheel(self, event):
        self.scale = max(0.2, min(3.0, self.scale + (0.1 if event.delta > 0 else -0.1)))
        self.render()

    def _reset_size(self):
        self.scale = 1.0
        self.render()

    def _show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def _copy(self):
        self.app.copy_image(self.original)
        self.app.toast("클립보드 복사 완료", "고정된 이미지를 복사했습니다.")

    def _save(self):
        path = self.app.save_image(self.original)
        self.app.record_capture(path)
        self.app.toast("이미지 저장 완료", path.name)

    def _edit(self):
        from editor import CaptureEditor  # 순환 import 방지
        image = self.original
        self.destroy()
        CaptureEditor(self.app, image)
