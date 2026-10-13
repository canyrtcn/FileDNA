"""Regression tests for FileDNA's bilingual help and native Windows title bar."""
import gc
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

from filedna.gui import (
    FileDNAApp, HELP_STEPS, _apply_windows_caption, _colorref
)
from filedna.scanner import DuplicateGroup, ScanReport


class WindowsCaptionTests(unittest.TestCase):
    def test_windows_colorref_byte_order(self):
        self.assertEqual(_colorref("#112233"), 0x00332211)
        self.assertEqual(_colorref("#f3b544"), 0x0044b5f3)

    def test_bad_color_rejected(self):
        with self.assertRaises(ValueError):
            _colorref("#fff")

    def test_unsupported_platform_is_safe(self):
        with patch("filedna.gui.sys.platform", "linux"):
            self.assertFalse(_apply_windows_caption(None))

    @unittest.skipUnless(sys.platform == "win32", "Requires Windows DWM")
    def test_real_windows_titlebar_fallback_no_crash(self):
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"No Tk display: {exc}")
        try:
            window.update_idletasks()
            self.assertIsInstance(_apply_windows_caption(window), bool)
        finally:
            window.destroy()
            del window
            gc.collect()


class HelpContentTests(unittest.TestCase):
    def test_four_complete_steps_per_language(self):
        for locale in ("EN", "TR"):
            self.assertEqual(len(HELP_STEPS[locale]), 4)
            self.assertTrue(all(title and content
                                for title, content in HELP_STEPS[locale]))


class HelpIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"No Tk display: {exc}")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._close()
            del self.app
            gc.collect()

    def test_help_dialog_opens_reuses_and_switches_language(self):
        self.app._open_help()
        dialog = self.app._help_window
        self.assertIsNotNone(dialog)
        self.assertIn("How to use FileDNA", dialog.title())
        self.assertEqual(len(self.app._help_text_widgets), 4)
        self.assertIn("Choose a folder", self.app._help_text_widgets[0][0]["text"])
        self.app._open_help()
        self.assertIs(self.app._help_window, dialog)
        self.app.set_language("TR")
        self.assertIn("nasıl kullanılır", dialog.title())
        self.assertEqual(self.app._help_text_widgets[0][0]["text"], "Klasör seçin")
        self.assertIn("JSON", self.app._help_safety["text"])
        self.app._dismiss_help()
        self.assertIsNone(self.app._help_window)

    def test_group_labels_translate_after_completed_scan(self):
        report = ScanReport(
            root="test", scanned_at="2026-10-13T00:00:00+00:00",
            examined_files=2,
            groups=[DuplicateGroup(sha256="a" * 64, size_bytes=4,
                                   paths=["first", "second"])]
        )
        self.app._show_result(report)
        parent = self.app.tree.get_children()[0]
        self.assertIn("files", self.app.tree.item(parent, "text"))
        self.app.set_language("TR")
        self.assertIn("dosya", self.app.tree.item(parent, "text"))
        self.assertIn("Kopya grubu", self.app.status_detail["text"])
        self.app.set_language("EN")
        self.assertIn("files", self.app.tree.item(parent, "text"))

    def test_help_button_keyboard_focus_and_close_idempotency(self):
        self.assertIn(str(self.app.help_button.cget("takefocus")).lower(), ("1", "true"))
        self.app._open_help()
        self.app._close()
        self.assertIsNone(self.app._help_window)
        self.app._close()


if __name__ == "__main__":
    unittest.main()
