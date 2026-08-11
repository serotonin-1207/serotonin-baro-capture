from __future__ import annotations

import ctypes
import io
import os
import queue
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageGrab, ImageTk

from config import APP_NAME, APP_VERSION, AUTHOR, DEFAULTS, DOWNLOADS, GITHUB_REPOSITORY, HOTKEY_ID, RELEASES_URL, load_settings, save_settings, set_startup
from hotkey import GlobalHotkeyListener
from assets import tray_image
from selector import ScreenSelector
from editor import CaptureEditor
from thumbbar import FloatingThumbnail
from windowpick import WindowPicker
from stepcap import StepCaptureSession
from ui import FONT, Switch, pill_button, section_label
from update_checker import UpdateCheckError, fetch_latest_release

try:
    import pystray
    HAS_TRAY = True
except ImportError:  # pystray가 없으면 트레이 없이도 동작한다.
    pystray = None
    HAS_TRAY = False


class CaptureApp:
    # CleanShot 풍: 크림 배경 위에 흰 카드, 맥 시스템 블루 액센트
    BG, PANEL, CARD, FIELD, TEXT, MUTED, BLUE = "#f4f2ee", "#f4f2ee", "#ffffff", "#ffffff", "#1d1d1f", "#8a8886", "#3478f6"
    BLUE_DARK, BLUE_SOFT, SIDEBAR, BORDER = "#2b66d9", "#eaf1fe", "#eceae4", "#e7e3db"
    NAV = [("캡처 홈", "home"), ("일반 설정", "general"), ("고급 설정", "advanced"), ("단축키 설정", "shortcuts"), ("캡처목록 설정", "recent")]
    NAV_ICONS = {"home": "⌂", "general": "⚙", "advanced": "⛭", "shortcuts": "⌨", "recent": "🕑"}

    def __init__(self):
        self.root = tk.Tk(); self.settings = load_settings(); self.current_page = None; self.vars = {}
        self.capture_events = queue.Queue()
        self.hotkey_listener = GlobalHotkeyListener(self.capture_events)
        self.hotkey_listener.start(); self.hotkey_listener.ready.wait(1.5)
        self.configure_window(); self.build_shell(); self.show_page("home")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.register_hotkey(self.settings["hotkey"]); self.root.after(80, self.poll_hotkeys)
        self.tray_icon = None
        self.step_session = None
        self.tray_commands = queue.Queue()
        self._hide_hinted = False
        self.start_tray()
        self.root.after(1800, lambda: self.check_for_updates(manual=False))
        if "--minimized" in sys.argv: self.root.after(400, self.hide)

    def configure_window(self):
        self.root.title("환경설정"); self.root.geometry("860x730"); self.root.minsize(760, 540); self.root.configure(bg=self.BG)
        try: self.root.iconphoto(True, ImageTk.PhotoImage(tray_image()))
        except Exception: pass
        style = ttk.Style(self.root); style.theme_use("clam")
        style.configure("TFrame", background=self.PANEL); style.configure("Page.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.PANEL, foreground=self.TEXT, font=("맑은 고딕", 10))
        style.configure("Title.TLabel", font=("맑은 고딕", 14, "bold"), foreground=self.TEXT)
        style.configure("Hint.TLabel", foreground=self.MUTED, font=("맑은 고딕", 9))
        style.configure("Accent.TButton", background=self.BLUE, foreground="#fff", borderwidth=0, padding=(24, 11), font=("맑은 고딕", 10, "bold"), focuscolor=self.BLUE)
        style.map("Accent.TButton", background=[("pressed", self.BLUE_DARK), ("active", self.BLUE_DARK)])
        style.configure("Secondary.TButton", background=self.CARD, foreground=self.TEXT, bordercolor=self.BORDER, borderwidth=1, padding=(18, 10), font=("맑은 고딕", 10), focuscolor=self.CARD)
        style.map("Secondary.TButton", background=[("active", "#f3f1ec")], bordercolor=[("active", "#d5d1c8")])
        style.configure("TEntry", fieldbackground=self.FIELD, bordercolor=self.BORDER, borderwidth=1, padding=8)
        style.configure("TCombobox", fieldbackground=self.FIELD, bordercolor=self.BORDER, borderwidth=1, padding=7)
        style.map("TCombobox", bordercolor=[("focus", self.BLUE)])
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.TEXT, font=("맑은 고딕", 10), focuscolor=self.PANEL)
        style.map("TCheckbutton", foreground=[("active", self.BLUE)])
        style.configure("TSeparator", background=self.BORDER)

    def build_shell(self):
        header = tk.Frame(self.root, bg=self.PANEL, height=64); header.pack(fill="x"); header.pack_propagate(False)
        tk.Frame(header, bg=self.BORDER, height=1).pack(side="bottom", fill="x")
        self.brand_logo = ImageTk.PhotoImage(tray_image().resize((30, 30), Image.LANCZOS))
        tk.Label(header, image=self.brand_logo, bg=self.PANEL).pack(side="left", padx=(22, 13))
        text_box = tk.Frame(header, bg=self.PANEL); text_box.pack(side="left")
        name_row = tk.Frame(text_box, bg=self.PANEL); name_row.pack(anchor="w")
        tk.Label(name_row, text=APP_NAME, bg=self.PANEL, fg=self.TEXT, font=("맑은 고딕", 13, "bold")).pack(side="left")
        tk.Label(name_row, text=APP_VERSION, bg="#eaf1fe", fg=self.BLUE, font=("맑은 고딕", 8, "bold"), padx=5, pady=1).pack(side="left", padx=(8, 0))
        status_box = tk.Frame(header, bg=self.PANEL); status_box.pack(side="right", padx=22)
        tk.Label(status_box, text="● 트레이에서 실행 중", bg=self.PANEL, fg="#22c55e", font=("맑은 고딕", 9)).pack(anchor="e")
        tk.Label(status_box, text=AUTHOR, bg=self.PANEL, fg=self.TEXT, font=("맑은 고딕", 9, "bold")).pack(anchor="e", pady=(3, 0))

        # 푸터를 먼저 하단에 고정한다. 이렇게 해야 본문이 길어져도 버튼이 창 밖으로 밀려나지 않는다.
        footer = tk.Frame(self.root, bg=self.PANEL, height=74); footer.pack(side="bottom", fill="x"); footer.pack_propagate(False)
        tk.Frame(footer, bg=self.BORDER, height=1).pack(side="top", fill="x")
        pill_button(footer, "기본값으로", self.restore_defaults, font_size=9, height=36).pack(side="left", padx=18, pady=13)
        pill_button(footer, "확인", self.apply_settings, primary=True, font_size=10, height=36, width=96).pack(side="right", padx=(8, 18), pady=13)
        pill_button(footer, "취소", self.hide, font_size=9, height=36, width=82).pack(side="right", pady=13)

        body = tk.Frame(self.root, bg=self.PANEL); body.pack(side="top", fill="both", expand=True)
        self.sidebar = tk.Frame(body, bg=self.SIDEBAR, width=210); self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        tk.Frame(self.sidebar, bg=self.BORDER, width=1).pack(side="right", fill="y")
        tk.Label(self.sidebar, text="메뉴", bg=self.SIDEBAR, fg="#a8a5a0", font=("맑은 고딕", 8, "bold")).pack(anchor="w", padx=22, pady=(16, 6))
        self.nav_buttons = {}
        for title, page in self.NAV:
            btn = tk.Button(self.sidebar, text=f" {self.NAV_ICONS.get(page, '·')}   {title}", anchor="w", relief="flat", bd=0,
                            bg=self.SIDEBAR, activebackground=self.BLUE_SOFT, fg="#57554f", activeforeground=self.BLUE,
                            font=("맑은 고딕", 10), padx=16, pady=10, cursor="hand2", command=lambda p=page: self.show_page(p))
            btn.pack(fill="x", padx=9, pady=1)
            btn.bind("<Enter>", lambda _e, p=page: self._nav_hover(p, True))
            btn.bind("<Leave>", lambda _e, p=page: self._nav_hover(p, False))
            self.nav_buttons[page] = btn

        # 페이지 탭과 구분되는 별도 동작: 편집 창을 직접 연다.
        tk.Frame(self.sidebar, bg=self.BORDER, height=1).pack(fill="x", padx=16, pady=(10, 8))
        edit_btn = tk.Button(self.sidebar, text=" ✎   이미지 편집", anchor="w", relief="flat", bd=0,
                             bg=self.SIDEBAR, activebackground=self.BLUE_SOFT, fg="#57554f", activeforeground=self.BLUE,
                             font=("맑은 고딕", 10), padx=16, pady=10, cursor="hand2", command=self.open_editor)
        edit_btn.pack(fill="x", padx=9, pady=1)
        edit_btn.bind("<Enter>", lambda _e: edit_btn.configure(bg="#e4e1da"))
        edit_btn.bind("<Leave>", lambda _e: edit_btn.configure(bg=self.SIDEBAR))

        # 본문은 캔버스 위에 올려, 내용이 창보다 길면 세로 스크롤되게 한다.
        page_area = tk.Frame(body, bg=self.PANEL); page_area.pack(side="left", fill="both", expand=True)
        self.page_canvas = tk.Canvas(page_area, bg=self.PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(page_area, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y"); self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page_holder = ttk.Frame(self.page_canvas, style="Page.TFrame", padding=(28, 24))
        self._page_window = self.page_canvas.create_window((0, 0), window=self.page_holder, anchor="nw")
        self.page_canvas.bind("<Configure>", lambda e: self.page_canvas.itemconfigure(self._page_window, width=e.width))
        self.page_holder.bind("<Configure>", lambda _e: self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all")))
        self.page_canvas.bind("<Enter>", lambda _e: self.page_canvas.bind_all("<MouseWheel>", self._on_page_scroll))
        self.page_canvas.bind("<Leave>", lambda _e: self.page_canvas.unbind_all("<MouseWheel>"))

    def _on_page_scroll(self, event):
        # 내용이 화면보다 길 때만 휠 스크롤이 의미가 있다.
        if self.page_canvas.bbox("all") and self.page_canvas.bbox("all")[3] > self.page_canvas.winfo_height():
            self.page_canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear_page(self):
        for child in self.page_holder.winfo_children(): child.destroy()
        self.vars = {}

    def show_page(self, page: str):
        if self.current_page:
            self.collect_current_page()
        self.current_page = page; self.clear_page(); self.highlight_nav(page)
        {"home": self.page_home, "general": self.page_general, "advanced": self.page_advanced, "shortcuts": self.page_shortcuts, "recent": self.page_recent}[page]()
        # 페이지를 바꾸면 스크롤을 맨 위로 되돌린다.
        if hasattr(self, "page_canvas"):
            self.page_canvas.yview_moveto(0); self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def highlight_nav(self, page: str):
        for key, btn in getattr(self, "nav_buttons", {}).items():
            if key == page:
                btn.configure(bg=self.BLUE_SOFT, fg=self.BLUE, font=("맑은 고딕", 10, "bold"))
            else:
                btn.configure(bg=self.SIDEBAR, fg="#57554f", font=("맑은 고딕", 10))

    def _nav_hover(self, page: str, entering: bool):
        if page == self.current_page: return
        self.nav_buttons[page].configure(bg="#e4e1da" if entering else self.SIDEBAR)

    def heading(self, title: str, hint: str = ""):
        ttk.Label(self.page_holder, text=title, style="Title.TLabel").pack(anchor="w")
        if hint: ttk.Label(self.page_holder, text=hint, style="Hint.TLabel").pack(anchor="w", pady=(4, 13))

    def check(self, key: str, text: str):
        """설정 항목 한 줄: 흰 카드 행 + 오른쪽 맥 스타일 토글 스위치."""
        variable = tk.BooleanVar(value=self.settings[key]); self.vars[key] = variable
        row = tk.Frame(self.page_holder, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=text, bg=self.CARD, fg=self.TEXT, font=(FONT, 10), anchor="w").pack(side="left", padx=14, pady=11)
        Switch(row, variable, bg=self.CARD).pack(side="right", padx=13)

    def separator(self): ttk.Separator(self.page_holder).pack(fill="x", pady=14)

    def page_home(self):
        """CleanShot 풍 시작 화면: 흰 히어로 카드 + 파란 알약 버튼 + 정보 카드."""
        shortcut = self.settings["hotkey"]
        hero = tk.Frame(self.page_holder, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 16))
        inner = tk.Frame(hero, bg=self.CARD); inner.pack(fill="x", padx=24, pady=20)
        tk.Label(inner, text="화면을 캡처할 준비가 됐습니다", bg=self.CARD, fg=self.TEXT, font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(inner, text="영역을 선택하면 클립보드에 복사되고, 우하단 미리보기 카드에서 편집·저장·텍스트 추출을 이어갈 수 있습니다.",
                 bg=self.CARD, fg=self.MUTED, font=(FONT, 9), wraplength=560, justify="left").pack(anchor="w", pady=(5, 15))
        row = tk.Frame(inner, bg=self.CARD); row.pack(anchor="w")
        pill_button(row, "＋  새 캡처", self.start_capture, primary=True, font_size=11, height=40, width=150).pack(side="left")
        pill_button(row, "🪟  창 캡처", self.start_window_capture, font_size=10, height=40, width=120).pack(side="left", padx=(10, 0))
        pill_button(row, "①  스텝 캡처", self.start_step_capture, font_size=10, height=40, width=130).pack(side="left", padx=(10, 0))
        tk.Label(row, text=f"⌨  {shortcut}", bg=self.BLUE_SOFT, fg=self.BLUE, font=(FONT, 9, "bold"), padx=13, pady=7).pack(side="left", padx=12)

        section_label(self.page_holder, "한눈에 보기", bg=self.PANEL).pack(anchor="w", pady=(2, 5))
        cards = tk.Frame(self.page_holder, bg=self.PANEL); cards.pack(fill="x", pady=(0, 2))
        cards.columnconfigure((0, 1), weight=1, uniform="info")
        info = [
            ("캡처 단축키", shortcut, "⌨"),
            ("저장 형식", f"{self.settings['image_format']} · 품질 {self.settings['quality']}", "🖼"),
            ("저장 위치", (self.settings["save_folder"] if self.settings["auto_save"] else "자동 저장 끔"), "📁"),
            ("최근 캡처", f"{len(self.settings['recent_captures'])}개", "🕑"),
        ]
        for index, (label, value, icon) in enumerate(info):
            card = tk.Frame(cards, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0 if index % 2 == 0 else 6, 6 if index % 2 == 0 else 0), pady=4)
            tk.Label(card, text=f"{icon}  {label}", bg=self.CARD, fg=self.MUTED, font=(FONT, 9)).pack(anchor="w", padx=14, pady=(9, 1))
            tk.Label(card, text=value, bg=self.CARD, fg=self.TEXT, font=(FONT, 11, "bold"),
                     anchor="w", wraplength=300, justify="left").pack(anchor="w", padx=14, pady=(0, 10), fill="x")

        action = tk.Frame(self.page_holder, bg=self.PANEL); action.pack(anchor="w", pady=(14, 0))
        pill_button(action, "단축키 변경", lambda: self.show_page("shortcuts"), font_size=9, height=32).pack(side="left")
        pill_button(action, "저장 설정", lambda: self.show_page("advanced"), font_size=9, height=32).pack(side="left", padx=8)
        pill_button(action, "최근 캡처 보기", lambda: self.show_page("recent"), font_size=9, height=32).pack(side="left")
        pill_button(action, "업데이트 확인", lambda: self.check_for_updates(manual=True), font_size=9, height=32).pack(side="left", padx=(0, 8))

    def check_for_updates(self, manual: bool = False):
        """GitHub의 최신 안정 릴리스를 백그라운드에서 확인한다."""
        def worker():
            try:
                release = fetch_latest_release(GITHUB_REPOSITORY, APP_VERSION)
            except UpdateCheckError as error:
                if manual:
                    self.root.after(0, lambda: messagebox.showwarning(APP_NAME, f"업데이트를 확인할 수 없습니다.\n{error}"))
                return
            self.root.after(0, lambda: self.show_update_result(release, manual))

        threading.Thread(target=worker, name="SerotoninUpdateCheck", daemon=True).start()

    def show_update_result(self, release, manual: bool):
        if release.is_newer:
            notes = release.notes.strip() or "새 버전의 변경 사항은 다운로드 페이지에서 확인할 수 있습니다."
            if len(notes) > 900:
                notes = notes[:897].rstrip() + "…"
            open_page = messagebox.askyesno(
                f"{APP_NAME} 업데이트",
                f"새 버전 {release.version}을 사용할 수 있습니다.\n\n{notes}\n\n다운로드 페이지를 열까요?",
            )
            if open_page:
                webbrowser.open(release.page_url or RELEASES_URL)
        elif manual:
            messagebox.showinfo(APP_NAME, f"현재 최신 버전({APP_VERSION})을 사용하고 있습니다.")

    def page_general(self):
        self.heading("기본 설정")
        self.check("show_overlay", "캡처 실행 시 화면 오버레이 표시")
        self.check("hide_capture_window", "캡처 실행창 숨김 (환경설정 창을 자동으로 감춥니다)")
        self.check("start_minimized", "Windows 로그인 후 숨김 상태로 시작")
        self.check("start_with_windows", "Windows 시작 시 자동 실행")
        self.separator(); self.heading("캡처 설정")
        self.check("show_result_window", "캡처 후 바로 편집 창 열기 (끄면 우하단 미리보기 카드)")
        self.check("copy_to_clipboard", "캡처한 내용을 항상 클립보드로 복사")
        self.check("show_save_notification", "캡처 이미지 저장완료 안내창 띄우기")
        self.check("include_cursor", "캡처할 때 마우스 커서 포함")
        self.separator(); self.heading("가이드라인 설정")
        row = ttk.Frame(self.page_holder); row.pack(anchor="w", pady=2)
        ttk.Label(row, text="표시선 색:").pack(side="left")
        guide = tk.StringVar(value=self.settings["guide_color"]); self.vars["guide_color"] = guide
        ttk.Combobox(row, textvariable=guide, values=("빨강", "초록", "파랑", "노랑"), state="readonly", width=13).pack(side="left", padx=10)
        self.check("keep_selection_guide", "캡처 이미지에 선택 영역 표시선 유지")

    def page_advanced(self):
        self.heading("이미지 저장 설정")
        grid = ttk.Frame(self.page_holder); grid.pack(anchor="w", fill="x"); grid.columnconfigure(1, weight=1)
        ttk.Label(grid, text="파일 포맷").grid(row=0, column=0, sticky="w", pady=5)
        fmt = tk.StringVar(value=self.settings["image_format"]); self.vars["image_format"] = fmt
        ttk.Combobox(grid, textvariable=fmt, values=("PNG", "JPG", "BMP", "GIF", "WEBP"), state="readonly", width=16).grid(row=0, column=1, sticky="w", padx=18)
        ttk.Label(grid, text="품질 (JPG/WEBP)").grid(row=0, column=2, sticky="w", padx=(40, 0))
        quality = tk.IntVar(value=int(self.settings["quality"])); self.vars["quality"] = quality
        ttk.Spinbox(grid, from_=1, to=100, textvariable=quality, width=8).grid(row=0, column=3, padx=10)
        ttk.Label(grid, text="파일명 형식").grid(row=1, column=0, sticky="w", pady=9)
        pattern = tk.StringVar(value=self.settings["filename_pattern"]); self.vars["filename_pattern"] = pattern
        ttk.Entry(grid, textvariable=pattern, width=42).grid(row=1, column=1, columnspan=3, sticky="ew", padx=18)
        ttk.Label(grid, text="{date}, {time}을 사용할 수 있습니다.", style="Hint.TLabel").grid(row=2, column=1, columnspan=3, sticky="w", padx=18)
        self.separator(); self.heading("자동저장 설정")
        auto = tk.BooleanVar(value=self.settings["auto_save"]); self.vars["auto_save"] = auto
        ttk.Checkbutton(self.page_holder, text="자동저장 설정 사용", variable=auto).pack(anchor="w", pady=3)
        folder_row = ttk.Frame(self.page_holder); folder_row.pack(fill="x", pady=(8, 2))
        ttk.Label(folder_row, text="저장위치").pack(side="left")
        folder = tk.StringVar(value=self.settings["save_folder"]); self.vars["save_folder"] = folder
        ttk.Entry(folder_row, textvariable=folder).pack(side="left", fill="x", expand=True, padx=12)
        ttk.Button(folder_row, text="…", style="Secondary.TButton", command=lambda: self.choose_folder(folder)).pack(side="right")
        self.separator(); self.heading("크기지정 캡처 프리셋", "자주 쓰는 크기를 최대 6개까지 등록할 수 있습니다.")
        preset_row = ttk.Frame(self.page_holder); preset_row.pack(fill="x")
        self.preset_list = tk.Listbox(preset_row, height=5, width=38, font=("맑은 고딕", 10), relief="solid", bd=1)
        for item in self.settings["size_presets"]: self.preset_list.insert("end", item)
        self.preset_list.pack(side="left")
        buttons = ttk.Frame(preset_row); buttons.pack(side="left", padx=12, anchor="n")
        ttk.Button(buttons, text="추가", style="Secondary.TButton", command=self.add_preset).pack(fill="x", pady=2)
        ttk.Button(buttons, text="삭제", style="Secondary.TButton", command=lambda: self.preset_list.delete("active")).pack(fill="x", pady=2)

    def page_shortcuts(self):
        self.heading("Print Screen 키 사용")
        enabled = tk.BooleanVar(value=self.settings["print_screen_enabled"]); self.vars["print_screen_enabled"] = enabled
        row = ttk.Frame(self.page_holder); row.pack(anchor="w")
        ttk.Checkbutton(row, text="PrintScreen 키를", variable=enabled).pack(side="left")
        action = tk.StringVar(value=self.settings["print_screen_action"]); self.vars["print_screen_action"] = action
        ttk.Combobox(row, textvariable=action, values=("직접 지정 캡처", "전체 캡처"), state="readonly", width=16).pack(side="left", padx=8)
        ttk.Label(row, text="기능으로 사용").pack(side="left")
        self.separator(); self.heading("캡처 단축키 설정", "직접 지정 캡처의 단축키는 전역으로 바로 적용됩니다.")
        hotkey = tk.StringVar(value=self.settings["hotkey"]); self.vars["hotkey"] = hotkey
        table = ttk.Frame(self.page_holder); table.pack(anchor="w")
        ttk.Label(table, text="기능", width=14).grid(row=0, column=0, sticky="w")
        ttk.Label(table, text="사용", width=8).grid(row=0, column=1); ttk.Label(table, text="단축키", width=24).grid(row=0, column=2)
        self.shortcut_vars = {}
        for index, name in enumerate(("직접지정", "창 캡처", "단위영역", "전체캡처", "스크롤캡처", "크기지정"), 1):
            ttk.Label(table, text=name).grid(row=index, column=0, sticky="w", pady=5)
            var = tk.BooleanVar(value=self.settings["shortcut_modes"].get(name, False)); self.shortcut_vars[name] = var
            ttk.Checkbutton(table, variable=var).grid(row=index, column=1)
            if name == "직접지정":
                entry = ttk.Entry(table, textvariable=hotkey, width=22); entry.grid(row=index, column=2, sticky="w"); entry.bind("<KeyPress>", self.record_shortcut)
                ttk.Label(table, text="입력 즉시 적용", style="Hint.TLabel").grid(row=index, column=3, padx=10, sticky="w")
            else:
                ttk.Label(table, text="추후 단축키 지원", style="Hint.TLabel").grid(row=index, column=2, sticky="w")

    def page_recent(self):
        self.heading("최근 캡처 목록")
        self.check("notify_on_clear", "목록 비우기 시 알림창 띄우기")
        self.check("notify_on_save_all", "목록 이미지 모두 저장 완료 안내창 띄우기")
        self.check("hide_recent_list", "목록 이미지 실제 사이즈로 숨김")
        self.check("delete_old_when_full", "최근 캡처 목록이 가득 찼을 경우, 오래 된 이미지 자동 삭제")
        self.separator()
        list_frame = ttk.Frame(self.page_holder); list_frame.pack(fill="both", expand=True)
        ttk.Label(list_frame, text=f"현재 최근 캡처: {len(self.settings['recent_captures'])}개 · 이미지를 클릭하면 원본을 엽니다.", style="Hint.TLabel").pack(anchor="w", pady=(0, 7))
        # Canvas 안에 타일 프레임을 넣어 많은 캡처도 스크롤하며 볼 수 있게 한다.
        gallery = tk.Frame(list_frame, bg="#f4f2ee", highlightbackground="#e7e3db", highlightthickness=1)
        gallery.pack(fill="both", expand=True)
        canvas = tk.Canvas(gallery, bg="#f4f2ee", highlightthickness=0)
        scrollbar = ttk.Scrollbar(gallery, orient="vertical", command=canvas.yview)
        self.tile_frame = tk.Frame(canvas, bg="#f4f2ee")
        self.tile_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.tile_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        # 저장된 경로가 있는 항목만 보이며, 새 캡처가 위로 오도록 정렬한다.
        self.recent_entries = list(reversed(self.settings["recent_captures"]))
        self.thumbnail_images = []  # PhotoImage가 가비지 컬렉션되지 않도록 참조를 유지한다.
        for index, entry in enumerate(self.recent_entries):
            self.add_capture_tile(index, entry)
        buttons = ttk.Frame(self.page_holder); buttons.pack(anchor="w", pady=10)
        ttk.Button(buttons, text="저장 폴더 열기", style="Secondary.TButton", command=self.open_save_folder).pack(side="left", padx=8)
        ttk.Button(buttons, text="최근 목록 비우기", style="Secondary.TButton", command=self.clear_recent).pack(side="left")

    def choose_folder(self, variable):
        selected = filedialog.askdirectory(title="캡처 이미지 저장 폴더 선택", initialdir=variable.get() or str(DOWNLOADS))
        if selected: variable.set(selected)

    def add_preset(self):
        value = simpledialog.askstring(APP_NAME, "크기를 입력하세요. 예: 1280 x 720")
        if value and len(self.preset_list.get(0, "end")) < 6: self.preset_list.insert("end", value)

    def clear_recent(self):
        if self.settings["notify_on_clear"] and not messagebox.askyesno(APP_NAME, "최근 캡처 목록을 비울까요?"): return
        self.settings["recent_captures"] = []; save_settings(self.settings); self.show_page("recent")

    def add_capture_tile(self, index, entry):
        """최근 저장 이미지를 150px 썸네일 타일로 그린다."""
        path = Path(entry.get("path", ""))
        tile = tk.Frame(self.tile_frame, bg="#ffffff", highlightbackground="#e7e3db", highlightthickness=1, width=156, height=166)
        tile.grid(row=index // 3, column=index % 3, padx=8, pady=8, sticky="n")
        tile.grid_propagate(False)
        try:
            with Image.open(path) as source:
                preview = source.convert("RGB").copy()
            preview.thumbnail((140, 104))
            photo = ImageTk.PhotoImage(preview)
            self.thumbnail_images.append(photo)
            image_label = tk.Label(tile, image=photo, bg="#ffffff", cursor="hand2")
            image_label.pack(padx=8, pady=(8, 4), fill="both", expand=True)
        except (OSError, ValueError):
            image_label = tk.Label(tile, text="이미지\n없음", bg="#eceae4", fg="#a8a5a0", cursor="hand2", font=("맑은 고딕", 10))
            image_label.pack(padx=8, pady=(8, 4), fill="both", expand=True)
        filename = path.name if path.name else "클립보드 캡처"
        timestamp = entry.get("created", "").replace("T", " ")[:16]
        caption = tk.Label(tile, text=f"{filename[:20]}\n{timestamp}", bg="#ffffff", fg="#57554f", justify="left", anchor="w", cursor="hand2", font=("맑은 고딕", 8))
        caption.pack(fill="x", padx=8, pady=(0, 7))
        for widget in (tile, image_label, caption):
            widget.bind("<Double-Button-1>", lambda _event, idx=index: self.open_capture(idx))

    def open_capture(self, index):
        path = Path(self.recent_entries[index].get("path", ""))
        if not path.exists():
            messagebox.showwarning(APP_NAME, "저장 파일을 찾을 수 없습니다. 파일이 이동되었거나 자동 저장이 꺼진 캡처입니다.")
            return
        os.startfile(str(path))

    def open_save_folder(self):
        folder = Path(self.settings["save_folder"]).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def collect_current_page(self):
        """화면 이동 시에도 이전 탭에서 바꾼 값을 잃지 않는다."""
        for key, variable in self.vars.items():
            self.settings[key] = variable.get()
        if self.current_page == "shortcuts":
            self.settings["shortcut_modes"] = {key: var.get() for key, var in self.shortcut_vars.items()}
        if self.current_page == "advanced":
            self.settings["size_presets"] = list(self.preset_list.get(0, "end"))

    def record_shortcut(self, event):
        if event.keysym in {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Win_L", "Win_R"}: return "break"
        pieces = []
        # Tk의 event.state에는 Num Lock 등의 상태 비트도 섞일 수 있다.
        # Windows가 보고하는 실제 modifier 키 상태를 사용해야 Alt가 잘못 붙지 않는다.
        pressed = ctypes.windll.user32.GetAsyncKeyState
        if pressed(0x11) & 0x8000: pieces.append("Ctrl")       # VK_CONTROL
        if pressed(0x10) & 0x8000: pieces.append("Shift")      # VK_SHIFT
        if pressed(0x12) & 0x8000: pieces.append("Alt")        # VK_MENU
        if (pressed(0x5B) & 0x8000) or (pressed(0x5C) & 0x8000): pieces.append("Win")
        if pieces and len(event.keysym) <= 12:
            self.vars["hotkey"].set("+".join(pieces + [event.keysym.upper()]))
            # 키를 놓은 뒤 등록해야 방금 누른 조합이 곧바로 캡처를 실행하지 않는다.
            self.root.after(180, self.apply_hotkey_immediately)
        return "break"

    def apply_hotkey_immediately(self):
        """단축키 탭에서는 확인/재시작 없이 새 전역 단축키를 적용한다."""
        hotkey = self.vars.get("hotkey", tk.StringVar(value=self.settings["hotkey"])).get().strip()
        if self.register_hotkey(hotkey):
            self.settings["hotkey"] = hotkey
            save_settings(self.settings)
            self.toast("단축키 적용", f"{hotkey}로 바로 캡처할 수 있습니다.")

    def register_hotkey(self, hotkey: str) -> bool:
        success, reason = self.hotkey_listener.configure(hotkey)
        if not success:
            self.status(reason)
        return success

    def poll_hotkeys(self):
        while True:
            try:
                self.capture_events.get_nowait()
            except queue.Empty:
                break
            self.start_capture()
        # 트레이 메뉴는 별도 스레드에서 동작하므로, 명령을 큐로 받아 메인 스레드에서 처리한다.
        while True:
            try:
                command = self.tray_commands.get_nowait()
            except queue.Empty:
                break
            self.handle_tray_command(command)
        self.root.after(80, self.poll_hotkeys)

    def start_tray(self):
        """작업표시줄 트레이에 아이콘과 메뉴를 띄운다(pystray가 있을 때만)."""
        if not HAS_TRAY:
            return
        menu = pystray.Menu(
            pystray.MenuItem("설정 열기", lambda icon, item: self.tray_commands.put("show"), default=True),
            pystray.MenuItem("영역 캡처", lambda icon, item: self.tray_commands.put("capture")),
            pystray.MenuItem("창 캡처", lambda icon, item: self.tray_commands.put("capture_window")),
            pystray.MenuItem("스텝 캡처", lambda icon, item: self.tray_commands.put("steps")),
            pystray.MenuItem("종료", lambda icon, item: self.tray_commands.put("quit")),
        )
        self.tray_icon = pystray.Icon("NoAdsCapture", tray_image(), APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, name="HwpCaptureTray", daemon=True).start()

    def handle_tray_command(self, command):
        if command == "show":
            self.root.deiconify(); self.root.lift(); self.root.focus_force(); self.show_page("home")
        elif command == "capture":
            self.start_capture()
        elif command == "capture_window":
            self.start_window_capture()
        elif command == "steps":
            self.start_step_capture()
        elif command == "quit":
            self.quit_app()

    def quit_app(self):
        """트레이 '종료'로 프로그램을 완전히 끝낸다."""
        if self.tray_icon is not None:
            self.tray_icon.stop()
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except OSError:
            pass
        self.root.quit(); self.root.destroy()

    def start_capture(self):
        if self.settings["hide_capture_window"]: self.root.withdraw()
        self.root.after(130, lambda: ScreenSelector(self))

    def start_window_capture(self):
        """마우스 아래 창을 자동 인식해 클릭 한 번으로 캡처한다."""
        if self.settings["hide_capture_window"]: self.root.withdraw()
        self.root.after(150, lambda: WindowPicker(self))

    def start_step_capture(self):
        """클릭마다 자동 캡처해 단계별 매뉴얼을 만드는 스텝 캡처를 시작한다."""
        if getattr(self, "step_session", None) is not None:
            return
        self.step_session = StepCaptureSession(self)

    def open_editor(self):
        """좌측 '이미지 편집' 탭: 빈 편집 창을 바로 연다. 이미지는 편집 창 안의 '이미지 열기'로 불러온다."""
        CaptureEditor(self, Image.new("RGB", (900, 600), "#ffffff"))

    def capture(self, bbox):
        # --noconsole로 빌드하면 예외가 보일 콘솔이 없으므로, 실패를 직접 사용자에게 알린다.
        try:
            image = ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception as error:
            self.status(f"화면을 캡처하지 못했습니다.\n{error}")
            return
        # 캡처 직후 원본을 클립보드에 넣어 HWP에서 곧바로 Ctrl+V 할 수 있게 한다.
        if self.settings["copy_to_clipboard"]:
            try:
                self.copy_image(image)
            except OSError as error:
                # 클립보드 복사가 실패해도 저장은 이어가고, 알림만 띄운다.
                self.toast("클립보드 복사 실패", str(error))
        # 자동 저장이 켜져 있으면 결과창을 열기 전에 먼저 저장한다.
        # 따라서 편집을 마치지 않아도 다운로드 폴더에 원본 캡처가 남는다.
        try:
            auto_saved_path = self.save_image(image) if self.settings["auto_save"] else None
        except OSError as error:
            self.status(f"이미지를 저장하지 못했습니다.\n{error}")
            auto_saved_path = None
        if auto_saved_path:
            self.record_capture(auto_saved_path)
        # 기본 흐름은 CleanShot처럼 우하단 미리보기 카드. 설정을 켜면 예전처럼 편집 창을 바로 연다.
        if self.settings["show_result_window"]:
            CaptureEditor(self, image, auto_saved_path)
        else:
            FloatingThumbnail(self, image, auto_saved_path)

    def record_capture(self, file_path: Path | None):
        self.settings["recent_captures"].append({"path": str(file_path) if file_path else "", "created": datetime.now().isoformat()})
        # 자동 정리가 켜지면 30개, 꺼져 있어도 설정 파일이 비대해지지 않게 200개로 상한을 둔다.
        limit = 30 if self.settings["delete_old_when_full"] else 200
        if len(self.settings["recent_captures"]) > limit:
            self.settings["recent_captures"] = self.settings["recent_captures"][-limit:]
        save_settings(self.settings)

    def save_image(self, image, image_format: str | None = None, quality: int | None = None) -> Path:
        folder = Path(self.settings["save_folder"]).expanduser(); folder.mkdir(parents=True, exist_ok=True)
        fmt = (image_format or self.settings["image_format"]).upper(); extension = {"JPG": "jpg", "JPEG": "jpg"}.get(fmt, fmt.lower())
        # 편집 창의 '용량 맞추기'가 정한 품질이 있으면 환경설정 품질보다 우선한다.
        save_quality = quality if quality is not None else self.settings["quality"]
        stamp = {"date": datetime.now().strftime("%Y%m%d"), "time": datetime.now().strftime("%H%M%S_%f")}
        try:
            name = self.settings["filename_pattern"].format(**stamp)
        except (KeyError, IndexError, ValueError):
            # 사용자가 {date}/{time} 외의 중괄호를 넣어도 저장이 실패하지 않게 기본 형식으로 대체한다.
            name = DEFAULTS["filename_pattern"].format(**stamp)
        path = folder / f"{name}.{extension}"; counter = 2
        while path.exists(): path = folder / f"{name}_{counter}.{extension}"; counter += 1
        if fmt == "JPG": image.convert("RGB").save(path, "JPEG", quality=save_quality, optimize=True)
        elif fmt == "WEBP": image.save(path, "WEBP", quality=save_quality)
        elif fmt == "GIF": image.convert("P", palette=Image.Palette.ADAPTIVE).save(path, "GIF")
        else: image.save(path, fmt)
        return path

    def copy_image(self, image):
        buffer = io.BytesIO(); image.convert("RGB").save(buffer, "BMP"); data = buffer.getvalue()[14:]
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        # 기본 ctypes 반환형은 c_int라서 64비트 포인터 주소가 잘린다. WinAPI 메모리 핸들은 포인터로 명시한다.
        kernel32.GlobalAlloc.argtypes = (ctypes.c_uint, ctypes.c_size_t)
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = (ctypes.c_void_p,)
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
        kernel32.GlobalFree.argtypes = (ctypes.c_void_p,)
        kernel32.GlobalFree.restype = ctypes.c_void_p
        handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        pointer = kernel32.GlobalLock(handle)
        if not handle or not pointer:
            raise OSError("클립보드용 메모리를 만들 수 없습니다.")
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData.argtypes = (ctypes.c_uint, ctypes.c_void_p)
        user32.SetClipboardData.restype = ctypes.c_void_p
        # 다른 앱이 클립보드를 잠깐 쥐고 있을 수 있으므로 짧게 재시도한다.
        if not any(user32.OpenClipboard(None) or time.sleep(0.03) for _ in range(10)):
            kernel32.GlobalFree(handle)  # 클립보드에 넘기지 못한 메모리는 직접 해제한다.
            raise OSError("다른 프로그램이 클립보드를 사용 중입니다.")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(8, handle):
                # SetClipboardData가 실패하면 핸들 소유권이 넘어가지 않으므로 해제한다.
                kernel32.GlobalFree(handle)
                raise OSError("이미지를 클립보드에 복사할 수 없습니다.")
        finally:
            user32.CloseClipboard()

    def toast(self, title, body):
        bg = "#0f172a"
        notice = tk.Toplevel(self.root); notice.overrideredirect(True); notice.attributes("-topmost", True); notice.configure(bg=bg)
        try: notice.attributes("-alpha", 0.97)
        except tk.TclError: pass
        tk.Frame(notice, bg=self.BLUE, width=4).pack(side="left", fill="y")
        text_box = tk.Frame(notice, bg=bg); text_box.pack(side="left", fill="both", expand=True)
        tk.Label(text_box, text=title, bg=bg, fg="white", font=("맑은 고딕", 10, "bold")).pack(anchor="w", padx=18, pady=(13, 0))
        tk.Label(text_box, text=body, bg=bg, fg="#cbd5e1", justify="left", wraplength=300, font=("맑은 고딕", 9)).pack(anchor="w", padx=18, pady=(3, 13))
        notice.update_idletasks(); notice.geometry(f"340x{notice.winfo_height()}+{notice.winfo_screenwidth()-360}+60"); notice.after(2800, notice.destroy)

    def apply_settings(self):
        self.collect_current_page()
        if not self.register_hotkey(self.settings["hotkey"]): return
        try:
            self.settings["quality"] = max(1, min(100, int(self.settings["quality"])))
            set_startup(self.settings["start_with_windows"], self.settings["start_minimized"])
            save_settings(self.settings); self.toast("설정 저장 완료", "변경한 환경설정을 적용했습니다.")
        except (OSError, ValueError) as error: messagebox.showerror(APP_NAME, f"설정을 저장할 수 없습니다.\n{error}")

    def restore_defaults(self):
        if messagebox.askyesno(APP_NAME, "현재 페이지의 설정을 기본값으로 되돌릴까요?"):
            for key in self.vars:
                if key in DEFAULTS: self.settings[key] = DEFAULTS[key]
            # show_page가 화면의 (아직 옛 값인) 위젯 값을 다시 수집해 방금 되돌린
            # 기본값을 덮어쓰지 않도록, 수집 없이 페이지를 다시 그린다.
            page, self.current_page = self.current_page, None
            self.show_page(page)

    def status(self, text):
        # 환경설정이 숨겨진 상태에서도 실패 원인을 확인할 수 있게 창을 다시 보인다.
        self.root.deiconify(); self.root.lift(); messagebox.showwarning(APP_NAME, text)

    def hide(self):
        self.root.withdraw()
        # 창을 닫아도 종료가 아니라 트레이로 숨는다는 사실을 처음 한 번 알려준다.
        if self.tray_icon is not None and not self._hide_hinted:
            self._hide_hinted = True
            self.toast("트레이에서 계속 실행 중", "단축키로 캡처할 수 있고, 트레이 아이콘에서 종료할 수 있습니다.")

    def run(self): self.root.mainloop()

