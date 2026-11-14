"""캡처가 끝났음을 알리는 짧은 미리보기."""
import ctypes
import tkinter as tk
from ctypes import wintypes

from PIL import Image, ImageTk


class MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                ("work", wintypes.RECT), ("flags", wintypes.DWORD)]


def work_area(window, bbox):
    left, top, right, bottom = bbox
    center = wintypes.POINT((left + right) // 2, (top + bottom) // 2)
    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MonitorInfo))
    monitor = user32.MonitorFromPoint(center, 2)  # MONITOR_DEFAULTTONEAREST
    info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
    if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return info.work.right, info.work.bottom
    return window.winfo_screenwidth(), window.winfo_screenheight()


class CapturePreview(tk.Toplevel):
    def __init__(self, root, image, bbox):
        super().__init__(root, takefocus=False)
        self.withdraw()
        self.timer = None
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.88)
        self.configure(bg="#aecfdf")

        scale = float(self.tk.call("tk", "scaling")) / (4 / 3)
        ratio = min(1.0, 156 * scale / image.width, 96 * scale / image.height)
        if ratio < 1:
            size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
            image = image.resize(size, Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(image, master=self)
        padding = max(2, round(3 * scale))
        tk.Label(self, image=self.photo, bd=0, bg="#aecfdf").pack(padx=padding, pady=padding)
        width = image.width + 2 * padding
        height = image.height + 2 * padding
        right, bottom = work_area(self, bbox)
        margin = round(16 * scale)
        self.geometry(f"{width}x{height}+{right-width-margin}+{bottom-height-margin}")
        self.update_idletasks()

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
        hwnd = user32.GetAncestor(self.winfo_id(), 2)
        style = user32.GetWindowLongW(hwnd, -20)
        # WS_EX_NOACTIVATE | WS_EX_TRANSPARENT: 포커스와 마우스 입력을 가로채지 않는다.
        user32.SetWindowLongW(hwnd, -20, style | 0x08000020)
        self.deiconify()
        self.timer = self.after(500, self.destroy)

    def destroy(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        super().destroy()
        self.photo = None
