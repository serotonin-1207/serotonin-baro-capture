from __future__ import annotations

import ctypes
import queue
import threading

from config import HOTKEY_ID, WM_HOTKEY, WM_HOTKEY_RECONFIGURE, parse_hotkey


class GlobalHotkeyListener(threading.Thread):
    """Tkinter 메시지 루프와 분리해 Windows 전역 단축키를 확실하게 수신한다."""
    daemon = True

    def __init__(self, capture_events: queue.Queue):
        super().__init__(name="HwpCaptureHotkey")
        self.capture_events = capture_events
        self.ready = threading.Event()
        self.thread_id = None
        self.active_hotkey = None
        self._lock = threading.Lock()
        self._request = None

    @staticmethod
    def _message_type():
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class MSG(ctypes.Structure):
            _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_size_t),
                        ("lParam", ctypes.c_ssize_t), ("time", ctypes.c_uint), ("pt", POINT), ("lPrivate", ctypes.c_uint)]
        return MSG

    def configure(self, hotkey: str) -> tuple[bool, str]:
        request = {"hotkey": hotkey, "done": threading.Event(), "result": (False, "단축키 감시기를 시작하지 못했습니다.")}
        with self._lock:
            self._request = request
        ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_HOTKEY_RECONFIGURE, 0, 0)
        request["done"].wait(1.5)
        return request["result"]

    def _apply_request(self):
        with self._lock:
            request, self._request = self._request, None
        if not request:
            return
        try:
            modifiers, key = parse_hotkey(request["hotkey"])
        except ValueError as error:
            request["result"] = (False, str(error)); request["done"].set(); return
        user32 = ctypes.windll.user32
        previous = self.active_hotkey
        user32.UnregisterHotKey(None, HOTKEY_ID)
        if not user32.RegisterHotKey(None, HOTKEY_ID, modifiers, key):
            if previous:
                old_modifiers, old_key = parse_hotkey(previous)
                user32.RegisterHotKey(None, HOTKEY_ID, old_modifiers, old_key)
            request["result"] = (False, "다른 프로그램이 이미 사용하는 단축키입니다.")
        else:
            self.active_hotkey = request["hotkey"]
            request["result"] = (True, "")
        request["done"].set()

    def run(self):
        MSG = self._message_type(); message = MSG()
        # PeekMessage를 한 번 호출해야 이 스레드의 Windows 메시지 큐가 생성된다.
        ctypes.windll.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.ready.set()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                self.capture_events.put("capture")
            elif message.message == WM_HOTKEY_RECONFIGURE:
                self._apply_request()

