from __future__ import annotations

import ctypes

from PIL import Image, ImageDraw


def tray_image() -> Image.Image:
    """트레이 아이콘용 이미지를 그린다(app.ico와 같은 파란 캡처 프레임)."""
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, s - 4, s - 4), radius=12, fill="#1677ff")
    m, t, L, white = 18, 4, 12, "#ffffff"
    for cx, sx in ((m, 1), (s - m, -1)):
        for cy, sy in ((m, 1), (s - m, -1)):
            d.line((cx, cy, cx + L * sx, cy), fill=white, width=t)
            d.line((cx, cy, cx, cy + L * sy), fill=white, width=t)
    d.ellipse((s // 2 - 5, s // 2 - 5, s // 2 + 5, s // 2 + 5), fill=white)
    return img


def enable_dpi_awareness():
    """Tk 선택 좌표와 ImageGrab 캡처 좌표를 같은 실제 픽셀 기준으로 맞춘다."""
    try:
        # PER_MONITOR_AWARE_V2: 모니터마다 다른 배율에서도 실제 화면 픽셀을 사용한다.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except AttributeError:
                pass

