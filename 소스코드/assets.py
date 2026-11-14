from __future__ import annotations

import ctypes

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

