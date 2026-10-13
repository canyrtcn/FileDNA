"""Amber theme and rounded-control regression checks.

Headless environments can run the palette checks; widget tests require a display.
"""
import gc
import tkinter as tk
import unittest

from filedna.gui import (
    ACCENT, BG, DARK_INK, HOVER, ActionButton, FileDNAApp,
    RoundedPanel, _rounded_shape,
)


class AmberThemeTests(unittest.TestCase):
    def test_palette_uses_amber_not_old_blue(self):
        self.assertEqual(ACCENT.lower(), "#f3b544")
        self.assertEqual(HOVER.lower(), "#ffd17a")
        self.assertNotEqual(ACCENT.lower(), "#428ce5")
        self.assertNotEqual(BG.lower(), "#0d131d")
        self.assertNotEqual(DARK_INK, ACCENT)

    def test_no_auto_delete_added(self):
        from filedna import gui
        self.assertFalse(hasattr(gui.FileDNAApp, "delete_duplicates"))


class RoundedWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._close()
            # Collect the destroyed root on the main thread: cyclic Tk
            # wrappers left for a later GC could otherwise be finalized on a
            # scanner worker thread, which aborts the interpreter.
            del self.app
            gc.collect()

    def test_rounded_components_keep_existing_callbacks(self):
        self.assertIsInstance(self.app.scan_button, ActionButton)
        self.assertIsInstance(self.app.browse_button, ActionButton)
        self.assertIsInstance(self.app.stop_button, ActionButton)
        self.assertEqual(self.app.scan_button.main.cget("text"), "Start scan")
        self.assertEqual(self.app.scan_button.small.cget("text"), "Taramayı başlat")
        self.app.set_language("TR")
        self.assertEqual(self.app.scan_button.main.cget("text"), "Taramayı başlat")
        self.assertEqual(self.app.scan_button.small.cget("text"), "Start scan")

    def test_entry_and_result_table_live_in_rounded_panels(self):
        self.assertIsInstance(self.app.folder_input.master.master, RoundedPanel)
        self.assertIsInstance(self.app.tree.master.master, RoundedPanel)

    def test_disabled_button_cannot_fire(self):
        calls = []
        action = ActionButton(self.app, lambda: calls.append(1), primary=True)
        action.enable(False)
        action.click()
        self.assertEqual(calls, [])
        action.enable(True)
        action.click()
        self.assertEqual(calls, [1])
        action.destroy()

    def test_rounded_shape_renders_on_canvas(self):
        canvas = tk.Canvas(self.app, width=100, height=45)
        _rounded_shape(canvas, 1, 1, 99, 44, 12, ACCENT)
        self.assertEqual(len(canvas.find_all()), 1)
        self.assertEqual(canvas.itemcget(canvas.find_all()[0], "fill"), ACCENT)
        canvas.destroy()


if __name__ == "__main__":
    unittest.main()
