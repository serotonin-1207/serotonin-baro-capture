"""영역 캡처 설정과 실행 중복 방지."""
import ctypes
import json
import os
import tempfile
from pathlib import Path

APP_NAME = "Serotonin 바로캡처"
APP_VERSION = "3.0.7"
RELEASES_URL = "https://github.com/serotonin-1207/serotonin-baro-capture/releases"
AUTHOR_EMAIL = "serotonin.1207@gmail.com"
DEFAULT_CAPTURE_SHORTCUT = "Ctrl+Shift+Z"
CONFIG_PATH = Path(os.getenv("APPDATA", Path.home())) / "HwpCapture" / "settings.json"


def read_settings():
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        saved = {}
    return saved if isinstance(saved, dict) else {}


def load_capture_shortcut():
    value = read_settings().get("hotkey")
    return value if isinstance(value, str) and value.strip() else DEFAULT_CAPTURE_SHORTCUT


def save_capture_shortcut(value):
    settings = read_settings()
    settings["hotkey"] = value
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_PATH.parent,
                                         prefix="settings-", suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            json.dump(settings, stream, ensure_ascii=False, indent=2)
        temporary_path.replace(CONFIG_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_hotkey(value):
    if not isinstance(value, str):
        raise ValueError("단축키 형식이 올바르지 않습니다.")
    modifiers = {"ctrl": 2, "control": 2, "shift": 4, "alt": 1, "win": 8, "windows": 8}
    flags = 0
    key = None
    for part in value.lower().split("+"):
        part = part.strip()
        if part in modifiers:
            flags |= modifiers[part]
        elif key is None:
            key = part
        else:
            raise ValueError("단축키 형식이 올바르지 않습니다.")
    if flags and key:
        if len(key) == 1 and key.isascii() and key.isalnum():
            return flags, ord(key.upper())
        if key in {f"f{i}" for i in range(1, 13)}:
            return flags, 0x6F + int(key[1:])
    raise ValueError("단축키 형식이 올바르지 않습니다.")


def format_hotkey(flags, key):
    names = ((2, "Ctrl"), (1, "Alt"), (4, "Shift"), (8, "Win"))
    modifiers = [name for bit, name in names if flags & bit]
    key_name = chr(key) if key < 0x70 else f"F{key - 0x6F}"
    return "+".join([*modifiers, key_name])


def acquire_single_instance():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, True, "Global\\NoAdsCapture_SingleInstance")
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return None
    if not handle:
        raise ctypes.WinError()
    return handle
