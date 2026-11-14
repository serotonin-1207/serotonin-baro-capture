import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PIL import Image

from app import CaptureApp
from config import load_capture_shortcut, parse_hotkey, read_settings, save_capture_shortcut
from history import CaptureHistory


class HistoryTests(unittest.TestCase):
    def test_memory_budget_evicts_oldest(self):
        history = CaptureHistory(max_bytes=1300)
        for index in range(5):
            history.add(Image.new("RGB", (10, 10), (index, 0, 0)))
        self.assertEqual(len(history.items), 3)
        self.assertEqual(history.items[0].image.getpixel((0, 0)), (4, 0, 0))

    def test_latest_capture_is_kept_even_when_large(self):
        history = CaptureHistory(max_bytes=10)
        history.add(Image.new("RGB", (10, 10)))
        self.assertEqual(len(history.items), 1)

    def test_count_limit(self):
        history = CaptureHistory(max_count=2)
        for _ in range(3):
            history.add(Image.new("RGB", (10, 10)))
        self.assertEqual(len(history.items), 2)


class HotkeyTests(unittest.TestCase):
    def test_settings_only_supply_retained_actions(self):
        with patch("config.CONFIG_PATH") as path:
            path.read_text.return_value = '{"hotkey":"Ctrl+F8","history_hotkey":"Ctrl+F9"}'
            self.assertEqual(load_capture_shortcut(), "Ctrl+F8")
            path.read_text.return_value = '{"history_hotkey":"Ctrl+F9"}'
            self.assertEqual(load_capture_shortcut(), "Ctrl+Shift+Z")

    def test_save_preserves_existing_settings(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"auto_save":true}', encoding="utf-8")
            with patch("config.CONFIG_PATH", path):
                save_capture_shortcut("Ctrl+F8")
                self.assertEqual(read_settings(), {"auto_save": True, "hotkey": "Ctrl+F8"})

    def test_occupied_shortcut_leaves_old_registration_and_settings(self):
        app = CaptureApp.__new__(CaptureApp)
        app.events = Mock()
        previous = app.hotkeys = Mock(label="Ctrl+Shift+Z")
        with patch("app.GlobalHotkeyListener") as factory, patch("app.save_capture_shortcut") as save:
            listener = factory.return_value
            listener.label = None
            with self.assertRaisesRegex(ValueError, "등록할 수 없습니다"):
                app.change_capture_shortcut("Ctrl+F8")
            listener.stop.assert_called_once()
            save.assert_not_called()
        self.assertIs(app.hotkeys, previous)
        previous.stop.assert_not_called()

    def test_legacy_shortcut_parsing(self):
        self.assertEqual(parse_hotkey("Ctrl+F8"), (2, 0x77))
        with self.assertRaises(ValueError):
            parse_hotkey("Ctrl+한")
