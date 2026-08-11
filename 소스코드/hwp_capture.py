from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from config import APP_NAME, acquire_single_instance
from assets import enable_dpi_awareness
from app import CaptureApp


def main() -> None:
    # 자동 시작 + 수동 실행으로 중복 실행되면 단축키 등록이 충돌하므로 한 번만 실행되게 막는다.
    # 핸들은 프로세스가 끝날 때까지 살려둬야 하므로 지역 변수로 mainloop 동안 유지한다.
    instance_handle = acquire_single_instance()
    if instance_handle is None:
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo(APP_NAME, "이미 실행 중입니다.\n작업표시줄 트레이 아이콘에서 설정을 열 수 있습니다.")
        root.destroy()
        sys.exit(0)
    enable_dpi_awareness()
    CaptureApp().run()


if __name__ == "__main__":
    main()
