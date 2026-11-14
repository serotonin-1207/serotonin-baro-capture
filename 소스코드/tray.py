"""영역 캡처용 Windows 알림 영역 아이콘과 메뉴."""
import ctypes
import logging
import sys
import threading
from ctypes import wintypes
from pathlib import Path

from config import APP_NAME


TRAY_MESSAGE = 0x8001
WM_CLOSE = 0x0010
NIM_ADD, NIM_DELETE, NIM_SETFOCUS = 0, 2, 3
MENU_ITEMS = (("capture", "영역 캡처"), ("history", "최근 캡처"), ("quit", "종료"))
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                           wintypes.WPARAM, wintypes.LPARAM)


class WindowClass(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("procedure", WNDPROC),
        ("class_extra", ctypes.c_int), ("window_extra", ctypes.c_int),
        ("instance", wintypes.HINSTANCE), ("icon", wintypes.HICON),
        ("cursor", wintypes.HANDLE), ("background", wintypes.HBRUSH),
        ("menu_name", wintypes.LPCWSTR), ("class_name", wintypes.LPCWSTR),
    ]


class NotifyIconData(ctypes.Structure):
    # V1 구조체는 필요한 아이콘, 콜백, 툴팁 필드만 포함한다.
    _fields_ = [
        ("size", wintypes.DWORD), ("window", wintypes.HWND),
        ("identifier", wintypes.UINT), ("flags", wintypes.UINT),
        ("callback", wintypes.UINT), ("icon", wintypes.HICON),
        ("tip", wintypes.WCHAR * 64),
    ]


class CaptureTray(threading.Thread):
    def __init__(self, events):
        super().__init__(name="CaptureTray", daemon=True)
        self.events = events
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.available = False
        self.window = None

    def run(self):
        user32 = self.user32 = ctypes.windll.user32
        self.notify = ctypes.windll.shell32.Shell_NotifyIconW
        self.notify.argtypes = (wintypes.DWORD, ctypes.POINTER(NotifyIconData))
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        instance = kernel32.GetModuleHandleW(None)
        user32.RegisterClassW.argtypes = (ctypes.POINTER(WindowClass),)
        user32.UnregisterClassW.argtypes = (wintypes.LPCWSTR, wintypes.HINSTANCE)
        user32.CreateWindowExW.argtypes = (
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        )
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DestroyWindow.argtypes = (wintypes.HWND,)
        user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        user32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT)
        user32.LoadImageW.restype = wintypes.HICON
        user32.DestroyIcon.argtypes = (wintypes.HICON,)
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = (wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR)
        user32.SetMenuDefaultItem.argtypes = (wintypes.HMENU, wintypes.UINT, wintypes.UINT)
        user32.TrackPopupMenu.argtypes = (wintypes.HMENU, wintypes.UINT, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.LPVOID)
        user32.DestroyMenu.argtypes = (wintypes.HMENU,)
        user32.RegisterWindowMessageW.argtypes = (wintypes.LPCWSTR,)

        class_name = "SerotoninBaroCaptureTray"
        procedure = WNDPROC(self.window_proc)
        window_class = WindowClass(procedure=procedure, instance=instance, class_name=class_name)
        self.taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        icon = None
        registered = False
        try:
            registered = user32.RegisterClassW(ctypes.byref(window_class))
            if not registered:
                return
            self.window = user32.CreateWindowExW(0, class_name, APP_NAME, 0, 0, 0, 0, 0,
                                                 None, None, instance, None)
            if not self.window:
                return
            icon_path = Path(__file__).resolve().with_name("app.ico")
            icon = user32.LoadImageW(None, str(icon_path), 1, 0, 0, 0x0050)
            if not icon:
                return
            self.icon_data = NotifyIconData(ctypes.sizeof(NotifyIconData), self.window, 1,
                                            0x0007, TRAY_MESSAGE, icon, APP_NAME)
            self.available = bool(self.notify(NIM_ADD, ctypes.byref(self.icon_data)))
            self.ready.set()
            if not self.available or self.stopping.is_set():
                return
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            if self.available:
                self.notify(NIM_DELETE, ctypes.byref(self.icon_data))
            if self.window:
                user32.DestroyWindow(self.window)
                self.window = None
            if icon:
                user32.DestroyIcon(icon)
            if registered:
                user32.UnregisterClassW(class_name, instance)
            self.ready.set()

    def window_proc(self, window, message, wparam, lparam):
        try:
            if message == WM_CLOSE:
                self.user32.PostQuitMessage(0)
                return 0
            if self.taskbar_created and message == self.taskbar_created and self.available:
                self.notify(NIM_ADD, ctypes.byref(self.icon_data))
                return 0
            if message == TRAY_MESSAGE:
                if lparam == 0x0202:  # WM_LBUTTONUP
                    self.events.put("history")
                elif lparam in (0x0205, 0x007B):  # WM_RBUTTONUP or WM_CONTEXTMENU
                    self.show_menu(window)
                return 0
        except Exception:
            logging.exception("Unable to process notification area event")
        return self.user32.DefWindowProcW(window, message, wparam, lparam)

    def show_menu(self, window):
        user32 = self.user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            for command, (_, label) in enumerate(MENU_ITEMS, 1):
                user32.AppendMenuW(menu, 0, command, label)
            user32.SetMenuDefaultItem(menu, 2, 0)
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(window)
            command = user32.TrackPopupMenu(menu, 0x0102, point.x, point.y, 0, window, None)
            user32.PostMessageW(window, 0, 0, 0)
            self.notify(NIM_SETFOCUS, ctypes.byref(self.icon_data))
            if 1 <= command <= len(MENU_ITEMS):
                self.events.put(MENU_ITEMS[command - 1][0])
        finally:
            user32.DestroyMenu(menu)

    def stop(self):
        self.stopping.set()
        if self.window:
            self.user32.PostMessageW(self.window, WM_CLOSE, 0, 0)
        self.join(timeout=1)
