"""Selection, context-menu and confirmation regression tests.

No real recycling occurs in these tests.
"""
import gc
import hashlib
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from filedna.cleanup import UnsafeSelection, make_plan, select_extra_paths
from filedna.gui import FileDNAApp, FIELD, FG, HIGHLIGHT
from filedna.scanner import DuplicateGroup, ScanReport


class SelectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = [str(self.root / n) for n in ("a.txt", "b.txt", "c.txt")]
        for path in self.paths:
            Path(path).write_bytes(b"same-file")
        digest = hashlib.sha256(b"same-file").hexdigest()
        report = ScanReport(root=str(self.root), scanned_at="2026-10-13")
        report.groups = [DuplicateGroup(digest, 9, self.paths)]
        report.examined_files = 3
        self.app._show_result(report)

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._close()
            del self.app
        if hasattr(self, "tmp"):
            self.tmp.cleanup()
        gc.collect()

    def test_treeview_extended_multiselect_and_select_extras(self):
        self.assertEqual(str(self.app.tree.cget("selectmode")), "extended")
        self.assertTrue(self.app.select_button.enabled)
        self.app._select_all_extras()
        self.assertEqual(set(self.app._selected_paths()), set(self.paths[1:]))
        self.assertEqual(make_plan(self.app._report, self.app._selected_paths()).bytes_total, 18)

    def test_manually_selecting_all_files_fails_safety_gate(self):
        rows = [row for row, path in self.app._row_paths.items() if path in self.paths]
        self.app.tree.selection_set(rows)
        with self.assertRaises(UnsafeSelection):
            make_plan(self.app._report, self.app._selected_paths())

    def test_recycle_cancel_never_creates_worker(self):
        self.app._select_all_extras()
        with patch("filedna.gui.messagebox.askyesno", return_value=False) as confirmation:
            self.app._recycle_selected()
        confirmation.assert_called_once()
        self.assertFalse(self.app._cleanup_running)
        self.assertIsNone(self.app._cleanup_thread)
        self.assertTrue(all(Path(path).exists() for path in self.paths))

    def test_recycle_all_group_selection_never_opens_confirmation(self):
        self.app.tree.selection_set(list(self.app._row_paths))
        with patch("filedna.gui.messagebox.askyesno") as confirm, \
             patch("filedna.gui.messagebox.showwarning") as warn:
            self.app._recycle_selected()
        confirm.assert_not_called()
        warn.assert_called_once()
        self.assertFalse(self.app._cleanup_running)

    def test_copy_paths_and_clear_selection(self):
        self.app._select_all_extras()
        self.app._copy_selected_paths()
        copied = self.app.clipboard_get()
        for path in self.paths[1:]:
            self.assertIn(path, copied)
        self.app._clear_selection()
        self.assertEqual(self.app.tree.selection(), ())

    def test_context_menu_theme(self):
        menu = self.app._context_menu
        self.assertEqual(menu.cget("background"), FIELD)
        self.assertEqual(menu.cget("activebackground"), HIGHLIGHT)
        self.assertEqual(menu.cget("foreground"), FG)

    def test_treeview_heading_hover_never_maps_white(self):
        from tkinter import ttk
        style = ttk.Style(self.app)
        mapping = style.map("DNA.Treeview.Heading")
        values = [value for _states, value in mapping["background"]]
        self.assertTrue(all(str(value).lower() not in ("white", "#ffffff") for value in values))


if __name__ == "__main__":
    unittest.main()
