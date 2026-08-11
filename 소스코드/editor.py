from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from config import APP_NAME
from ui import FONT, Tooltip, pill_button

if TYPE_CHECKING:
    from app import CaptureApp


class CaptureEditor(tk.Toplevel):
    """캡처 후 HWP 문서에 넣기 전 필요한 최소 편집만 제공하는 창."""
    MAX_WIDTH, MAX_HEIGHT = 870, 610

    def __init__(self, app: "CaptureApp", image: Image.Image, auto_saved_path: Path | None = None):
        super().__init__(app.root)
        self.app, self.image = app, image.convert("RGB")
        self.original = self.image.copy()
        self.auto_saved_path = auto_saved_path
        self.dirty = False
        self.mode, self.start, self.number = "select", None, 1
        self.pending_text, self.photo, self.scale, self.color = None, None, 1.0, "#e53935"
        self.text_size_var = tk.IntVar(value=24)
        self.number_size_var = tk.IntVar(value=34)
        self.line_width_var = tk.IntVar(value=5)
        self.format_var = tk.StringVar(value=app.settings["image_format"])
        self.font_paths = self.available_fonts()
        self.font_var = tk.StringVar(value="맑은 고딕" if "맑은 고딕" in self.font_paths else next(iter(self.font_paths)))
        self.text_items, self.selected_text_index, self.text_marker = [], None, None
        self.number_items, self.selected_number_index = [], None
        self.number_style = "filled"  # 번호 마커 스타일: filled(채운 원) / outline(빈 원) / square(사각형)
        self.stamp_char = "✓"          # 스탬프 도구로 찍을 기호
        self.quality_override = None   # '용량 맞추기'가 정한 저장 품질(없으면 환경설정 품질 사용)
        self.active_overlay = None     # 형광펜을 그리는 동안 사용하는 반투명 레이어
        self.opacity_var = tk.IntVar(value=40)  # 형광펜 농도(%) — 낮을수록 뒤 글자가 잘 비친다
        self.straight_var = tk.BooleanVar(value=False)  # 직선(자) 모드: 펜·형광펜을 반듯한 직선으로 긋는다
        self.zoom, self.drag_text_index, self.drag_initial = 1.0, None, None
        self.drag_number_index, self.number_resize, self.number_drag_initial = None, False, None
        self.preview_ids = []
        self.icon_photos, self._icon_art = {}, {}
        self.rail_buttons = {}
        self.pen_last = None
        self.image_offset_x, self.image_offset_y = 0, 0
        self.title(f"{APP_NAME} 결과창")
        # 작업표시줄에 하단 메뉴가 가리지 않도록 화면 가운데(약간 위)에 띄운다.
        width, height = 1320, 820
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height - 80) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}"); self.minsize(1000, 640)
        self.configure(bg="#f4f2ee"); self.protocol("WM_DELETE_WINDOW", self.maybe_save_and_close)
        # 메인 창은 단축키 대기 중 숨겨져 있을 수 있다. transient로 종속시키면 결과창까지 함께
        # 뒤로 숨을 수 있으므로 독립 비모달 창으로 띄우고 전면으로 가져온다.
        self.build_ui(); self.refresh(); self.after(120, self.refresh)
        self.deiconify(); self.lift(); self.attributes("-topmost", True); self.focus_force()
        self.after(350, lambda: self.attributes("-topmost", False))

    def build_ui(self):
        # ── 상단 바: 왼쪽은 파일·되돌리기, 오른쪽은 내보내기 (CleanShot식 슬림 바) ──
        top = tk.Frame(self, bg="#ffffff", highlightbackground="#e7e3db", highlightthickness=1); top.pack(fill="x")
        bar = tk.Frame(top, bg="#ffffff"); bar.pack(fill="x", padx=12, pady=7)
        pill_button(bar, "＋  새 캡처", self.new_capture, primary=True, font_size=10, height=38, width=126).pack(side="left")
        self.top_icon(bar, "image", "열기", "이미지 열기", self.load_image).pack(side="left", padx=(18, 0))
        self.top_icon(bar, "folder", "폴더", "저장 폴더 열기", self.app.open_save_folder).pack(side="left", padx=(6, 0))
        self.top_icon(bar, "home", "홈", "홈으로 (환경설정)", self.go_home).pack(side="left", padx=(6, 0))
        self.vsep(bar)
        self.top_icon(bar, "undo", "이전", "이전 (Ctrl+Z)", self.undo).pack(side="left")
        self.top_icon(bar, "redo", "다시", "다시 (Ctrl+Y)", self.redo).pack(side="left", padx=(6, 0))
        self.rotate_button(bar).pack(side="left", padx=(6, 0))
        self.top_icon(bar, "reset", "초기화", "원본으로 초기화", self.reset).pack(side="left", padx=(6, 0))
        self.top_icon(bar, "delete", "삭제", "선택한 항목 삭제 (Delete)", self.delete_selected).pack(side="left", padx=(6, 0))
        self.top_icon(bar, "pin", "고정", "현재 이미지를 화면에 항상 위로 붙여두기", self.pin_current).pack(side="left", padx=(6, 0))
        pill_button(bar, "완료", self.finish, primary=True, font_size=10, height=38, width=92).pack(side="right")
        pill_button(bar, "저장", self.save_only, font_size=10, height=38, width=84).pack(side="right", padx=8)
        pill_button(bar, "복사", self.copy_for_hwp, font_size=10, height=38, width=84).pack(side="right")
        self.beautify_button(bar).pack(side="right", padx=(0, 16))
        ocr_button = tk.Button(bar, image=self.editor_icon("ocr", 24), text=" 텍스트 추출", compound="left",
                               command=self.extract_text_to_clipboard, relief="flat", bg="#ffffff",
                               activebackground="#eaf1fe", fg="#3f3f46", font=(FONT, 10), bd=0, padx=10, cursor="hand2")
        ocr_button.pack(side="right", padx=(0, 6)); Tooltip(ocr_button, "이미지 속 글자를 클립보드로 복사 (Windows OCR)")
        redact_button = tk.Button(bar, image=self.editor_icon("shield", 24), text=" 가리기", compound="left",
                                  command=self.redact_sensitive, relief="flat", bg="#ffffff",
                                  activebackground="#eaf1fe", fg="#3f3f46", font=(FONT, 10), bd=0, padx=10, cursor="hand2")
        redact_button.pack(side="right", padx=(0, 6)); Tooltip(redact_button, "전화번호·이메일·주민번호를 찾아 자동 모자이크")

        # ── 스타일 줄: 색·크기·글꼴 등 그리기 옵션 ──
        strip = tk.Frame(self, bg="#ffffff", highlightbackground="#e7e3db", highlightthickness=1); strip.pack(fill="x")
        style_row = tk.Frame(strip, bg="#ffffff"); style_row.pack(fill="x", padx=14, pady=5)
        tk.Label(style_row, text="색상", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(0, 3))
        for color in ("#111827", "#8a8886", "#e53935", "#eab308", "#22c55e", "#2563eb", "#7c3aed"):
            tk.Button(style_row, text="●", command=lambda value=color: self.set_color(value), bg="#ffffff", fg=color, relief="flat", font=("맑은 고딕", 19), padx=1).pack(side="left")
        tk.Label(style_row, text="글자", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(10, 2))
        size_box = ttk.Combobox(style_row, textvariable=self.text_size_var, values=(14, 18, 22, 24, 28, 32, 40, 48), state="readonly", width=4)
        size_box.pack(side="left"); size_box.bind("<<ComboboxSelected>>", self.change_selected_text_size)
        tk.Label(style_row, text="번호", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(8, 2))
        number_box = ttk.Combobox(style_row, textvariable=self.number_size_var, values=(20, 24, 28, 34, 40, 48, 56, 64), state="readonly", width=4)
        number_box.pack(side="left"); number_box.bind("<<ComboboxSelected>>", self.change_selected_number_size)
        tk.Label(style_row, text="선굵기", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(8, 2))
        ttk.Combobox(style_row, textvariable=self.line_width_var, values=(1, 2, 3, 5, 7, 10, 14, 20), state="readonly", width=3).pack(side="left")
        tk.Label(style_row, text="농도%", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(8, 2))
        ttk.Combobox(style_row, textvariable=self.opacity_var, values=(20, 30, 40, 55, 70), state="readonly", width=3).pack(side="left")
        tk.Checkbutton(style_row, text="📏 직선(자)", variable=self.straight_var, bg="#ffffff", fg="#1d1d1f",
                       activebackground="#ffffff", selectcolor="#ffffff", font=("맑은 고딕", 10)).pack(side="left", padx=(10, 2))
        tk.Label(style_row, text="글꼴", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(8, 2))
        font_box = ttk.Combobox(style_row, textvariable=self.font_var, values=tuple(self.font_paths), state="readonly", width=13)
        font_box.pack(side="left"); font_box.bind("<<ComboboxSelected>>", self.change_selected_text_font)

        # 하단 메뉴를 먼저 바닥에 고정한다. 이렇게 해야 창이 작아져도 항상 보인다.
        footer = tk.Frame(self, bg="#ffffff", height=54, highlightbackground="#e7e3db", highlightthickness=1); footer.pack(side="bottom", fill="x"); footer.pack_propagate(False)
        tk.Label(footer, text="저장 형식", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(10, 3))
        ttk.Combobox(footer, textvariable=self.format_var, values=("JPG", "PNG", "BMP", "GIF", "WEBP"), state="readonly", width=7).pack(side="left", pady=10)
        self.size_var = tk.StringVar(value="원본 크기")
        ttk.Combobox(footer, textvariable=self.size_var, state="readonly", values=("원본 크기", "HWP 문서 폭 (1600px)", "HWP 반쪽 폭 (800px)", "작은 설명 (550px)"), width=22).pack(side="left", padx=(10, 5), pady=10)
        pill_button(footer, "크기 적용", self.apply_size, font_size=9, height=30, bg="#efede7").pack(side="left")
        self.margin_var = tk.StringVar(value="여백 없음")
        ttk.Combobox(footer, textvariable=self.margin_var, state="readonly", values=("여백 없음", "흰 여백 8px", "흰 여백 16px"), width=14).pack(side="left", padx=(12, 5))
        pill_button(footer, "문서 스타일", self.apply_document_style, font_size=9, height=30, bg="#efede7").pack(side="left")
        tk.Label(footer, text="용량", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10)).pack(side="left", padx=(12, 3))
        self.target_size_var = tk.StringVar(value="500KB")
        ttk.Combobox(footer, textvariable=self.target_size_var, state="readonly", values=("300KB", "500KB", "1MB", "2MB", "직접 입력…"), width=9).pack(side="left")
        pill_button(footer, "용량 맞추기", self.fit_to_target_size, font_size=9, height=30, bg="#efede7").pack(side="left", padx=(5, 0))
        self.zoom_label = tk.Label(footer, text="100%", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 10))
        self.zoom_label.pack(side="right", padx=12)

        # ── 본문: 왼쪽 세로 도구 레일 + 캔버스 + 최근 캡처 ──
        content = tk.Frame(self, bg="#eceae4"); content.pack(side="top", fill="both", expand=True)
        rail = tk.Frame(content, bg="#ffffff", highlightbackground="#e7e3db", highlightthickness=1)
        rail.pack(side="left", fill="y")
        self.rail_button(rail, "select", "선택", "선택 · 이동", lambda: self.select_tool("select"))
        self.rail_button(rail, "text", "텍스트", "텍스트 넣기", lambda: self.select_tool("text"))
        self.rail_button(rail, "number", "번호", "번호 찍기", menu_items=[
            ("① 채운 원", lambda: self.select_number_style("filled")),
            ("⓵ 빈 원(테두리)", lambda: self.select_number_style("outline")),
            ("▣ 사각형", lambda: self.select_number_style("square")),
            ("1  숫자만", lambda: self.select_number_style("plain")),
            ("1)  괄호", lambda: self.select_number_style("paren"))])
        self.rail_button(rail, "stamp", "스탬프", "스탬프 찍기", menu_items=[
            ("✓ 체크", lambda: self.select_stamp("✓", "#16a34a")),
            ("✗ 엑스", lambda: self.select_stamp("✗", "#e53935")),
            ("★ 별", lambda: self.select_stamp("★", "#eab308")),
            ("♥ 하트", lambda: self.select_stamp("♥", "#e53935")),
            ("? 물음표", lambda: self.select_stamp("?", "#2563eb")),
            ("! 느낌표", lambda: self.select_stamp("!", "#e53935"))])
        self.rail_button(rail, "pen", "펜", "펜으로 그리기", lambda: self.select_tool("pen"))
        self.rail_button(rail, "highlight", "형광펜", "형광펜 (반투명)", lambda: self.select_tool("highlight"))
        self.rail_button(rail, "shape", "도형", "도형 그리기", menu_items=[
            ("사각형", lambda: self.select_tool("rect")),
            ("원형", lambda: self.select_tool("ellipse")),
            ("선", lambda: self.select_tool("line")),
            ("화살표", lambda: self.select_tool("arrow")),
            ("점선 사각형", lambda: self.select_tool("dashed_rect"))])
        self.rail_button(rail, "callout", "콜아웃", "말풍선 · 돋보기 확대", menu_items=[
            ("💬 말풍선 (설명 상자)", lambda: self.select_tool("callout")),
            ("🔍 돋보기 확대", lambda: self.select_tool("magnify"))])
        self.rail_button(rail, "mosaic", "모자이크", "모자이크 · 흐림", menu_items=[
            ("▦ 픽셀 모자이크", lambda: self.select_tool("mosaic")),
            ("〜 부드러운 흐림", lambda: self.select_tool("blur"))])
        self.rail_button(rail, "crop", "자르기", "이미지 자르기 (모양 선택)", menu_items=[
            ("▭ 사각형 자르기", lambda: self.select_tool("crop")),
            ("▢ 둥근 사각형 자르기", lambda: self.select_tool("crop_round")),
            ("⬭ 타원 자르기", lambda: self.select_tool("crop_ellipse")),
            ("○ 원형 자르기", lambda: self.select_tool("crop_circle"))])
        self.update_rail_selection()

        work_area = tk.Frame(content, bg="#eceae4"); work_area.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(work_area, bg="#e3e0d9", highlightthickness=0, cursor="crosshair")
        # fill 없이 expand만 주면 캔버스가 이미지 크기를 유지한 채 작업 영역 가운데에 놓인다.
        # (캔버스 크기 = 이미지 크기이므로 클릭 좌표 계산은 그대로 유지된다.)
        self.canvas.pack(expand=True, padx=15, pady=15)
        self.canvas.bind("<ButtonPress-1>", self.mouse_down); self.canvas.bind("<ButtonRelease-1>", self.mouse_up)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<Motion>", self.update_cursor)
        self.canvas.bind("<Leave>", lambda _event: self.canvas.config(cursor="crosshair"))
        self.canvas.bind("<Double-Button-1>", self.edit_text_at_point)
        self.canvas.bind("<Control-MouseWheel>", self.zoom_with_wheel)
        self.bind("<Delete>", self.delete_selected); self.bind("<BackSpace>", self.delete_selected)
        self.bind("<Control-z>", lambda _e: self.undo()); self.bind("<Control-Z>", lambda _e: self.undo())
        self.bind("<Control-y>", lambda _e: self.redo()); self.bind("<Control-Y>", lambda _e: self.redo())
        self.bind("<Control-s>", lambda _e: self.save_only()); self.bind("<Control-S>", lambda _e: self.save_only())
        self.bind("<Control-c>", lambda _e: self.copy_for_hwp()); self.bind("<Control-C>", lambda _e: self.copy_for_hwp())
        self.bind("<Escape>", self.cancel_tool)
        self.build_recent_sidebar(content)
        self.history, self.redo_history = [], []

    # ── 아이콘: 104px 원본을 Pillow로 그린 뒤 축소해 곡선을 부드럽게 만든다 ──
    ICON_INK, ICON_ACCENT = "#3f3f46", "#3478f6"
    RAIL_MODE_KEYS = {"select": "select", "text": "text", "crop": "crop", "crop_round": "crop",
                      "crop_ellipse": "crop", "crop_circle": "crop", "mosaic": "mosaic", "blur": "mosaic",
                      "pen": "pen", "highlight": "highlight", "rect": "shape", "ellipse": "shape",
                      "line": "shape", "arrow": "shape", "dashed_rect": "shape", "ruler": "shape",
                      "callout": "callout", "magnify": "callout"}

    def icon_art(self, key):
        """104x104 아이콘 원본. icons/{key}.png 파일이 있으면 직접 그린 이미지를 우선 사용한다."""
        if key in self._icon_art:
            return self._icon_art[key]
        custom = Path(__file__).with_name("icons") / f"{key}.png"
        if custom.exists():
            art = Image.open(custom).convert("RGBA").resize((104, 104), Image.Resampling.LANCZOS)
            self._icon_art[key] = art
            return art
        s, ink, accent = 104, self.ICON_INK, self.ICON_ACCENT
        art = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(art); w = 8
        bold = lambda size: ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", size)
        if key == "select":       # 마우스 커서
            d.polygon(((32, 10), (32, 80), (48, 64), (58, 90), (70, 84), (60, 60), (80, 60)), fill=ink)
        elif key == "text":        # Aa
            d.text((8, 12), "A", font=bold(64), fill=ink)
            d.text((54, 30), "a", font=bold(50), fill=accent)
        elif key == "crop":        # 자르기 프레임
            d.line((30, 6, 30, 74), fill=ink, width=w); d.line((26, 74, 98, 74), fill=ink, width=w)
            d.line((6, 30, 74, 30), fill=accent, width=w); d.line((74, 26, 74, 98), fill=accent, width=w)
        elif key == "number":      # ① 번호
            d.ellipse((12, 12, 92, 92), outline=accent, width=w)
            box = d.textbbox((0, 0), "1", font=bold(48))
            d.text((52 - (box[2] - box[0]) / 2 - box[0], 52 - (box[3] - box[1]) / 2 - box[1]), "1", font=bold(48), fill=ink)
        elif key == "stamp":       # 도장(체크)
            d.rounded_rectangle((10, 10, 94, 94), radius=22, outline=ink, width=w)
            d.line((32, 54, 46, 70), fill=accent, width=11); d.line((44, 70, 74, 36), fill=accent, width=11)
        elif key == "pen":         # 펜
            d.line((32, 72, 78, 26), fill=ink, width=17)
            d.polygon(((14, 90), (36, 84), (22, 68)), fill=accent)
        elif key == "highlight":   # 형광펜
            d.polygon(((30, 62), (60, 30), (78, 48), (48, 80)), fill="#fbbf24", outline=ink)
            d.polygon(((18, 88), (30, 62), (48, 80)), fill=ink)
            d.rectangle((14, 94, 90, 103), fill="#fde047")
        elif key == "shape":       # 사각형+원
            d.rectangle((10, 10, 62, 62), outline=ink, width=w)
            d.ellipse((40, 40, 94, 94), outline=accent, width=w)
        elif key == "mosaic":      # 픽셀 격자
            for i in range(9):
                x, y = 12 + (i % 3) * 28, 12 + (i // 3) * 28
                d.rectangle((x, y, x + 24, y + 24), fill=accent if i % 2 == 0 else "#c9c9ce")
        elif key == "delete":      # 휴지통
            red = "#e5484d"
            d.rectangle((26, 32, 78, 92), outline=red, width=w)
            d.line((14, 32, 90, 32), fill=red, width=w)
            d.rectangle((38, 14, 66, 32), outline=red, width=6)
            d.line((44, 46, 44, 78), fill=red, width=6); d.line((60, 46, 60, 78), fill=red, width=6)
        elif key == "home":        # 집
            d.line((10, 52, 52, 14), fill=ink, width=w); d.line((52, 14, 94, 52), fill=ink, width=w)
            d.line((22, 44, 22, 92), fill=ink, width=w); d.line((82, 44, 82, 92), fill=ink, width=w)
            d.line((18, 92, 86, 92), fill=ink, width=w)
            d.rectangle((44, 62, 60, 92), outline=accent, width=6)
        elif key == "image":       # 사진
            d.rounded_rectangle((8, 16, 96, 88), radius=10, outline=ink, width=w)
            d.ellipse((24, 30, 40, 46), fill=accent)
            for a, b in (((18, 76), (44, 50)), ((44, 50), (60, 68)), ((56, 64), (72, 46)), ((72, 46), (88, 64))):
                d.line((a, b), fill=ink, width=w)
        elif key == "folder":      # 폴더
            d.rectangle((14, 14, 46, 30), outline=ink, width=6)
            d.rounded_rectangle((8, 24, 96, 86), radius=8, outline=ink, width=w)
        elif key == "undo":        # 왼쪽으로 도는 화살표
            d.line((30, 34, 64, 34), fill=ink, width=w)
            d.arc((40, 34, 90, 84), start=-90, end=90, fill=ink, width=w)
            d.line((44, 84, 66, 84), fill=ink, width=w)
            d.polygon(((8, 34), (36, 18), (36, 50)), fill=accent)
        elif key == "redo":        # undo 좌우 반전
            art = self.icon_art("undo").transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            self._icon_art[key] = art
            return art
        elif key == "rotate":      # 회전
            d.arc((18, 18, 86, 86), start=-30, end=210, fill=accent, width=w)
            d.polygon(((6, 44), (34, 34), (28, 62)), fill=accent)
        elif key == "reset":       # 처음으로 되감기
            d.arc((18, 18, 86, 86), start=40, end=320, fill=ink, width=w)
            d.polygon(((92, 60), (98, 32), (72, 42)), fill=accent)
            d.ellipse((46, 46, 58, 58), fill=ink)
        elif key == "ocr":         # 스캔 괄호 + T
            for cx, cy, dx, dy in ((8, 8, 1, 1), (96, 8, -1, 1), (8, 96, 1, -1), (96, 96, -1, -1)):
                d.line((cx, cy, cx + 24 * dx, cy), fill=ink, width=w)
                d.line((cx, cy, cx, cy + 24 * dy), fill=ink, width=w)
            box = d.textbbox((0, 0), "T", font=bold(52))
            d.text((52 - (box[2] - box[0]) / 2 - box[0], 52 - (box[3] - box[1]) / 2 - box[1]), "T", font=bold(52), fill=accent)
        elif key == "pin":         # 압정
            d.polygon(((36, 8), (68, 8), (62, 40), (78, 52), (26, 52), (42, 40)), outline=ink, width=6)
            d.line((52, 52, 52, 92), fill=accent, width=8)
        elif key == "callout":     # 말풍선 + 돋보기
            d.rounded_rectangle((8, 12, 80, 62), radius=14, outline=ink, width=w)
            d.polygon(((24, 60), (24, 82), (44, 61)), fill=ink)
            d.ellipse((58, 52, 92, 86), outline=accent, width=w)
            d.line((86, 80, 100, 94), fill=accent, width=w)
        elif key == "shield":      # 개인정보 보호 방패
            d.polygon(((52, 6), (92, 20), (90, 58), (52, 96), (14, 58), (12, 20)), outline=ink, width=6)
            d.line((32, 42, 72, 42), fill=accent, width=8)
            d.line((32, 58, 72, 58), fill=accent, width=8)
        elif key == "sparkle":     # 꾸미기 반짝임
            d.polygon(((50, 8), (60, 40), (92, 50), (60, 60), (50, 92), (40, 60), (8, 50), (40, 40)), fill=accent)
            d.polygon(((82, 12), (86, 24), (98, 28), (86, 32), (82, 44), (78, 32), (66, 28), (78, 24)), fill="#fbbf24")
        self._icon_art[key] = art
        return art

    def editor_icon(self, key, size=22):
        """상단 바용 아이콘 PhotoImage."""
        cache_key = (key, size)
        if cache_key in self.icon_photos:
            return self.icon_photos[cache_key]
        photo = ImageTk.PhotoImage(self.icon_art(key).resize((size, size), Image.Resampling.LANCZOS))
        self.icon_photos[cache_key] = photo
        return photo

    def rail_icon_image(self, key, selected, menu=False):
        """도구 레일용 44px 버튼 이미지. 선택되면 파란 알약 배경, 메뉴 버튼이면 ▾ 표시."""
        cache_key = (key, "rail", selected, menu)
        if cache_key in self.icon_photos:
            return self.icon_photos[cache_key]
        size, scale = 36, 3
        base = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
        if selected:
            ImageDraw.Draw(base).rounded_rectangle((3, 3, size * scale - 4, size * scale - 4), radius=10 * scale, fill="#dcebfd")
        inner = 24 * scale
        base.alpha_composite(self.icon_art(key).resize((inner, inner), Image.Resampling.LANCZOS), ((size * scale - inner) // 2, (size * scale - inner) // 2))
        if menu:
            d = ImageDraw.Draw(base); mx, my = size * scale - 24, size * scale - 21
            d.polygon(((mx, my), (mx + 15, my), (mx + 7, my + 11)), fill="#8a8886")
        photo = ImageTk.PhotoImage(base.resize((size, size), Image.Resampling.LANCZOS))
        self.icon_photos[cache_key] = photo
        return photo

    def top_icon(self, parent, key, label, tip, command):
        button = tk.Button(parent, image=self.editor_icon(key, 24), text=label, compound="top",
                           command=command, relief="flat", bg="#ffffff", activebackground="#eaf1fe",
                           fg="#6b6b6e", activeforeground="#3478f6", font=("맑은 고딕", 8),
                           bd=0, padx=9, pady=3, cursor="hand2")
        Tooltip(button, tip)
        return button

    @staticmethod
    def vsep(parent):
        tk.Frame(parent, bg="#e7e3db", width=1, height=36).pack(side="left", padx=14)

    def rotate_button(self, parent):
        button = tk.Menubutton(parent, image=self.editor_icon("rotate", 24), text="회전", compound="top",
                               relief="flat", bg="#ffffff", activebackground="#eaf1fe",
                               fg="#6b6b6e", activeforeground="#3478f6", font=("맑은 고딕", 8),
                               bd=0, padx=9, pady=3, cursor="hand2")
        menu = tk.Menu(button, tearoff=False, font=("맑은 고딕", 10))
        menu.add_command(label="↺ 왼쪽으로 90°", command=self.rotate_left)
        menu.add_command(label="↻ 오른쪽으로 90°", command=self.rotate_right)
        menu.add_command(label="180° 뒤집기", command=self.rotate_180)
        button.configure(menu=menu)
        Tooltip(button, "회전")
        return button

    def rail_button(self, parent, key, label, tip, command=None, menu_items=None):
        normal = self.rail_icon_image(key, False, menu=bool(menu_items))
        active = self.rail_icon_image(key, True, menu=bool(menu_items))
        options = dict(image=normal, text=label, compound="top", relief="flat", bg="#ffffff",
                       activebackground="#ffffff", fg="#6b6b6e", activeforeground="#3478f6",
                       font=("맑은 고딕", 8), bd=0, cursor="hand2")
        if menu_items:
            widget = tk.Menubutton(parent, **options)
            menu = tk.Menu(widget, tearoff=False, font=("맑은 고딕", 10))
            for item_label, item_command in menu_items:
                menu.add_command(label=item_label, command=item_command)
            widget.configure(menu=menu)
        else:
            widget = tk.Button(parent, command=command, **options)
        Tooltip(widget, tip)
        widget.pack(pady=0, padx=6, fill="x")
        self.rail_buttons[key] = (widget, normal, active)
        return widget

    def update_rail_selection(self):
        """현재 도구에 해당하는 레일 버튼만 파란 배경 + 파란 이름으로 강조한다."""
        key = self.RAIL_MODE_KEYS.get(self.mode)
        if self.mode == "number":
            key = "stamp" if self.number_style == "stamp" else "number"
        for name, (widget, normal, active) in self.rail_buttons.items():
            selected = name == key
            widget.configure(image=active if selected else normal,
                             fg="#3478f6" if selected else "#6b6b6e",
                             font=("맑은 고딕", 8, "bold" if selected else "normal"))

    @staticmethod
    def available_fonts():
        """문서 작업에 자주 쓰는 한글 글꼴만 간결하게 제공한다."""
        directory = Path(r"C:\Windows\Fonts")
        fonts = {}
        # 설치돼 있는 글꼴만 목록에 보인다(없는 파일은 자동으로 건너뜀).
        common_fonts = {
            # 한글 글꼴
            "맑은 고딕": "malgun.ttf", "맑은 고딕 Bold": "malgunbd.ttf", "맑은 고딕 Light": "malgunsl.ttf",
            "굴림": "gulim.ttc", "굴림체": "gulim.ttc", "돋움": "dotum.ttc", "돋움체": "dotum.ttc",
            "바탕": "batang.ttc", "바탕체": "batang.ttc", "궁서": "gungsuh.ttc", "궁서체": "GUNGSO.TTF",
            "나눔고딕": "NanumGothic.ttf", "나눔고딕 Bold": "NanumGothicBold.ttf",
            "나눔명조": "NanumMyeongjo.ttf", "나눔손글씨 펜": "NanumPen.ttf", "나눔바른고딕": "NanumBarunGothic.ttf",
            "본고딕": "NotoSansCJKkr-Regular.otf", "본명조": "NotoSerifCJKkr-Regular.otf",
            "함초롬바탕": "HMFMPYUN.ttf",
            # 영문 글꼴
            "Arial": "arial.ttf", "Arial Bold": "arialbd.ttf", "Times New Roman": "times.ttf",
            "Calibri": "calibri.ttf", "Cambria": "cambria.ttc", "Georgia": "georgia.ttf",
            "Verdana": "verdana.ttf", "Tahoma": "tahoma.ttf", "Segoe UI": "segoeui.ttf",
            "Consolas": "consola.ttf", "Comic Sans MS": "comic.ttf", "Impact": "impact.ttf",
        }
        for name, filename in common_fonts.items():
            path = directory / filename
            if path.exists() and name not in fonts: fonts[name] = str(path)
        return fonts or {"기본 글꼴": ""}

    BEAUTIFY_PRESETS = {
        "퍼플 블루": ("#7c3aed", "#2563eb"), "민트": ("#10b981", "#06b6d4"),
        "선셋": ("#f97316", "#ec4899"), "그레이": ("#e5e7eb", "#94a3b8"), "화이트": ("#ffffff", "#f1f5f9"),
    }

    def beautify_button(self, parent):
        """캡처에 둥근 모서리 + 그림자 + 그라데이션 배경을 입힌다(발표자료용)."""
        button = tk.Menubutton(parent, image=self.editor_icon("sparkle", 24), text=" 꾸미기 ▾", compound="left",
                               relief="flat", bg="#ffffff", activebackground="#eaf1fe", fg="#3f3f46",
                               font=(FONT, 10), bd=0, padx=10, cursor="hand2")
        menu = tk.Menu(button, tearoff=False, font=("맑은 고딕", 10))
        for name in self.BEAUTIFY_PRESETS:
            menu.add_command(label=name, command=lambda value=name: self.apply_beautify(value))
        button.configure(menu=menu)
        Tooltip(button, "둥근 모서리 + 그림자 + 배경 입히기")
        return button

    def apply_beautify(self, preset):
        self.snapshot(); self.flatten_text_items()
        self.image = self.beautified(self.image, *self.BEAUTIFY_PRESETS[preset])
        self.refresh()

    @classmethod
    def beautified(cls, image, color_a, color_b):
        pad = max(40, image.width // 10)
        radius = max(10, image.width // 60)
        # 둥근 모서리: 3배 마스크를 줄여 곡선을 부드럽게 만든다.
        scale = 3
        mask = Image.new("L", (image.width * scale, image.height * scale), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width * scale - 1, image.height * scale - 1), radius=radius * scale, fill=255)
        rounded = image.convert("RGBA"); rounded.putalpha(mask.resize(image.size, Image.Resampling.LANCZOS))
        # 대각선 그라데이션 배경 (작게 그린 뒤 확대)
        width, height = image.width + pad * 2, image.height + pad * 2
        start, end = cls.rgba(color_a, 255)[:3], cls.rgba(color_b, 255)[:3]
        gradient = Image.new("RGB", (64, 64))
        for gy in range(64):
            for gx in range(64):
                t = (gx + gy) / 126
                gradient.putpixel((gx, gy), tuple(round(a + (b - a) * t) for a, b in zip(start, end)))
        background = gradient.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
        # 부드러운 그림자
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        offset = max(6, pad // 6)
        ImageDraw.Draw(shadow).rounded_rectangle((pad, pad + offset, pad + image.width, pad + offset + image.height), radius=radius, fill=(0, 0, 0, 115))
        background = Image.alpha_composite(background, shadow.filter(ImageFilter.GaussianBlur(max(8, pad // 4))))
        background.alpha_composite(rounded, (pad, pad))
        return background.convert("RGB")

    def extract_text_to_clipboard(self):
        """Windows 내장 OCR로 이미지 속 글자를 추출해 클립보드에 넣는다."""
        try:
            import ocr
            text = ocr.extract_text(self.rendered_image())
        except RuntimeError as error:
            messagebox.showwarning(APP_NAME, str(error), parent=self); return
        if not text.strip():
            self.app.toast("텍스트 추출", "이미지에서 글자를 찾지 못했습니다."); return
        self.clipboard_clear(); self.clipboard_append(text)
        preview = text.replace("\n", " ")
        self.app.toast("텍스트 복사 완료", preview[:80] + ("…" if len(preview) > 80 else ""))

    def select_stamp(self, char, color):
        self.stamp_char, self.color, self.number_style = char, color, "stamp"
        self.select_tool("number")

    def select_number_style(self, style):
        self.number_style = style
        self.select_tool("number")

    @staticmethod
    def rgba(hex_color, alpha):
        h = hex_color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)

    @staticmethod
    def snap_to_angle(start, end):
        """직선 자: 끝점을 가장 가까운 45° 방향(수평·수직·대각선)으로 맞춰 반듯하게 만든다."""
        import math
        dx, dy = end[0] - start[0], end[1] - start[1]
        dist = math.hypot(dx, dy)
        if dist < 1:
            return end
        step = math.pi / 4
        angle = round(math.atan2(dy, dx) / step) * step
        return (round(start[0] + dist * math.cos(angle)), round(start[1] + dist * math.sin(angle)))

    def build_recent_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg="#ffffff", width=210, highlightbackground="#e7e3db", highlightthickness=1); sidebar.pack(side="right", fill="y"); sidebar.pack_propagate(False)
        tk.Label(sidebar, text="최근 캡처 목록", bg="#ffffff", fg="#1d1d1f", font=("맑은 고딕", 12, "bold")).pack(anchor="w", padx=14, pady=(16, 2))
        tk.Label(sidebar, text=f"{len(self.app.settings['recent_captures'])}개 저장됨 · 클릭하면 편집 캔버스로 불러옵니다", bg="#ffffff", fg="#8a8886", font=("맑은 고딕", 9), wraplength=180, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
        self.recent_photos = []
        entries = list(reversed(self.app.settings["recent_captures"]))
        if not entries:
            tk.Label(sidebar, text="아직 최근 캡처가 없습니다.", bg="#ffffff", fg="#a8a5a0", font=("맑은 고딕", 10), wraplength=170).pack(padx=14, pady=30)
            return
        # 캡처가 많으면 세로 스크롤로 전부 볼 수 있게 캔버스에 올린다.
        area = tk.Frame(sidebar, bg="#ffffff"); area.pack(fill="both", expand=True)
        self.recent_canvas = tk.Canvas(area, bg="#ffffff", highlightthickness=0, width=176)
        bar = ttk.Scrollbar(area, orient="vertical", command=self.recent_canvas.yview)
        self.recent_canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y"); self.recent_canvas.pack(side="left", fill="both", expand=True)
        holder = tk.Frame(self.recent_canvas, bg="#ffffff")
        window = self.recent_canvas.create_window((0, 0), window=holder, anchor="nw")
        self.recent_canvas.bind("<Configure>", lambda e: self.recent_canvas.itemconfigure(window, width=e.width))
        holder.bind("<Configure>", lambda _e: self.recent_canvas.configure(scrollregion=self.recent_canvas.bbox("all")))
        self.recent_canvas.bind("<Enter>", lambda _e: self.recent_canvas.bind_all("<MouseWheel>", self._scroll_recent))
        self.recent_canvas.bind("<Leave>", lambda _e: self.recent_canvas.unbind_all("<MouseWheel>"))
        for entry in entries:
            path = Path(entry.get("path", ""))
            try:
                with Image.open(path) as source: thumb = source.convert("RGB").copy()
                thumb.thumbnail((160, 105)); photo = ImageTk.PhotoImage(thumb); self.recent_photos.append(photo)
                label = tk.Label(holder, image=photo, bg="#f4f2ee", cursor="hand2")
                label.pack(pady=6)
                label.bind("<Button-1>", lambda _event, target=path: self.load_recent_capture(target))
            except (OSError, ValueError):
                pass

    def _scroll_recent(self, event):
        if self.recent_canvas.bbox("all") and self.recent_canvas.bbox("all")[3] > self.recent_canvas.winfo_height():
            self.recent_canvas.yview_scroll(int(-event.delta / 120), "units")

    def snapshot(self):
        self.history.append((self.image.copy(), [item.copy() for item in self.text_items], [item.copy() for item in self.number_items], self.selected_text_index, self.selected_number_index))
        if len(self.history) > 30:
            del self.history[0]  # 전체 이미지 복사본이 쌓이므로 메모리를 위해 오래된 기록을 버린다.
        self.redo_history.clear()
        self.dirty = True
    def undo(self):
        if self.history:
            self.redo_history.append((self.image.copy(), [item.copy() for item in self.text_items], [item.copy() for item in self.number_items], self.selected_text_index, self.selected_number_index))
            self.image, self.text_items, self.number_items, self.selected_text_index, self.selected_number_index = self.history.pop()
            self.refresh()
    def redo(self):
        if self.redo_history:
            self.history.append((self.image.copy(), [item.copy() for item in self.text_items], [item.copy() for item in self.number_items], self.selected_text_index, self.selected_number_index))
            self.image, self.text_items, self.number_items, self.selected_text_index, self.selected_number_index = self.redo_history.pop()
            self.refresh()
    def reset(self):
        self.image = self.original.copy(); self.history.clear(); self.redo_history.clear(); self.number = 1; self.dirty = False
        self.quality_override = None  # 용량 맞추기로 정한 품질도 원본 기준으로 되돌린다.
        self.text_items, self.selected_text_index = [], None; self.number_items, self.selected_number_index = [], None; self.refresh()
    def rotate_left(self): self.snapshot(); self.flatten_text_items(); self.image = self.image.rotate(90, expand=True); self.refresh()
    def rotate_right(self): self.snapshot(); self.flatten_text_items(); self.image = self.image.rotate(-90, expand=True); self.refresh()
    def rotate_180(self): self.snapshot(); self.flatten_text_items(); self.image = self.image.rotate(180, expand=True); self.refresh()
    def set_color(self, color):
        self.color = color
        if self.selected_text_index is not None:
            self.text_items[self.selected_text_index]["color"] = color
            self.dirty = True; self.refresh()
        if self.selected_number_index is not None:
            self.number_items[self.selected_number_index]["color"] = color
            self.dirty = True; self.refresh()
    def new_capture(self):
        self.maybe_save_and_close(after=lambda: self.app.root.after(150, self.app.start_capture))

    def maybe_save_and_close(self, after=None):
        """편집 내용이 있으면 저장 여부를 묻고 닫는다. 예=저장 후 닫기 / 아니요=저장 없이 닫기 / 취소=닫지 않음."""
        if self.dirty:
            answer = messagebox.askyesnocancel(APP_NAME, "편집한 내용을 저장하시겠습니까?", parent=self)
            if answer is None:
                return  # 취소: 창을 닫지 않는다.
            if answer:
                self.save_only()
        self.close()
        if after:
            after()

    def load_recent_capture(self, path: Path):
        """오른쪽 최근 캡처 썸네일을 현재 편집 캔버스로 불러온다."""
        if not path.exists():
            return
        try:
            with Image.open(path) as source:
                self.image = source.convert("RGB").copy()
            self.original = self.image.copy()
            self.text_items, self.number_items = [], []
            self.selected_text_index, self.selected_number_index = None, None
            self.history, self.redo_history = [], []
            self.refresh()
        except (OSError, ValueError) as error:
            messagebox.showwarning(APP_NAME, f"최근 캡처를 불러올 수 없습니다.\n{error}", parent=self)

    def go_home(self):
        self.maybe_save_and_close(after=self._show_home)

    def _show_home(self):
        self.app.root.deiconify(); self.app.root.lift(); self.app.show_page("home")

    def load_image(self):
        path = filedialog.askopenfilename(parent=self, title="편집할 이미지 열기", filetypes=[("이미지 파일", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            with Image.open(path) as source:
                opened = source.convert("RGB").copy()
            self.snapshot(); self.image = opened; self.original = opened.copy()
            self.text_items, self.number_items = [], []
            self.selected_text_index, self.selected_number_index = None, None
            self.refresh()
        except (OSError, ValueError) as error:
            messagebox.showerror(APP_NAME, f"이미지를 열 수 없습니다.\n{error}", parent=self)

    def select_tool(self, mode):
        self.mode = mode
        if mode == "text":
            # 위치를 먼저 선택해야 문구가 어느 곳에 들어갈지 바로 알 수 있다.
            self.pending_text = None
        self.update_rail_selection()

    def rendered_image(self):
        """텍스트 편집 요소까지 합친 최종 이미지. 저장·복사·완료 시에만 사용한다."""
        rendered = self.image.copy(); draw = ImageDraw.Draw(rendered)
        for item in self.text_items:
            font = self.font(item["size"], item.get("font"))
            x, y = item["x"], item["y"]
            text = self.wrap_text(draw, item["text"], font, item["width"])
            draw.multiline_text((x+2, y+2), text, fill="white", stroke_width=2, stroke_fill="white", font=font, spacing=4)
            draw.multiline_text((x, y), text, fill=item["color"], font=font, spacing=4)
        for item in self.number_items:
            radius = item["size"] // 2
            x, y = item["x"], item["y"]
            style = item.get("style", "filled")
            if style == "stamp":
                # 도장 기호. 흰 외곽선을 둘러 어떤 배경에서도 잘 보이게 한다.
                char = item.get("char", "✓")
                font = self.stamp_font(item["size"])
                box = draw.textbbox((0, 0), char, font=font)
                draw.text((x-(box[2]-box[0])/2-box[0], y-(box[3]-box[1])/2-box[1]), char, fill=item["color"],
                          font=font, stroke_width=max(2, item["size"] // 14), stroke_fill="white")
                continue
            if style in ("plain", "paren"):
                # 도형 없이 번호만. 흰 외곽선으로 어떤 배경에서도 잘 보이게 한다.
                text = f'{item["number"]})' if style == "paren" else str(item["number"])
                font = self.font(max(14, item["size"]))
                box = draw.textbbox((0, 0), text, font=font)
                draw.text((x-(box[2]-box[0])/2, y-(box[3]-box[1])/2-2), text, fill=item["color"],
                          font=font, stroke_width=max(2, item["size"] // 12), stroke_fill="white")
                continue
            if style == "outline":
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="white", outline=item["color"], width=max(3, item["size"] // 12))
                text_fill = item["color"]
            elif style == "square":
                draw.rounded_rectangle((x-radius, y-radius, x+radius, y+radius), radius=max(4, item["size"] // 6), fill=item["color"], outline="white", width=2)
                text_fill = "white"
            else:
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=item["color"], outline="white", width=2)
                text_fill = "white"
            font = self.font(max(12, round(item["size"] * .54)))
            text = str(item["number"]); box = draw.textbbox((0, 0), text, font=font)
            draw.text((x-(box[2]-box[0])/2, y-(box[3]-box[1])/2-2), text, fill=text_fill, font=font)
        return rendered

    @staticmethod
    def wrap_text(draw, text, font, max_width):
        """선택한 점선 상자 폭을 넘지 않도록 글자를 줄바꿈한다."""
        lines = []
        for source_line in text.splitlines() or [""]:
            line = ""
            for char in source_line:
                candidate = line + char
                if line and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                    lines.append(line); line = char
                else:
                    line = candidate
            lines.append(line)
        return "\n".join(lines)

    def flatten_text_items(self):
        """크기 변경·문서 스타일처럼 픽셀 자체를 바꾸는 작업 직전에 텍스트를 이미지에 합친다."""
        if self.text_items or self.number_items:
            self.image = self.rendered_image()
            self.text_items, self.selected_text_index = [], None
            self.number_items, self.selected_number_index = [], None

    def refresh(self, fast=False):
        preview = self.rendered_image()
        if self.active_overlay is not None:
            # 형광펜을 그리는 중에는 반투명 레이어를 합쳐 미리 보여 준다(아직 이미지에는 굽지 않음).
            preview = Image.alpha_composite(preview.convert("RGBA"), self.active_overlay).convert("RGB")
        width, height = preview.size
        self.scale = min(self.MAX_WIDTH / width, self.MAX_HEIGHT / height, 1.0) * self.zoom
        # 드래그 중에는 빠른 리샘플링으로 지연을 줄이고, 손을 떼면 고품질로 다시 그린다.
        resample = Image.Resampling.NEAREST if fast else Image.Resampling.LANCZOS
        display = preview.resize((max(1, round(width * self.scale)), max(1, round(height * self.scale))), resample)
        self.photo = ImageTk.PhotoImage(display)
        self.canvas.config(width=display.width, height=display.height)
        self.canvas.delete("all"); self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        if self.selected_text_index is not None and self.selected_text_index < len(self.text_items):
            item = self.text_items[self.selected_text_index]
            padding = 5
            self.canvas.create_rectangle((item["x"]-padding)*self.scale, (item["y"]-padding)*self.scale, (item["x"]+item["width"]+padding)*self.scale, (item["y"]+item["height"]+padding)*self.scale, outline="#3478f6", width=2, dash=(5, 3))
        if self.selected_number_index is not None and self.selected_number_index < len(self.number_items):
            item = self.number_items[self.selected_number_index]; radius = item["size"] // 2 + 5
            self.canvas.create_oval((item["x"]-radius)*self.scale, (item["y"]-radius)*self.scale, (item["x"]+radius)*self.scale, (item["y"]+radius)*self.scale, outline="#3478f6", width=2, dash=(5, 3))
            handle_x, handle_y = (item["x"]+radius)*self.scale, (item["y"]+radius)*self.scale
            self.canvas.create_rectangle(handle_x-5, handle_y-5, handle_x+5, handle_y+5, fill="#3478f6", outline="white")
        self.zoom_label.config(text=f"{round(self.zoom * 100)}%")

    def point(self, event): return (max(0, round(event.x / self.scale)), max(0, round(event.y / self.scale)))
    def mouse_down(self, event):
        self.start = self.point(event)
        if self.mode in ("pen", "highlight"):
            self.snapshot(); self.flatten_text_items(); self.pen_last = self.start
            if self.mode == "highlight":
                self.active_overlay = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        if self.mode == "number" and self.on_number_handle(*self.start):
            # 번호 모드라도 방금 찍은 번호의 핸들을 잡으면 새 번호를 찍지 않고 크기를 조절한다.
            self.drag_number_index, self.number_resize = self.selected_number_index, True
            self.snapshot()
            return
        if self.mode == "text":
            x, y = event.x, event.y
            self.text_marker = self.canvas.create_rectangle(x, y, x + 5, y + 5, outline="#3478f6", width=2, dash=(5, 3))
        elif self.mode == "select":
            index = self.find_text_at(*self.start)
            if index is not None:
                self.selected_text_index, self.selected_number_index = index, None
                item = self.text_items[index]
                self.text_size_var.set(item["size"]); self.color = item["color"]
                self.drag_text_index, self.drag_initial = index, (item["x"], item["y"])
                self.snapshot(); self.refresh()
            elif self.on_number_handle(*self.start):
                # 핸들은 원 밖에 있으므로 따로 검사한다: 선택된 번호의 핸들을 잡으면 크기 조절 시작.
                self.drag_number_index = self.selected_number_index
                self.number_resize = True
                self.snapshot()
            else:
                number_index = self.find_number_at(*self.start)
                if number_index is not None:
                    self.selected_number_index, self.selected_text_index = number_index, None
                    item = self.number_items[number_index]
                    self.number_size_var.set(item["size"]); self.color = item["color"]; self.number_style = item.get("style", "filled")
                    self.drag_number_index, self.number_resize = number_index, False
                    self.number_drag_initial = (item["x"], item["y"])
                    self.snapshot(); self.refresh()
                else:
                    self.selected_text_index = self.selected_number_index = None
                    self.refresh()

    def mouse_drag(self, event):
        if self.mode == "pen" and self.pen_last:
            if self.straight_var.get():
                self.draw_live_preview("ruler", self.start[0]*self.scale, self.start[1]*self.scale, event.x, event.y)
            else:
                current = self.point(event)
                ImageDraw.Draw(self.image).line((self.pen_last, current), fill=self.color, width=self.line_width_var.get(), joint="curve")
                self.pen_last = current
                self.refresh(fast=True)
        elif self.mode == "highlight" and self.pen_last:
            if self.straight_var.get():
                self.draw_live_preview("ruler", self.start[0]*self.scale, self.start[1]*self.scale, event.x, event.y)
            elif self.active_overlay is not None:
                current = self.point(event)
                alpha = round(255 * max(5, min(100, self.opacity_var.get())) / 100)
                width = max(14, self.line_width_var.get() * 3)
                ImageDraw.Draw(self.active_overlay).line((self.pen_last, current), fill=self.rgba(self.color, alpha), width=width, joint="curve")
                self.pen_last = current
                self.refresh(fast=True)
        elif self.mode == "text" and self.text_marker and self.start:
            self.canvas.coords(self.text_marker, self.start[0]*self.scale, self.start[1]*self.scale, event.x, event.y)
        elif self.drag_text_index is not None and self.start and self.drag_initial:
            x, y = self.point(event)
            item = self.text_items[self.drag_text_index]
            item["x"] = max(0, self.drag_initial[0] + x - self.start[0])
            item["y"] = max(0, self.drag_initial[1] + y - self.start[1])
            self.dirty = True; self.refresh(fast=True)
        elif self.drag_number_index is not None:
            x, y = self.point(event); item = self.number_items[self.drag_number_index]
            if self.number_resize:
                # 중심에서 커서까지 거리로 크기를 정한다.
                item["size"] = max(16, min(220, 2 * max(abs(x-item["x"]), abs(y-item["y"]))))
                self.number_size_var.set(item["size"])
            elif self.number_drag_initial is not None and self.start:
                item["x"] = max(0, self.number_drag_initial[0] + x - self.start[0])
                item["y"] = max(0, self.number_drag_initial[1] + y - self.start[1])
            self.dirty = True; self.refresh(fast=True)
        elif self.start and self.mode in {"crop", "crop_round", "crop_ellipse", "crop_circle", "mosaic", "blur", "arrow", "rect", "ellipse", "line", "dashed_rect", "ruler", "callout", "magnify"}:
            self.draw_live_preview(self.mode, self.start[0]*self.scale, self.start[1]*self.scale, event.x, event.y)

    def zoom_with_wheel(self, event):
        self.zoom = max(0.35, min(2.5, self.zoom + (0.1 if event.delta > 0 else -0.1)))
        self.refresh()

    def update_cursor(self, event):
        """텍스트 상자 위에서는 이동 가능함을 나타내는 커서를 보여 준다."""
        if self.mode == "select" and self.find_text_at(*self.point(event)) is not None:
            self.canvas.config(cursor="fleur")
        elif self.mode == "select" and self.selected_number_index is not None:
            item = self.number_items[self.selected_number_index]; radius = item["size"] // 2 + 5; x, y = self.point(event)
            self.canvas.config(cursor="sizing" if abs(x-(item["x"]+radius)) < 12 and abs(y-(item["y"]+radius)) < 12 else "arrow")
        else:
            self.canvas.config(cursor="crosshair")
        if self.mode == "number" and not self.start:
            self.draw_live_preview("number", event.x, event.y, event.x, event.y)
        elif not self.start:
            self.clear_live_preview()

    def clear_live_preview(self):
        for item_id in self.preview_ids:
            self.canvas.delete(item_id)
        self.preview_ids = []

    def draw_live_preview(self, mode, x1, y1, x2, y2):
        """마우스를 놓기 전 적용될 영역·도형·번호를 반투명/점선으로 보여 준다."""
        self.clear_live_preview()
        if mode == "mosaic":
            self.preview_ids.append(self.canvas.create_rectangle(x1, y1, x2, y2, outline="#be123c", width=2, dash=(5, 3), fill="#fb7185", stipple="gray25"))
        elif mode == "blur":
            self.preview_ids.append(self.canvas.create_rectangle(x1, y1, x2, y2, outline="#2563eb", width=2, dash=(5, 3), fill="#93c5fd", stipple="gray25"))
        elif mode in ("crop", "crop_round"):
            self.preview_ids.append(self.canvas.create_rectangle(x1, y1, x2, y2, outline="#3478f6", width=2, dash=(5, 3)))
        elif mode in ("crop_ellipse", "crop_circle"):
            if mode == "crop_circle":
                # 원형은 가로·세로 중 짧은 쪽에 맞춰 정원을 유지한다.
                side = min(abs(x2 - x1), abs(y2 - y1))
                x2 = x1 + side * (1 if x2 >= x1 else -1)
                y2 = y1 + side * (1 if y2 >= y1 else -1)
            self.preview_ids.append(self.canvas.create_oval(x1, y1, x2, y2, outline="#3478f6", width=2, dash=(5, 3)))
        elif mode == "callout":
            # 시작점 = 화살촉이 가리킬 곳, 끝점 = 말풍선이 놓일 곳
            self.preview_ids.append(self.canvas.create_line(x1, y1, x2, y2, fill=self.color, width=2, dash=(4, 3)))
            self.preview_ids.append(self.canvas.create_rectangle(x2 - 55, y2 - 22, x2 + 55, y2 + 22, outline=self.color, width=2, dash=(4, 3)))
            self.preview_ids.append(self.canvas.create_oval(x1 - 4, y1 - 4, x1 + 4, y1 + 4, fill=self.color, outline=""))
        elif mode == "magnify":
            import math
            radius = max(10, math.hypot(x2 - x1, y2 - y1))
            self.preview_ids.append(self.canvas.create_oval(x1 - radius, y1 - radius, x1 + radius, y1 + radius, outline=self.color, width=2, dash=(5, 3)))
        elif mode in {"arrow", "line"}:
            self.preview_ids.append(self.canvas.create_line(x1, y1, x2, y2, fill=self.color, width=4, arrow="last" if mode == "arrow" else "none"))
        elif mode == "ruler":
            ex, ey = self.snap_to_angle((x1, y1), (x2, y2))
            self.preview_ids.append(self.canvas.create_line(x1, y1, ex, ey, fill=self.color, width=max(2, self.line_width_var.get())))
        elif mode in {"rect", "dashed_rect"}:
            self.preview_ids.append(self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.color, width=3, dash=(5, 3) if mode == "dashed_rect" else ()))
        elif mode == "ellipse":
            self.preview_ids.append(self.canvas.create_oval(x1, y1, x2, y2, outline=self.color, width=3))
        elif mode == "number":
            radius = max(12, self.number_size_var.get() // 2)
            if self.number_style == "stamp":
                self.preview_ids.append(self.canvas.create_text(x1, y1, text=self.stamp_char, fill=self.color, font=("맑은 고딕", max(12, self.number_size_var.get() // 2), "bold")))
                return
            if self.number_style in ("plain", "paren"):
                text = f"{self.number})" if self.number_style == "paren" else str(self.number)
                self.preview_ids.append(self.canvas.create_text(x1, y1, text=text, fill=self.color, font=("맑은 고딕", max(12, self.number_size_var.get() // 2), "bold")))
                return
            if self.number_style == "outline":
                self.preview_ids.append(self.canvas.create_oval(x1-radius, y1-radius, x1+radius, y1+radius, fill="white", outline=self.color, width=3))
                text_fill = self.color
            elif self.number_style == "square":
                self.preview_ids.append(self.canvas.create_rectangle(x1-radius, y1-radius, x1+radius, y1+radius, fill=self.color, outline="white", width=2))
                text_fill = "white"
            else:
                self.preview_ids.append(self.canvas.create_oval(x1-radius, y1-radius, x1+radius, y1+radius, fill=self.color, outline="white", width=2))
                text_fill = "white"
            self.preview_ids.append(self.canvas.create_text(x1, y1, text=str(self.number), fill=text_fill, font=("맑은 고딕", 12, "bold")))

    def mouse_up(self, event):
        if not self.start: return
        self.clear_live_preview()
        x1, y1 = self.start; x2, y2 = self.point(event); self.start = None
        if self.mode in ("pen", "highlight"):
            if self.straight_var.get():
                # 직선(자) 모드: 시작~끝을 수평·수직·45°로 맞춘 반듯한 직선을 그린다.
                end = self.snap_to_angle((x1, y1), (x2, y2))
                if self.mode == "pen":
                    ImageDraw.Draw(self.image).line(((x1, y1), end), fill=self.color, width=self.line_width_var.get())
                else:
                    alpha = round(255 * max(5, min(100, self.opacity_var.get())) / 100)
                    width = max(14, self.line_width_var.get() * 3)
                    if self.active_overlay is None:
                        self.active_overlay = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
                    ImageDraw.Draw(self.active_overlay).line(((x1, y1), end), fill=self.rgba(self.color, alpha), width=width)
            if self.mode == "highlight" and self.active_overlay is not None:
                # 그동안 그린 반투명 스트로크를 이미지에 한 번에 합친다.
                self.image = Image.alpha_composite(self.image.convert("RGBA"), self.active_overlay).convert("RGB")
                self.active_overlay = None
            self.pen_last = None
            self.refresh()
            return
        if self.drag_text_index is not None:
            self.drag_text_index, self.drag_initial = None, None
            self.refresh()
            return
        if self.drag_number_index is not None:
            self.drag_number_index, self.number_resize, self.number_drag_initial = None, False, None
            self.refresh()
            return
        if self.mode in ("crop", "crop_round", "crop_ellipse", "crop_circle") and abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
            self.snapshot(); self.flatten_text_items()
            left, top = min(x1, x2), min(y1, y2); right, bottom = max(x1, x2), max(y1, y2)
            if self.mode == "crop_circle":
                # 미리보기와 같은 정원: 드래그 방향 쪽으로 짧은 변에 맞춘다.
                side = min(right - left, bottom - top)
                if x2 >= x1: right = left + side
                else: left = right - side
                if y2 >= y1: bottom = top + side
                else: top = bottom - side
            region = self.image.crop((left, top, right, bottom))
            self.image = region if self.mode == "crop" else self.shaped_crop(region, self.mode)
            self.refresh()
        elif self.mode == "mosaic" and abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
            self.snapshot(); self.flatten_text_items(); box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)); region = self.image.crop(box)
            small = region.resize((max(1, region.width // 16), max(1, region.height // 16)), Image.Resampling.BILINEAR)
            self.image.paste(small.resize(region.size, Image.Resampling.NEAREST), box); self.refresh()
        elif self.mode == "arrow":
            self.snapshot(); self.flatten_text_items(); self.draw_arrow((x1, y1), (x2, y2)); self.refresh()
        elif self.mode in ("rect", "ellipse", "line", "dashed_rect"):
            self.snapshot(); self.flatten_text_items(); self.draw_shape(self.mode, (x1, y1), (x2, y2)); self.refresh()
        elif self.mode == "ruler":
            # 자(직선): 끝점을 수평·수직·45°로 맞춰 반듯한 선을 긋는다.
            self.snapshot(); self.flatten_text_items()
            end = self.snap_to_angle((x1, y1), (x2, y2))
            ImageDraw.Draw(self.image).line(((x1, y1), end), fill=self.color, width=self.line_width_var.get()); self.refresh()
        elif self.mode == "callout" and abs(x2 - x1) + abs(y2 - y1) > 12:
            text = simpledialog.askstring(APP_NAME, "말풍선에 넣을 문구를 입력하세요.", parent=self)
            if text:
                self.snapshot(); self.flatten_text_items()
                self.draw_callout((x1, y1), (x2, y2), text); self.refresh()
        elif self.mode == "magnify":
            import math
            radius = round(math.hypot(x2 - x1, y2 - y1))
            if radius > 12:
                self.snapshot(); self.flatten_text_items()
                self.draw_magnifier((x1, y1), radius); self.refresh()
        elif self.mode == "blur" and abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
            self.snapshot(); self.flatten_text_items(); box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)); region = self.image.crop(box)
            radius = max(4, min(region.width, region.height) // 18)
            self.image.paste(region.filter(ImageFilter.GaussianBlur(radius)), box); self.refresh()
        elif self.mode == "number":
            # 번호 모드를 유지해 다음 클릭이면 다음 번호(2, 3, …)가 이어서 찍히게 한다.
            # 방금 찍은 번호는 선택 상태로 남아, 핸들을 끌거나 '번호' 크기 상자로 바로 크기를 조절할 수 있다.
            self.snapshot(); self.add_number(x1, y1)
            if self.number_style != "stamp":
                self.number += 1  # 스탬프는 순번 없이 같은 도장을 계속 찍는다.
            self.refresh()
        elif self.mode == "text":
            if self.text_marker: self.canvas.delete(self.text_marker); self.text_marker = None
            left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
            width, height = max(80, right-left), max(35, bottom-top)
            text = simpledialog.askstring(APP_NAME, "선택한 위치에 넣을 문구를 입력하세요.", parent=self)
            if text:
                self.snapshot(); self.add_text(left, top, width, height, text); self.mode = "select"; self.refresh()
        elif self.mode == "select":
            self.select_text_at(x1, y1)

    @staticmethod
    def shaped_crop(region, mode):
        """타원·원형·둥근 사각형 모양으로 잘라내고, 모양 밖은 흰색으로 채운다.
        3배 마스크를 만들었다 줄여 가장자리를 부드럽게 만든다."""
        scale = 3
        mask = Image.new("L", (region.width * scale, region.height * scale), 0)
        draw = ImageDraw.Draw(mask)
        if mode == "crop_round":
            radius = max(10, min(region.width, region.height) // 8) * scale
            draw.rounded_rectangle((0, 0, region.width * scale - 1, region.height * scale - 1), radius=radius, fill=255)
        else:  # crop_ellipse · crop_circle
            draw.ellipse((0, 0, region.width * scale - 1, region.height * scale - 1), fill=255)
        mask = mask.resize(region.size, Image.Resampling.LANCZOS)
        result = Image.new("RGB", region.size, "white")
        result.paste(region, (0, 0), mask)
        return result

    def draw_callout(self, anchor, pos, text):
        """설명 말풍선: pos에 흰 상자를 그리고 anchor를 가리키는 꼬리를 붙인다."""
        draw = ImageDraw.Draw(self.image)
        font = self.font(self.text_size_var.get())
        wrapped = self.wrap_text(draw, text, font, 340)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4)
        pad = 15
        width, height = bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2
        left = max(4, min(self.image.width - width - 4, pos[0] - width // 2))
        top = max(4, min(self.image.height - height - 4, pos[1] - height // 2))
        right, bottom = left + width, top + height
        line_width = max(3, self.line_width_var.get())
        # 꼬리 밑변: 앵커와 가장 가까운 변 위에 잡는다.
        cx, cy = (left + right) // 2, (top + bottom) // 2
        dx, dy = anchor[0] - cx, anchor[1] - cy
        base = min(20, width // 3, height // 3)
        if abs(dx) * height > abs(dy) * width:   # 좌/우 변
            edge_x = right if dx > 0 else left
            base_y = max(top + 14, min(bottom - 14, cy))
            p1, p2 = (edge_x, base_y - base), (edge_x, base_y + base)
        else:                                     # 위/아래 변
            edge_y = bottom if dy > 0 else top
            base_x = max(left + 14, min(right - 14, cx))
            p1, p2 = (base_x - base, edge_y), (base_x + base, edge_y)
        draw.rounded_rectangle((left, top, right, bottom), radius=12, fill="white", outline=self.color, width=line_width)
        draw.polygon((anchor, p1, p2), fill="white", outline=self.color)
        draw.line((anchor, p1), fill=self.color, width=line_width)
        draw.line((anchor, p2), fill=self.color, width=line_width)
        draw.line((p1, p2), fill="white", width=line_width + 2)  # 꼬리가 상자와 만나는 경계선을 지운다.
        draw.multiline_text((left + pad - bbox[0], top + pad - bbox[1]), wrapped, fill="#1d1d1f", font=font, spacing=4)

    def draw_magnifier(self, center, radius):
        """center 주변을 2배로 키운 원을 옆에 붙여, 세부를 강조해 보여 준다."""
        image = self.image
        radius = min(radius, image.width // 2 - 2, image.height // 2 - 2)
        if radius < 8:
            return
        x = max(radius, min(image.width - radius, center[0]))
        y = max(radius, min(image.height - radius, center[1]))
        source = image.crop((x - radius, y - radius, x + radius, y + radius))
        big_r = min(round(radius * 1.9), image.width // 2 - 2, image.height // 2 - 2)
        enlarged = source.resize((big_r * 2, big_r * 2), Image.Resampling.LANCZOS)
        scale = 3
        mask = Image.new("L", (big_r * 2 * scale, big_r * 2 * scale), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, big_r * 2 * scale - 1, big_r * 2 * scale - 1), fill=255)
        mask = mask.resize((big_r * 2, big_r * 2), Image.Resampling.LANCZOS)
        # 확대 원 위치: 공간이 가장 넉넉한 대각선 방향에 놓는다.
        gap = radius + big_r + 24
        candidates = sorted(((sx, sy) for sx in (1, -1) for sy in (1, -1)),
                            key=lambda d: -( (image.width - x if d[0] > 0 else x) + (image.height - y if d[1] > 0 else y) ))
        px, py = x, y
        for sx, sy in candidates:
            cx, cy = x + sx * gap * 0.72, y + sy * gap * 0.72
            if big_r <= cx <= image.width - big_r and big_r <= cy <= image.height - big_r:
                px, py = round(cx), round(cy)
                break
        else:
            px = max(big_r, min(image.width - big_r, x + gap))
            py = max(big_r, min(image.height - big_r, y))
        draw = ImageDraw.Draw(image)
        line_width = max(3, self.line_width_var.get())
        draw.line((x, y, px, py), fill=self.color, width=max(2, line_width - 1))
        image.paste(enlarged, (px - big_r, py - big_r), mask)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=self.color, width=line_width)
        draw.ellipse((px - big_r, py - big_r, px + big_r, py + big_r), outline=self.color, width=line_width + 1)

    def pin_current(self):
        """현재 편집 중인 이미지를 화면에 항상-위로 붙여 둔다."""
        from pin import PinnedImage
        PinnedImage(self.app, self.rendered_image())
        self.app.toast("화면 고정", "드래그로 이동 · 휠로 크기 조절 · 더블클릭으로 닫기")

    def redact_sensitive(self):
        """OCR로 전화번호·이메일·주민번호를 찾아 자동으로 모자이크한다."""
        try:
            import ocr
            regions = ocr.find_sensitive(self.rendered_image())
        except RuntimeError as error:
            messagebox.showwarning(APP_NAME, str(error), parent=self); return
        if not regions:
            self.app.toast("개인정보 가리기", "전화번호·이메일·주민번호 형태를 찾지 못했습니다."); return
        self.snapshot(); self.flatten_text_items()
        pad = 4
        for rx, ry, rw, rh in regions:
            box = (max(0, int(rx - pad)), max(0, int(ry - pad)),
                   min(self.image.width, int(rx + rw + pad)), min(self.image.height, int(ry + rh + pad)))
            if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                continue
            region = self.image.crop(box)
            small = region.resize((max(1, region.width // 10), max(1, region.height // 10)), Image.Resampling.BILINEAR)
            self.image.paste(small.resize(region.size, Image.Resampling.NEAREST), box)
        self.refresh()
        self.app.toast("개인정보 가리기 완료", f"{len(regions)}곳을 모자이크했습니다. (Ctrl+Z로 되돌리기 가능)")

    def draw_arrow(self, start, end):
        import math
        draw = ImageDraw.Draw(self.image); draw.line((start, end), fill=self.color, width=self.line_width_var.get())
        angle = math.atan2(end[1] - start[1], end[0] - start[0]); size = 18
        points = [end, (end[0] - size * math.cos(angle - .55), end[1] - size * math.sin(angle - .55)), (end[0] - size * math.cos(angle + .55), end[1] - size * math.sin(angle + .55))]
        draw.polygon(points, fill=self.color)

    def draw_shape(self, mode, start, end):
        draw = ImageDraw.Draw(self.image); box = (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1]))
        if mode == "rect": draw.rectangle(box, outline=self.color, width=self.line_width_var.get())
        elif mode == "ellipse": draw.ellipse(box, outline=self.color, width=self.line_width_var.get())
        elif mode == "line": draw.line((start, end), fill=self.color, width=self.line_width_var.get())
        else:
            # Pillow의 점선은 직접 그려야 하므로 사각형 네 변을 짧은 선분으로 나눈다.
            x1, y1, x2, y2 = box
            for position in range(x1, x2, 16):
                draw.line((position, y1, min(position+9, x2), y1), fill=self.color, width=4); draw.line((position, y2, min(position+9, x2), y2), fill=self.color, width=4)
            for position in range(y1, y2, 16):
                draw.line((x1, position, x1, min(position+9, y2)), fill=self.color, width=4); draw.line((x2, position, x2, min(position+9, y2)), fill=self.color, width=4)

    def draw_number(self, x, y):
        draw = ImageDraw.Draw(self.image); radius = 17
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=self.color, outline="white", width=2)
        font = self.font(18); text = str(self.number); box = draw.textbbox((0, 0), text, font=font)
        draw.text((x-(box[2]-box[0])/2, y-(box[3]-box[1])/2-2), text, fill="white", font=font)

    def add_number(self, x, y):
        item = {"x": x, "y": y, "number": self.number, "size": self.number_size_var.get(), "color": self.color, "style": self.number_style}
        if self.number_style == "stamp":
            item["char"] = self.stamp_char
        self.number_items.append(item)
        self.selected_number_index, self.selected_text_index = len(self.number_items) - 1, None

    def font(self, size, font_name=None):
        path = self.font_paths.get(font_name or self.font_var.get(), r"C:\Windows\Fonts\malgun.ttf")
        try: return ImageFont.truetype(path, size)
        except OSError: return ImageFont.load_default()

    @staticmethod
    def stamp_font(size):
        """✓ ★ 같은 기호가 온전히 들어 있는 글꼴을 우선 사용한다."""
        for name in ("seguisym.ttf", "seguiemj.ttf", "malgun.ttf"):
            try: return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)
            except OSError: continue
        return ImageFont.load_default()

    def add_text(self, x, y, width, height, text):
        self.text_items.append({"x": x, "y": y, "width": width, "height": height, "text": text, "size": self.text_size_var.get(), "color": self.color, "font": self.font_var.get()})
        self.selected_text_index = len(self.text_items) - 1

    def find_text_at(self, x, y):
        for index in range(len(self.text_items) - 1, -1, -1):
            item = self.text_items[index]
            if item["x"] <= x <= item["x"] + item["width"] and item["y"] <= y <= item["y"] + item["height"]:
                return index
        return None

    def find_number_at(self, x, y):
        for index in range(len(self.number_items) - 1, -1, -1):
            item = self.number_items[index]; radius = max(12, item["size"] // 2)
            if (x-item["x"]) ** 2 + (y-item["y"]) ** 2 <= radius ** 2:
                return index
        return None

    def on_number_handle(self, x, y):
        """선택된 번호의 우하단 크기 조절 핸들(원 바깥) 위인지 확인한다."""
        if self.selected_number_index is None or self.selected_number_index >= len(self.number_items):
            return False
        item = self.number_items[self.selected_number_index]; radius = item["size"] // 2 + 5
        return abs(x - (item["x"] + radius)) < 16 and abs(y - (item["y"] + radius)) < 16

    def cancel_tool(self, _event=None):
        """Esc: 그리던 미리보기와 선택을 모두 지우고 선택 도구로 돌아간다."""
        self.clear_live_preview()
        if self.text_marker:
            self.canvas.delete(self.text_marker); self.text_marker = None
        self.start = self.pen_last = None
        self.active_overlay = None
        self.drag_text_index = self.drag_number_index = None
        self.selected_text_index = self.selected_number_index = None
        self.mode = "select"
        self.refresh()

    def delete_selected(self, _event=None):
        """선택된 번호나 텍스트를 삭제한다."""
        if self.selected_text_index is not None and self.selected_text_index < len(self.text_items):
            self.snapshot(); del self.text_items[self.selected_text_index]; self.selected_text_index = None; self.refresh()
        elif self.selected_number_index is not None and self.selected_number_index < len(self.number_items):
            self.snapshot(); del self.number_items[self.selected_number_index]; self.selected_number_index = None; self.refresh()
        else:
            messagebox.showinfo(APP_NAME, "삭제할 대상을 먼저 '선택' 도구로 클릭하세요.", parent=self)

    def select_text_at(self, x, y):
        self.selected_text_index = self.find_text_at(x, y)
        self.selected_number_index = None
        if self.selected_text_index is not None:
            item = self.text_items[self.selected_text_index]
            self.text_size_var.set(item["size"]); self.color = item["color"]; self.font_var.set(item.get("font", self.font_var.get()))
        else:
            self.selected_number_index = self.find_number_at(x, y)
            if self.selected_number_index is not None:
                item = self.number_items[self.selected_number_index]
                self.number_size_var.set(item["size"]); self.color = item["color"]
        self.refresh()

    def edit_text_at_point(self, event):
        """이미지를 더블클릭하면, 그 자리에 텍스트가 있을 때만 선택해 편집한다(빈 곳은 아무 동작 없음)."""
        index = self.find_text_at(*self.point(event))
        if index is None:
            return
        self.selected_text_index, self.selected_number_index = index, None
        self.refresh()
        self.edit_selected_text()

    def edit_selected_text(self, _event=None):
        if self.selected_text_index is None:
            messagebox.showinfo(APP_NAME, "편집할 텍스트를 '선택' 도구로 클릭한 뒤 눌러 주세요.", parent=self)
            return
        item = self.text_items[self.selected_text_index]
        text = simpledialog.askstring(APP_NAME, "텍스트 편집", initialvalue=item["text"], parent=self)
        if text:
            self.snapshot(); item["text"] = text; self.dirty = True; self.refresh()

    def change_selected_text_size(self, _event=None):
        if self.selected_text_index is not None:
            self.text_items[self.selected_text_index]["size"] = self.text_size_var.get()
            self.dirty = True; self.refresh()

    def change_selected_text_font(self, _event=None):
        if self.selected_text_index is not None:
            self.text_items[self.selected_text_index]["font"] = self.font_var.get()
            self.dirty = True; self.refresh()

    def change_selected_number_size(self, _event=None):
        if self.selected_number_index is not None:
            self.number_items[self.selected_number_index]["size"] = self.number_size_var.get()
            self.dirty = True; self.refresh()

    def apply_size(self):
        target = {"HWP 문서 폭 (1600px)": 1600, "HWP 반쪽 폭 (800px)": 800, "작은 설명 (550px)": 550}.get(self.size_var.get())
        if target and self.image.width != target:
            self.snapshot(); self.flatten_text_items()
            self.image = self.image.resize((target, max(1, round(self.image.height * target / self.image.width))), Image.Resampling.LANCZOS); self.refresh()

    @staticmethod
    def encoded_bytes(image, fmt, quality=None):
        """현재 형식·품질로 저장했을 때의 파일 크기(바이트)를 계산한다."""
        buffer = io.BytesIO()
        if fmt == "JPG": image.convert("RGB").save(buffer, "JPEG", quality=quality or 95, optimize=True)
        elif fmt == "WEBP": image.save(buffer, "WEBP", quality=quality or 95)
        elif fmt == "GIF": image.convert("P", palette=Image.Palette.ADAPTIVE).save(buffer, "GIF")
        else: image.save(buffer, fmt)
        return buffer.tell()

    def best_quality(self, image, fmt, target):
        """목표 용량을 넘지 않는 가장 높은 품질을 이진 탐색으로 찾는다."""
        lo, hi, best = 20, 95, None
        while lo <= hi:
            mid = (lo + hi) // 2
            size = self.encoded_bytes(image, fmt, mid)
            if size <= target: best, lo = (mid, size), mid + 1
            else: hi = mid - 1
        return best or (20, self.encoded_bytes(image, fmt, 20))

    @staticmethod
    def scaled_down(image, target, size):
        """용량 비율에 맞춰 이미지를 한 단계 축소한다(최소 폭 200px)."""
        factor = min(0.95, (target / size) ** 0.5)
        width = max(200, round(image.width * factor))
        return image.resize((width, max(1, round(image.height * width / image.width))), Image.Resampling.LANCZOS)

    def parse_target_bytes(self):
        value = self.target_size_var.get()
        if value == "직접 입력…":
            kb = simpledialog.askinteger(APP_NAME, "목표 용량을 KB 단위로 입력하세요.\n예: 500 (= 0.5MB)", parent=self, minvalue=30, maxvalue=51200)
            return kb * 1024 if kb else None
        return {"300KB": 300, "500KB": 500, "1MB": 1024, "2MB": 2048}[value] * 1024

    def fit_to_target_size(self):
        """저장 파일이 목표 용량 이하가 되도록 품질을(부족하면 크기까지) 자동 조정한다."""
        target = self.parse_target_bytes()
        if not target:
            return
        fmt = self.format_var.get()
        self.snapshot(); self.flatten_text_items()
        image, quality = self.image, None
        if fmt in ("JPG", "WEBP"):
            # 품질을 먼저 낮추고, 품질 20으로도 크면 이미지를 줄여 다시 시도한다.
            for _ in range(8):
                quality, size = self.best_quality(image, fmt, target)
                if size <= target or image.width <= 200: break
                image = self.scaled_down(image, target, size)
        else:
            # PNG·BMP·GIF는 품질 개념이 없으므로 크기 축소로만 맞춘다.
            size = self.encoded_bytes(image, fmt)
            for _ in range(8):
                if size <= target or image.width <= 200: break
                image = self.scaled_down(image, target, size)
                size = self.encoded_bytes(image, fmt)
        self.image, self.quality_override = image, quality
        self.dirty = True; self.refresh()
        detail = f"약 {size / 1024:,.0f}KB" + (f" · 품질 {quality}" if quality else "") + f" · 폭 {image.width}px"
        if size > target:
            self.app.toast("용량 맞추기", f"최소 크기 한계로 목표보다 큽니다.\n{detail}")
        else:
            self.app.toast("용량 맞추기 완료", f"{detail}\n저장하면 이 용량으로 기록됩니다.")

    def apply_document_style(self):
        margin = {"여백 없음": 0, "흰 여백 8px": 8, "흰 여백 16px": 16}[self.margin_var.get()]
        if not margin: return
        self.snapshot(); self.flatten_text_items(); styled = Image.new("RGB", (self.image.width + margin*2, self.image.height + margin*2), "white")
        styled.paste(self.image, (margin, margin)); ImageDraw.Draw(styled).rectangle((0, 0, styled.width-1, styled.height-1), outline="#cbd5e1", width=1)
        self.image = styled; self.refresh()

    def copy_for_hwp(self):
        self.app.copy_image(self.rendered_image()); self.app.toast("클립보드 복사 완료", "HWP·워드 등 어디서든 Ctrl+V로 붙여넣으세요.")

    def save_only(self):
        path = self.app.save_image(self.rendered_image(), self.format_var.get(), quality=self.quality_override); self.app.record_capture(path); self.app.toast("이미지 저장 완료", path.name)
        self.dirty = False  # 방금 저장했으므로 창을 닫을 때 다시 저장 여부를 묻지 않는다.

    def finish(self):
        final_image = self.rendered_image()
        if self.app.settings["copy_to_clipboard"]: self.app.copy_image(final_image)
        # 원본은 캡처 시점에 이미 자동 저장했다. 편집한 경우에만 편집본을 한 장 더 저장한다.
        if self.auto_saved_path and not self.dirty:
            path = self.auto_saved_path
        else:
            path = self.app.save_image(final_image, self.format_var.get(), quality=self.quality_override) if self.app.settings["auto_save"] else None
            self.app.record_capture(path)
        if self.app.settings["show_save_notification"]: self.app.toast("캡처 완료", "HWP에서 Ctrl+V로 붙여 넣으세요." + (f"\n{path.name} 저장됨" if path else ""))
        self.close()

    def close(self):
        if self.grab_current() == self:
            self.grab_release()
        self.destroy()

