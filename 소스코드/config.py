from __future__ import annotations

import ctypes
import json
import os
import sys
import winreg
from pathlib import Path


APP_NAME, RUN_VALUE = "Serotonin 바로캡처", "NoAdsCapture"
APP_VERSION = "v1.0.0"
AUTHOR = "제작 이은호 · serotonin.1207@gmail.com"
GITHUB_REPOSITORY = "serotonin-1207/serotonin-baro-capture"
RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases"
HOTKEY_ID, WM_HOTKEY, PM_REMOVE = 1024, 0x0312, 0x0001
WM_HOTKEY_RECONFIGURE = 0x8000 + 41
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 1, 2, 4, 8
DOWNLOADS = Path.home() / "Downloads"
DEFAULT_SAVE_FOLDER = DOWNLOADS / "캡처"  # 다운로드 안의 '캡처' 폴더가 기본 저장 위치
CONFIG_PATH = Path(os.getenv("APPDATA", Path.home())) / "HwpCapture" / "settings.json"
DEFAULTS = {
    "hotkey": "Ctrl+Shift+Z", "save_folder": str(DEFAULT_SAVE_FOLDER), "image_format": "JPG", "quality": 100,
    "filename_pattern": "HWP_Capture_{date}_{time}", "auto_save": True, "start_with_windows": True,
    "start_minimized": True, "show_overlay": True, "hide_capture_window": True, "show_result_window": False,
    "copy_to_clipboard": True, "show_save_notification": True, "include_cursor": False,
    "guide_color": "파랑", "keep_selection_guide": False, "print_screen_enabled": False,
    "print_screen_action": "직접 지정 캡처", "shortcut_modes": {"직접지정": True, "창 캡처": False, "단위영역": False, "전체캡처": False, "스크롤캡처": False, "크기지정": False},
    "size_presets": [], "notify_on_clear": True, "notify_on_save_all": True, "hide_recent_list": False,
    "delete_old_when_full": True, "recent_captures": [],
}


def load_settings() -> dict:
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))  # BOM이 섞여 있어도 견고하게 읽는다.
        defaults = DEFAULTS.copy()
        defaults["shortcut_modes"] = DEFAULTS["shortcut_modes"].copy()
        defaults.update(loaded)
        return defaults
    except (OSError, json.JSONDecodeError):
        return DEFAULTS.copy()


def save_settings(settings: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 임시 파일에 먼저 쓰고 교체한다. 저장 도중 종료돼도 기존 설정이 깨지지 않는다.
    temp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, CONFIG_PATH)


def startup_command(start_minimized: bool) -> str:
    argument = " --minimized" if start_minimized else ""
    return f'"{sys.executable}"{argument}' if getattr(sys, "frozen", False) else f'"{sys.executable}" "{Path(__file__).resolve()}"{argument}'


def set_startup(enabled: bool, start_minimized: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, startup_command(start_minimized))
        else:
            try: winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError: pass


MUTEX_NAME = "Global\\NoAdsCapture_SingleInstance"
ERROR_ALREADY_EXISTS = 183


def acquire_single_instance() -> int | None:
    """이미 실행 중이면 None을 반환한다. 핸들은 프로세스가 끝날 때까지 살려둬야 한다."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def parse_hotkey(value: str) -> tuple[int, int]:
    modifiers, key = 0, None
    for part in [item.strip().lower() for item in value.split("+") if item.strip()]:
        if part in ("ctrl", "control"): modifiers |= MOD_CONTROL
        elif part == "shift": modifiers |= MOD_SHIFT
        elif part == "alt": modifiers |= MOD_ALT
        elif part in ("win", "windows"): modifiers |= MOD_WIN
        elif key is None: key = part
        else: raise ValueError("단축키 형식이 올바르지 않습니다.")
    if not modifiers or not key: raise ValueError("예: Ctrl+Shift+S처럼 조합키와 일반 키를 함께 지정하세요.")
    if len(key) == 1 and key.isalnum(): return modifiers, ord(key.upper())
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12: return modifiers, 0x6F + int(key[1:])
    raise ValueError("영문·숫자·F1~F12 키를 사용하세요.")
