"""CleanShot 풍 디자인 시스템.

크림빛 배경 + 흰 카드 + 맥 시스템 블루 액센트를 쓰고,
tkinter가 기본 제공하지 않는 토글 스위치·알약 버튼을 Pillow로 그려 제공한다.
"""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

# ── 팔레트 ─────────────────────────────────────────────────────────
CREAM = "#f4f2ee"        # 앱 전체 배경 (맥 크림 그레이)
CARD = "#ffffff"         # 카드/패널
BORDER = "#e7e3db"       # 헤어라인 경계
TEXT = "#1d1d1f"         # 본문 (맥 잉크 블랙)
MUTED = "#8a8886"        # 보조 텍스트
ACCENT = "#3478f6"       # 맥 시스템 블루
ACCENT_DARK = "#2b66d9"
ACCENT_SOFT = "#eaf1fe"  # 선택/호버 배경
GREEN = "#34c759"        # 토글 켜짐 (맥 그린)
FONT = "맑은 고딕"

_pill_cache: dict[tuple, ImageTk.PhotoImage] = {}


def pill_image(width: int, height: int, color: str, radius: int | None = None) -> ImageTk.PhotoImage:
    """둥근 알약 모양 배경 이미지. 3배로 그린 뒤 줄여 곡선을 부드럽게 만든다."""
    key = (width, height, color, radius)
    if key in _pill_cache:
        return _pill_cache[key]
    scale = 3
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    r = (radius if radius is not None else height // 2) * scale
    ImageDraw.Draw(img).rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=r, fill=color)
    photo = ImageTk.PhotoImage(img.resize((width, height), Image.Resampling.LANCZOS))
    _pill_cache[key] = photo
    return photo


def pill_button(parent, text, command, *, primary=False, width=None, bg=None, fg=None, font_size=10, bold=None, height=34):
    """둥근 모서리 버튼. primary=True면 파란 채움, 아니면 흰 카드 스타일."""
    parent_bg = parent.cget("bg") if isinstance(parent, (tk.Frame, tk.Toplevel, tk.Tk, tk.Canvas)) else CREAM
    fill = bg or (ACCENT if primary else CARD)
    text_color = fg or ("#ffffff" if primary else TEXT)
    weight = "bold" if (bold if bold is not None else primary) else "normal"
    w = width or (len(text) * (font_size + 3) + 34)
    photo = pill_image(w, height, fill)
    button = tk.Button(parent, image=photo, text=text, compound="center", command=command,
                       fg=text_color, activeforeground=text_color, font=(FONT, font_size, weight),
                       relief="flat", bd=0, bg=parent_bg, activebackground=parent_bg,
                       highlightthickness=0, cursor="hand2")
    button._pill_photo = photo  # 가비지 컬렉션 방지
    return button


class Switch(tk.Canvas):
    """맥 스타일 토글 스위치. BooleanVar와 양방향으로 묶인다."""
    W, H = 44, 25

    def __init__(self, parent, variable: tk.BooleanVar, command=None, bg=CARD):
        super().__init__(parent, width=self.W, height=self.H, bg=bg, highlightthickness=0, cursor="hand2")
        self.variable, self.command = variable, command
        self.bind("<Button-1>", self.toggle)
        self._trace = variable.trace_add("write", lambda *_: self.draw())
        self.bind("<Destroy>", self._untrace)
        self.draw()

    def _untrace(self, _event=None):
        try: self.variable.trace_remove("write", self._trace)
        except (tk.TclError, ValueError): pass

    def toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        if self.command: self.command()

    def draw(self):
        try: on = self.variable.get()
        except tk.TclError: return
        self.delete("all")
        track = GREEN if on else "#d6d3cd"
        # 양 끝 원 + 가운데 사각형으로 알약 트랙을 만든다.
        self.create_oval(1, 1, self.H - 1, self.H - 1, fill=track, outline=track)
        self.create_oval(self.W - self.H + 1, 1, self.W - 1, self.H - 1, fill=track, outline=track)
        self.create_rectangle(self.H // 2, 1, self.W - self.H // 2, self.H - 1, fill=track, outline=track)
        x = self.W - self.H + 3 if on else 3
        self.create_oval(x, 3, x + self.H - 6, self.H - 3, fill="#ffffff", outline="#d8d5cf")


class Tooltip:
    """아이콘 버튼에 마우스를 올리면 잠시 뒤 아래에 뜨는 검은 말풍선."""

    def __init__(self, widget, text, delay=420):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip, self.job = None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self.job = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tip or not self.widget.winfo_exists():
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.overrideredirect(True); self.tip.attributes("-topmost", True)
        tk.Label(self.tip, text=self.text, bg="#2c2c2e", fg="#ffffff", font=(FONT, 8), padx=9, pady=4).pack()
        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2 - self.tip.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip.geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        if self.job:
            self.widget.after_cancel(self.job); self.job = None
        if self.tip:
            self.tip.destroy(); self.tip = None


def card(parent, bg=CARD, padx=0, pady=0):
    """헤어라인 경계의 흰 카드 프레임."""
    frame = tk.Frame(parent, bg=bg, highlightbackground=BORDER, highlightthickness=1, padx=padx, pady=pady)
    return frame


def section_label(parent, text, bg=CREAM):
    """카드 위에 붙는 작은 대문자풍 섹션 제목."""
    return tk.Label(parent, text=text, bg=bg, fg=MUTED, font=(FONT, 9, "bold"), anchor="w")
