import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from app import CaptureApp
from selector import ScreenSelector
from snapshot import ScreenSnapshot


class SnapshotTests(unittest.TestCase):
    def test_popup_pixels_survive_later_desktop_change(self):
        desktop = Image.new("RGB", (100, 80), "white")
        desktop.paste("red", (20, 10, 60, 50))
        with patch("snapshot.ImageGrab.grab", return_value=desktop.copy()):
            with patch("snapshot.ctypes.windll.user32.GetSystemMetrics", return_value=0):
                snapshot = ScreenSnapshot.grab()
        desktop.paste("white", (20, 10, 60, 50))
        self.assertEqual(snapshot.crop((20, 10, 60, 50)).getpixel((5, 5)), (255, 0, 0))

    def test_negative_monitor_origin_and_cross_monitor_crop(self):
        desktop = Image.new("RGB", (300, 200), "white")
        desktop.paste("blue", (90, 40, 120, 70))
        result = ScreenSnapshot(desktop, (-100, -50)).crop((-10, -10, 20, 20))
        self.assertEqual(result.size, (30, 30))
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255))

    def test_offscreen_selection_is_clipped(self):
        snapshot = ScreenSnapshot(Image.new("RGB", (100, 80), "red"), (0, 0))
        self.assertEqual(snapshot.crop((-10, -20, 30, 40)).size, (30, 40))
        with self.assertRaises(ValueError):
            snapshot.crop((101, 0, 110, 10))


class CaptureFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = CaptureApp.__new__(CaptureApp)
        self.app.root = Mock()
        self.app.user32 = Mock()
        self.app.panel = None
        self.app.preview = None
        self.app.selecting = False
        self.app.confirming_clear = False
        self.app.closing = False
        self.app.return_focus = None
        self.app.history = Mock()
        self.app.copy = Mock()
        self.app.show_preview = Mock()
        self.app.status = Mock()

    def test_capture_grabs_before_creating_selection_ui(self):
        sequence = []
        with patch("app.ScreenSnapshot.grab", side_effect=lambda: sequence.append("grab") or Mock()):
            with patch("app.ScreenSelector", side_effect=lambda *args: sequence.append("overlay")):
                self.app.start_capture()
                self.app.start_capture()
        self.assertEqual(sequence, ["grab", "overlay"])
        self.app.root.after_idle.assert_not_called()

    def test_visible_panel_is_hidden_before_grabbing(self):
        self.app.panel = Mock(settings_page=None)
        self.app.panel.winfo_viewable.return_value = True
        with patch("app.ScreenSnapshot.grab") as grab, patch("app.ScreenSelector"):
            self.app.start_capture()
            self.app.panel.hide.assert_called_once()
            grab.assert_not_called()
            self.app.root.after_idle.call_args.args[0]()
            grab.assert_called_once()

    def test_shortcut_captures_visible_settings_and_restores_panel_focus(self):
        panel = self.app.panel = Mock(hwnd=42, settings_page=Mock())
        panel.winfo_viewable.return_value = True
        self.app.user32.GetForegroundWindow.return_value = panel.hwnd
        self.app.return_focus = 17
        with patch("app.ScreenSnapshot.grab") as grab, patch("app.ScreenSelector") as selector:
            self.app.handle_event("capture")
            panel.hide.assert_not_called()
            grab.assert_called_once()
            self.assertIs(selector.call_args.args[1], grab.return_value)
            selector.call_args.args[3]()
        self.assertFalse(self.app.selecting)
        self.app.user32.SetForegroundWindow.assert_called_once_with(panel.hwnd)
        self.assertEqual(self.app.return_focus, 17)

    def test_failed_grab_allows_retry(self):
        with patch("app.ScreenSnapshot.grab", side_effect=OSError("capture failed")):
            self.app.start_capture()
        self.assertFalse(self.app.selecting)
        self.app.status.assert_called_once()
        with patch("app.ScreenSnapshot.grab"), patch("app.ScreenSelector") as selector:
            self.app.start_capture()
        selector.assert_called_once()

    def test_history_and_clipboard_use_same_original(self):
        snapshot = ScreenSnapshot(Image.new("RGB", (100, 80), "red"), (-50, -20))
        self.app.capture(snapshot, (-40, -10, -20, 10))
        image = self.app.copy.call_args.args[0]
        self.assertEqual(image.size, (20, 20))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
        self.app.history.add.assert_called_once_with(image)
        self.app.show_preview.assert_called_once_with(image, (-40, -10, -20, 10))

    def test_reverse_drag_and_tiny_selection(self):
        selector = Mock(start=(50, 60))
        ScreenSelector.finish(selector, SimpleNamespace(x_root=10, y_root=20))
        selector.picked.assert_called_once_with(selector.snapshot, (10, 20, 50, 60))
        selector.picked.reset_mock()
        ScreenSelector.finish(selector, SimpleNamespace(x_root=51, y_root=61))
        selector.picked.assert_not_called()
