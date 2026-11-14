"""영역 캡처, 최근 목록, 설정을 여는 패널."""
import ctypes
import os
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageTk

from config import APP_NAME, AUTHOR_EMAIL, format_hotkey, load_capture_shortcut

BG = "#aecfdf"
HEADER = "#5897b6"
PALE = "#cfe4ee"
INK = "#13354b"
MUTED = "#284e65"
ACCENT = "#24658a"
FONT = "맑은 고딕"


def shortcut_from_keypress(event):
    key = event.keycode
    if not (0x30 <= key <= 0x39 or 0x41 <= key <= 0x5A or 0x70 <= key <= 0x7B):
        return None
    flags = 0
    if event.state & 0x0004:
        flags |= 2
    if event.state & 0x0001:
        flags |= 4
    get_key_state = ctypes.windll.user32.GetKeyState
    if get_key_state(0x12) & 0x8000:
        flags |= 1
    if (get_key_state(0x5B) | get_key_state(0x5C)) & 0x8000:
        flags |= 8
    return format_hotkey(flags, key) if flags else None


def rounded(canvas, box, radius, color):
    x1, y1, x2, y2 = box
    r = radius
    points = (x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
              x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1)
    return canvas.create_polygon(points, smooth=True, splinesteps=16, fill=color)


class Capsule(tk.Canvas):
    def __init__(self, parent, text, action, width, height, *, primary=False):
        super().__init__(parent, width=width, height=height, bg=BG, highlightthickness=0,
                         takefocus=True, cursor="hand2")
        self.action = action
        self.enabled = True
        self.fill = ACCENT if primary else PALE
        self.hover = "#1c5375" if primary else "#e4f1f7"
        self.ink = "white" if primary else INK
        self.shape = rounded(self, (1, 1, width-1, height-1), height//2, self.fill)
        self.label = self.create_text(width//2, height//2, text=text, font=(FONT, 10, "bold"),
                                      fill=self.ink)
        self.bind("<Enter>", lambda event: self.highlight(True))
        self.bind("<Leave>", lambda event: self.highlight(False))
        self.bind("<FocusIn>", lambda event: self.highlight(True))
        self.bind("<FocusOut>", lambda event: self.highlight(False))
        self.bind("<ButtonRelease-1>", self.click)
        self.bind("<Return>", self.invoke)
        self.bind("<space>", self.invoke)

    def highlight(self, active):
        if self.enabled:
            self.itemconfigure(self.shape, fill=self.hover if active else self.fill,
                               outline=INK if self.focus_get() == self else "")

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "", takefocus=enabled)
        self.itemconfigure(self.shape, fill=self.fill if enabled else "#a1bdcc", outline="")
        self.itemconfigure(self.label, fill=self.ink if enabled else MUTED)

    def click(self, event):
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            return self.invoke()

    def invoke(self, event=None):
        if self.enabled:
            self.action()
        return "break"


class HistoryWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.withdraw()
        self.app = app
        self.hwnd = None
        self.photo = None
        self.settings_page = None
        self.title(f"{APP_NAME} · 최근 캡처")
        self.overrideredirect(True)
        self.attributes("-alpha", 0.93)
        self.configure(bg=BG)
        scale = float(self.tk.call("tk", "scaling")) / (4 / 3)

        def px(value):
            return round(value * scale)

        self.px = px
        self.width, self.height = px(540), px(350)
        self.preview_size = (px(324), px(177))
        x = max(12, self.winfo_screenwidth() - self.width - px(30))
        self.geometry(f"{self.width}x{self.height}+{x}+{px(60)}")
        header = tk.Canvas(self, bg=HEADER, highlightthickness=0, height=px(48))
        header.pack(fill="x")
        rounded(header, (px(14), px(8), px(237), px(59)), px(12), BG)
        header.create_text(self.width-px(24), px(24), text="×", fill="#f3fbff", font=(FONT, 18), tags="close")
        header.tag_bind("close", "<ButtonRelease-1>", self.close)
        header.bind("<ButtonPress-1>", self.drag_start)
        header.bind("<B1-Motion>", self.drag)
        self.header = header
        self.header_title = header.create_text(px(27), px(27), text=APP_NAME, fill=INK,
                                               font=(FONT, 12, "bold"), anchor="w")
        self.history_page = tk.Frame(self, bg=BG)
        self.history_page.pack(fill="both", expand=True)
        toolbar = tk.Frame(self.history_page, bg=BG)
        toolbar.pack(fill="x", padx=px(14), pady=(px(7), px(8)))
        self.capture_button = Capsule(toolbar, "", self.app.start_capture, self.width-px(101), px(32))
        self.capture_button.pack(side="left", fill="x", expand=True)
        self.settings_button = Capsule(toolbar, "설정", self.show_settings, px(64), px(32))
        self.settings_button.pack(side="right", padx=(px(9), 0))
        self.update_release_button()
        self.update_capture_label()

        body = tk.Frame(self.history_page, bg=BG)
        body.pack(fill="both", expand=True, padx=px(14))
        title = tk.Frame(body, bg=BG)
        title.pack(fill="x", pady=(0, px(5)))
        tk.Label(title, text="최근 캡처", font=(FONT, 11, "bold"), bg=BG, fg=INK).pack(side="left")
        self.clear_button = Capsule(title, "전체 삭제", self.clear_history, px(84), px(24))
        self.clear_button.pack(side="right")

        footer = tk.Frame(body, bg=BG)
        footer.pack(side="bottom", fill="x", pady=px(9))
        tk.Label(footer, text="최대 10장 · 실행 중에만 보관", font=(FONT, 9), fg=MUTED, bg=BG).pack(side="left")
        self.copy_button = Capsule(footer, "다시 복사", self.copy_selected, px(104), px(30), primary=True)
        self.copy_button.pack(side="right")
        self.delete_button = Capsule(footer, "삭제", self.delete_selected, px(60), px(30))
        self.delete_button.pack(side="right", padx=(0, px(7)))

        content = tk.Frame(body, bg=BG)
        content.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(content, width=18, bg=PALE, fg=INK, font=(FONT, 9),
                                  relief="flat", bd=0, highlightthickness=1, highlightbackground="#b8d5e5",
                                  highlightcolor=ACCENT, exportselection=False, activestyle="none",
                                  selectbackground=ACCENT, selectforeground="white")
        self.listbox.pack(side="left", fill="y", padx=(0, px(8)))
        self.listbox.bind("<<ListboxSelect>>", self.select)
        self.listbox.bind("<Double-Button-1>", self.copy_selected)
        self.preview = tk.Label(content, bg=PALE, fg=MUTED, font=(FONT, 10), anchor="center")
        self.preview.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Return>", self.copy_selected)
        self.bind("<Escape>", self.escape)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.radius = px(14)

    def drag_start(self, event):
        self.drag_offset = (event.x_root-self.winfo_x(), event.y_root-self.winfo_y())

    def drag(self, event):
        x, y = self.drag_offset
        self.geometry(f"+{event.x_root-x}+{event.y_root-y}")

    def round_window(self):
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user32.GetAncestor.restype = wintypes.HWND
        user32.SetWindowRgn.argtypes = (wintypes.HWND, wintypes.HRGN, wintypes.BOOL)
        gdi32.CreateRoundRectRgn.argtypes = (ctypes.c_int,) * 6
        gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
        gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
        self.hwnd = user32.GetAncestor(self.winfo_id(), 2)
        region = gdi32.CreateRoundRectRgn(0, 0, self.width+1, self.height+1, self.radius*2, self.radius*2)
        if region and not user32.SetWindowRgn(self.hwnd, region, True):
            gdi32.DeleteObject(region)

    def refresh_history(self, index=0):
        self.listbox.delete(0, "end")
        records = self.app.history.items
        for record in records:
            width, height = record.image.size
            self.listbox.insert("end", f"{record.created:%H:%M:%S}   {width}×{height}")
        self.clear_button.set_enabled(bool(records))
        if records:
            index = min(index, len(records) - 1)
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)
        self.select()

    def show(self):
        self.refresh_history()
        self.deiconify()
        self.update_idletasks()
        if self.hwnd is None:
            self.round_window()
        self.lift()
        self.focus_force()
        if self.settings_page is None:
            self.listbox.focus_set()
        else:
            self.shortcut_entry.focus_set()

    def select(self, event=None):
        selected = self.listbox.curselection()
        self.copy_button.set_enabled(bool(selected))
        self.delete_button.set_enabled(bool(selected))
        if not selected:
            self.preview.configure(image="", text="영역을 캡처하면 여기에 표시됩니다.")
            self.photo = None
            return
        image = self.app.history.items[selected[0]].image
        width, height = image.size
        pw, ph = self.preview_size
        ratio = min(1.0, pw/width, ph/height)
        if ratio < 1:
            image = image.resize((max(1, round(width*ratio)), max(1, round(height*ratio))), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.preview.configure(image=self.photo, text="")

    def delete_selected(self):
        selected = self.listbox.curselection()
        if selected:
            index = selected[0]
            del self.app.history.items[index]
            self.refresh_history(index)
            self.listbox.focus_set()

    def clear_history(self):
        self.app.confirming_clear = True
        try:
            confirmed = messagebox.askyesno(APP_NAME, "최근 캡처를 모두 지울까요?", parent=self)
        finally:
            self.app.confirming_clear = False
        if confirmed:
            self.app.history.items.clear()
            self.refresh_history()
        self.listbox.focus_set()

    def update_capture_label(self):
        shortcut = self.app.hotkeys.label or "단축키 미등록"
        self.capture_button.itemconfigure(self.capture_button.label, text=f"영역 캡처    {shortcut}")

    def update_release_button(self):
        label = "설정 •" if self.app.pending_update else "설정"
        self.settings_button.itemconfigure(self.settings_button.label, text=label)
        if self.settings_page is not None:
            label = "새 버전 보기" if self.app.pending_update else "업데이트 확인"
            self.release_button.itemconfigure(self.release_button.label, text=label)

    def show_settings(self):
        px = self.px
        self.history_page.pack_forget()
        self.header.itemconfigure(self.header_title, text="설정")
        self.settings_page = content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=px(14), pady=(px(14), px(9)))

        tk.Label(content, text="영역 캡처 단축키", bg=BG, fg=INK,
                 font=(FONT, 11, "bold")).pack(anchor="w")
        shortcut = tk.StringVar(master=self, value=self.app.hotkeys.label or load_capture_shortcut())
        entry = self.shortcut_entry = tk.Entry(
            content, textvariable=shortcut, state="readonly", readonlybackground=PALE,
            fg=INK, font=(FONT, 11),
            relief="flat", highlightthickness=1, highlightbackground="#b8d5e5",
            highlightcolor=ACCENT,
        )
        entry.pack(fill="x", ipady=px(5), pady=(px(6), px(4)))
        tk.Label(content, text="사용할 키 조합을 누르세요. 예: Ctrl+Shift+A", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w")
        error_label = tk.Label(content, bg=BG, fg="#87252c", font=(FONT, 9),
                               wraplength=self.width-px(32), justify="left")
        error_label.pack(anchor="w", pady=(px(4), 0))

        def open_licenses():
            try:
                os.startfile(Path(__file__).resolve().with_name("licenses"))
            except OSError:
                error_label.configure(text="라이선스 고지 폴더를 열 수 없습니다.")

        tools = tk.Frame(content, bg=BG)
        tools.pack(anchor="w", pady=(px(8), 0))
        Capsule(tools, "라이선스 고지", open_licenses, px(122), px(30)).pack(side="left")
        self.release_button = Capsule(tools, "", self.check_release, px(122), px(30))
        self.release_button.pack(side="left", padx=(px(8), 0))
        self.update_release_button()

        def save(event=None):
            try:
                self.app.change_capture_shortcut(shortcut.get())
            except ValueError as error:
                error_label.configure(text=str(error))
            except OSError:
                error_label.configure(text="설정을 저장할 수 없습니다.")
            else:
                self.update_capture_label()
                self.close_settings()
            return "break"

        def record(event):
            if event.keysym in ("Tab", "ISO_Left_Tab", "Escape"):
                return None
            value = shortcut_from_keypress(event)
            if value:
                shortcut.set(value)
                error_label.configure(text="")
            return "break"

        buttons = tk.Frame(content, bg=BG)
        buttons.pack(side="bottom", fill="x")
        tk.Label(buttons, text=f"제작 문의  {AUTHOR_EMAIL}", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left")
        Capsule(buttons, "저장", save, px(88), px(30), primary=True).pack(side="right")
        Capsule(buttons, "취소", self.close_settings, px(72), px(30)).pack(
            side="right", padx=(0, px(7))
        )
        entry.bind("<KeyPress>", record)
        entry.bind("<Return>", save)
        entry.bind("<KP_Enter>", save)
        entry.focus_set()

    def check_release(self):
        if self.app.pending_update:
            self.app.show_update()
        else:
            self.app.check_update(manual=True)

    def close_settings(self):
        self.settings_page.destroy()
        self.settings_page = None
        self.header.itemconfigure(self.header_title, text=APP_NAME)
        self.history_page.pack(fill="both", expand=True)
        self.listbox.focus_set()

    def escape(self, event=None):
        if self.settings_page is not None:
            self.close_settings()
            return "break"
        return self.close()

    def copy_selected(self, event=None):
        selected = self.listbox.curselection()
        if selected:
            self.app.copy_recent(selected[0])
        return "break"

    def hide(self):
        self.withdraw()
        self.preview.configure(image="")
        self.photo = None

    def close(self, event=None):
        if self.app.tray is None:
            self.app.quit_app()
        else:
            self.hide()
            self.app.restore_focus()
        return "break"
