"""Compact results-first layout regression tests (GUI requires a display)."""
import gc
import tkinter as tk
import unittest

from filedna.gui import ActionButton, FileDNAApp, RoundedPanel, WORDS


class CompactLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._close()
            del self.app
        gc.collect()

    def test_compact_controls_keep_stable_public_widgets(self):
        app = self.app
        self.assertEqual(tuple(map(int, app.minsize())), (950, 660))
        for button in (app.browse_button, app.scan_button, app.stop_button,
                       app.open_button, app.export_button, app.select_button):
            self.assertIsInstance(button, ActionButton)
            self.assertLessEqual(int(button.cget("height")), 40)
            self.assertEqual(button.itemcget(button._sub_window, "state"),
                             "hidden")
        self.assertEqual(int(app.folder_input.master.master.cget("height")), 42)
        self.assertIsInstance(app.tree.master.master, RoundedPanel)
        self.assertEqual(int(app.tree.master.master.cget("height")), 240)

    def test_metrics_are_a_small_one_line_ribbon(self):
        app = self.app
        for name, (title, alternate, value) in app.metrics.items():
            self.assertIsInstance(title.master.master, RoundedPanel)
            self.assertEqual(int(title.master.master.cget("height")), 82)
            self.assertFalse(alternate.winfo_manager())
            self.assertTrue(value.winfo_manager())

    def test_language_switch_preserves_primary_and_secondary_text_state(self):
        app = self.app
        app.set_language("EN")
        self.assertEqual(app.scan_button.main["text"], WORDS["scan"][0])
        self.assertEqual(app.scan_button.small["text"], WORDS["scan"][1])
        self.assertEqual(app.open_button.main["text"], WORDS["open_short"][0])
        self.assertEqual(app.export_button.main["text"], WORDS["export_short"][0])
        app.set_language("TR")
        self.assertEqual(app.scan_button.main["text"], WORDS["scan"][1])
        self.assertEqual(app.open_button.main["text"], WORDS["open_short"][1])
        self.assertEqual(app.select_button.main["text"], WORDS["select_short"][1])

    def test_keyboard_shortcuts_are_installed(self):
        app = self.app
        self.assertTrue(app.bind("<Control-f>"))
        self.assertTrue(app.bind("<F5>"))
        self.assertTrue(app.bind("<F1>"))
        app._focus_filter()
        self.assertEqual(app.focus_get(), app.filter_entry)

    def test_buttons_show_focus_border(self):
        app = self.app
        button = app.scan_button
        button._set_focus(True)
        self.assertTrue(button._focused)
        button._set_focus(False)
        self.assertFalse(button._focused)


if __name__ == "__main__":
    unittest.main()
