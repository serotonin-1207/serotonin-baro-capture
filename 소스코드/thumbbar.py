"""캡처 직후 화면 우하단에 뜨는 CleanShot식 플로팅 미리보기 카드.

캡처는 이미 클립보드/자동저장으로 처리된 뒤이므로, 이 카드는
'다음에 무엇을 할지'(편집·복사·텍스트 추출·닫기)만 빠르게 고르는 용도다.
잠시 두면 스스로 사라지고, 마우스를 올리면 타이머가 멈춘다.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import tkinter as tk

from PIL import Image, ImageTk

from config import APP_NAME
from ui import BORDER, CARD, FONT, MUTED, TEXT, pill_button

if TYPE_CHECKING:
    from app import CaptureApp

LIFETIME_MS = 9000  # 이 시간 동안 아무 조작이 없으면 자동으로 닫힌다.
TICK_MS = 90


class FloatingThumbnail(tk.Toplevel):
    def __init__(self, app: "CaptureApp", image: Image.Image, auto_saved_path: Path | None = None):
        super().__init__(app.root)
        self.app, self.image, self.auto_saved_path = app, image, auto_saved_path
        self.remaining = LIFETIME_MS
        self.paused = False
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BORDER)  # 1px 경계 역할

        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        # 미리보기 (클릭하면 편집으로)
        thumb = image.copy(); thumb.thumbnail((280, 170))
        self.photo = ImageTk.PhotoImage(thumb)
        preview = tk.Label(body, image=self.photo, bg=CARD, cursor="hand2")
        preview.pack(padx=10, pady=(10, 6))
        preview.bind("<Button-1>", lambda _e: self.edit())

        caption = "클립보드에 복사됨 · 클릭하면 편집" if app.settings["copy_to_clipboard"] else "클릭하면 편집"
        tk.Label(body, text=caption, bg=CARD, fg=MUTED, font=(FONT, 8)).pack()

        actions = tk.Frame(body, bg=CARD)
        actions.pack(pady=(6, 8))
        pill_button(actions, "편집", self.edit, primary=True, font_size=9, height=28, width=60).pack(side="left", padx=2)
        pill_button(actions, "고정", self.pin, font_size=9, height=28, width=56).pack(side="left", padx=2)
        pill_button(actions, "저장", self.save, font_size=9, height=28, width=56).pack(side="left", padx=2)
        pill_button(actions, "텍스트", self.extract_text, font_size=9, height=28, width=60).pack(side="left", padx=2)
        pill_button(actions, "✕", self.close, font_size=9, height=28, width=36, fg=MUTED).pack(side="left", padx=2)

        # 남은 시간 게이지 (하단 얇은 줄)
        self.gauge = tk.Canvas(body, height=3, bg=CARD, highlightthickness=0)
        self.gauge.pack(fill="x", side="bottom")

        self.bind("<Enter>", lambda _e: self.set_paused(True))
        self.bind("<Leave>", lambda _e: self.set_paused(False))
        self.bind("<Escape>", lambda _e: self.close())

        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = self.winfo_screenwidth() - width - 24
        y = self.winfo_screenheight() - height - 70  # 작업표시줄 위
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.lift()
        self.after(TICK_MS, self.tick)

    def set_paused(self, paused: bool):
        self.paused = paused

    def tick(self):
        if not self.winfo_exists():
            return
        if not self.paused:
            self.remaining -= TICK_MS
            if self.remaining <= 0:
                self.close(); return
        try:
            width = self.gauge.winfo_width()
            self.gauge.delete("all")
            self.gauge.create_rectangle(0, 0, width * self.remaining / LIFETIME_MS, 3, fill="#3478f6", outline="")
        except tk.TclError:
            return
        self.after(TICK_MS, self.tick)

    def edit(self):
        from editor import CaptureEditor  # 순환 import 방지
        image, path = self.image, self.auto_saved_path
        self.close()
        CaptureEditor(self.app, image, path)

    def pin(self):
        from pin import PinnedImage
        image = self.image
        self.close()
        PinnedImage(self.app, image)

    def save(self):
        if self.auto_saved_path:
            self.app.toast("이미 저장됨", self.auto_saved_path.name)
        else:
            path = self.app.save_image(self.image)
            self.app.record_capture(path)
            self.app.toast("이미지 저장 완료", path.name)
        self.close()

    def extract_text(self):
        try:
            import ocr
            text = ocr.extract_text(self.image)
        except RuntimeError as error:
            self.app.toast("텍스트 추출 실패", str(error)); return
        if not text.strip():
            self.app.toast("텍스트 추출", "이미지에서 글자를 찾지 못했습니다."); return
        self.app.root.clipboard_clear(); self.app.root.clipboard_append(text)
        preview = text.replace("\n", " ")
        self.app.toast("텍스트 복사 완료", preview[:80] + ("…" if len(preview) > 80 else ""))
        self.close()

    def close(self):
        if self.winfo_exists():
            self.destroy()
