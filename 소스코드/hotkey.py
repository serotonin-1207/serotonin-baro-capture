"""Windows 메시지로 영역 캡처 단축키를 전달한다."""
import ctypes
import threading
from ctypes import wintypes

from config import DEFAULT_CAPTURE_SHORTCUT, parse_hotkey


class GlobalHotkeyListener(threading.Thread):
    def __init__(self, events, shortcut, *, fallback=True):
        super().__init__(name="CaptureHotkeys", daemon=True)
        self.events = events
        self.shortcuts = (shortcut,)
        if fallback and shortcut != DEFAULT_CAPTURE_SHORTCUT:
            self.shortcuts += (DEFAULT_CAPTURE_SHORTCUT,)
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.label = None
        self.thread_id = None

    def run(self):
        user32 = ctypes.windll.user32
        message = wintypes.MSG()
        hotkey_id = 1024
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        try:
            for label in self.shortcuts:
                try:
                    flags, key = parse_hotkey(label)
                except ValueError:
                    continue
                if user32.RegisterHotKey(None, hotkey_id, flags | 0x4000, key):
                    self.label = label
                    break
            self.ready.set()
            if not self.label:
                return
            while not self.stopping.is_set() and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312 and message.wParam == hotkey_id:
                    self.events.put("capture")
        finally:
            self.ready.set()
            if self.label:
                user32.UnregisterHotKey(None, hotkey_id)

    def stop(self):
        self.stopping.set()
        if self.is_alive() and self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
