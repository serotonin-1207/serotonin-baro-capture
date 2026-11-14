"""영역 캡처와 최근 캡처의 실행 경로."""
import ctypes
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

from clipboard import copy_image
from config import APP_NAME, format_hotkey, load_capture_shortcut, parse_hotkey, save_capture_shortcut
from events import MainThreadEvents
from history import CaptureHistory
from hotkey import GlobalHotkeyListener
from selector import ScreenSelector
from snapshot import ScreenSnapshot
from tray import CaptureTray
from update_checker import fetch_update


class CaptureApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.history = CaptureHistory()
        self.panel = None
        self.preview = None
        self.tray = None
        self.selecting = False
        self.confirming_clear = False
        self.closing = False
        self.return_focus = None
        self.update_worker = None
        self.manual_update = False
        self.pending_update = None
        self.user32 = ctypes.windll.user32
        self.user32.GetForegroundWindow.restype = ctypes.c_void_p
        self.user32.IsWindow.argtypes = (ctypes.c_void_p,)
        self.user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
        self.events = MainThreadEvents(self.root, self.handle_event)
        self.hotkeys = GlobalHotkeyListener(self.events, load_capture_shortcut())
        self.hotkeys.start()
        self.hotkeys.ready.wait(1)
        self.start_tray()
        if "--minimized" not in sys.argv or self.tray is None:
            self.root.after_idle(self.show_history)
        self.root.after(1200, self.check_update)

    def start_tray(self):
        tray = CaptureTray(self.events)
        tray.start()
        self.tray = tray
        if not tray.ready.wait(1) or not tray.available:
            tray.stop()
            self.tray = None

    def handle_event(self, action):
        if isinstance(action, tuple):
            self.update_checked(*action)
        elif action == "capture":
            self.start_capture()
        elif action == "history":
            self.show_history()
        elif action == "quit":
            self.quit_app()

    def check_update(self, manual=False):
        self.manual_update |= manual
        if self.update_worker is not None:
            return

        def lookup():
            try:
                result = fetch_update()
            except (OSError, ValueError, KeyError, TypeError):
                self.events.put((None, True))
            else:
                self.events.put((result, False))

        self.update_worker = threading.Thread(target=lookup, name="ReleaseCheck", daemon=True)
        self.update_worker.start()

    def update_checked(self, result, failed):
        self.update_worker = None
        manual, self.manual_update = self.manual_update, False
        if result:
            self.pending_update = result
            if manual:
                self.show_update()
            elif self.panel is not None:
                self.panel.update_release_button()
        elif manual:
            message = "업데이트 정보를 확인할 수 없습니다." if failed else "최신 버전을 사용 중입니다."
            messagebox.showinfo(APP_NAME, message, parent=self.panel or self.root)

    def show_update(self):
        version, page, notes = self.pending_update
        message = f"{version} 버전을 사용할 수 있습니다."
        if notes:
            message += "\n\n" + notes[:550]
        message += "\n\n릴리스 페이지를 열까요?"
        if messagebox.askyesno(APP_NAME, message, parent=self.panel or self.root):
            webbrowser.open(page)

    def show_history(self):
        if self.selecting or self.confirming_clear:
            return
        self.close_preview()
        if self.panel is None:
            from history_view import HistoryWindow
            self.panel = HistoryWindow(self)
        if not self.panel.winfo_viewable():
            self.return_focus = self.user32.GetForegroundWindow()
        self.panel.show()

    def start_capture(self):
        if self.selecting or self.confirming_clear:
            return
        self.selecting = True
        foreground = self.user32.GetForegroundWindow()
        panel_visible = self.panel is not None and self.panel.winfo_viewable()
        settings_visible = panel_visible and self.panel.settings_page is not None
        focus_after_capture = foreground if settings_visible and foreground == self.panel.hwnd else None
        if not panel_visible or foreground != self.panel.hwnd:
            self.return_focus = foreground
        hide_panel = panel_visible and not settings_visible
        if hide_panel:
            self.panel.hide()
        preview_visible = self.close_preview()
        if hide_panel or preview_visible:
            self.root.after_idle(lambda: self.prepare_capture(flush=True, focus_after_capture=focus_after_capture))
        else:
            self.prepare_capture(focus_after_capture=focus_after_capture)

    def prepare_capture(self, flush=False, focus_after_capture=None):
        def closed():
            self.selection_closed(focus_after_capture)

        try:
            if flush:
                ctypes.windll.dwmapi.DwmFlush()
            snapshot = ScreenSnapshot.grab()
            ScreenSelector(self.root, snapshot, self.capture, closed)
        except (OSError, tk.TclError) as error:
            closed()
            self.status(f"화면을 캡처하지 못했습니다.\n{error}")

    def selection_closed(self, focus_after_capture=None):
        self.selecting = False
        self.restore_focus(focus_after_capture)

    def restore_focus(self, window=None):
        window = window or self.return_focus
        if not self.closing and window and self.user32.IsWindow(window):
            self.user32.SetForegroundWindow(window)

    def capture(self, snapshot, bbox):
        try:
            image = snapshot.crop(bbox)
        except ValueError as error:
            self.status(str(error))
            return
        self.history.add(image)
        if self.copy(image):
            self.show_preview(image, bbox)

    def show_preview(self, image, bbox):
        from preview import CapturePreview

        self.close_preview()
        self.preview = CapturePreview(self.root, image, bbox)

    def close_preview(self):
        preview, self.preview = self.preview, None
        if preview is not None and preview.winfo_exists():
            preview.destroy()
            return True
        return False

    def copy(self, image):
        try:
            copy_image(image, self.root.winfo_id())
            return True
        except OSError as error:
            self.status(str(error))
            return False

    def copy_recent(self, index):
        if self.copy(self.history.items[index].image):
            self.panel.hide()
            self.restore_focus()

    def change_capture_shortcut(self, shortcut):
        flags, key = parse_hotkey(shortcut)
        shortcut = format_hotkey(flags, key)
        if self.hotkeys.label and parse_hotkey(self.hotkeys.label) == (flags, key):
            save_capture_shortcut(shortcut)
            self.hotkeys.label = shortcut
            return

        listener = GlobalHotkeyListener(self.events, shortcut, fallback=False)
        listener.start()
        if not listener.ready.wait(1) or not listener.label:
            listener.stop()
            raise ValueError("이 단축키를 등록할 수 없습니다. 다른 조합을 입력해 주세요.")
        try:
            save_capture_shortcut(shortcut)
        except OSError:
            listener.stop()
            raise
        previous = self.hotkeys
        self.hotkeys = listener
        previous.stop()

    def status(self, message):
        messagebox.showwarning(APP_NAME, message, parent=self.root)

    def quit_app(self):
        self.closing = True
        self.events.close()
        self.hotkeys.stop()
        if self.tray is not None:
            self.tray.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
