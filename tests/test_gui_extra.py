"""Extra GUI tests: full-language toggle, cancel/progress, clean close, links.

Supplements tests/test_gui_ui.py for the Aşama 2 acceptance list:
instant EN/TR switch of every visible string, scan cancellation, progress
indication, Tkinter-clean window close, and correct GitHub link handling.
"""
from __future__ import annotations

import gc
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import filedna.gui as gui_module
from filedna.gui import WORDS, FileDNAApp


def walk_widgets(root):
    yield root
    for child in root.winfo_children():
        yield from walk_widgets(child)


class GuiExtraTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.closed = False

    def tearDown(self):
        if hasattr(self, "app") and not self.closed:
            self.app._close()
            self.closed = True
        if hasattr(self, "app"):
            # Collect the destroyed root on the main thread: cyclic Tk
            # wrappers left for a later GC could otherwise be finalized on a
            # scanner worker thread, which aborts the interpreter.
            del self.app
            gc.collect()

    def close_app(self):
        self.app._close()
        self.closed = True
        del self.app
        gc.collect()

    def pump_until(self, condition, timeout=30.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.update()
            if condition():
                return True
            time.sleep(0.02)
        return condition()

    def test_toggle_translates_all_key_strings(self):
        from filedna.scanner import ScanReport
        app = self.app
        self.assertEqual(app.language, "EN")
        for code, idx in (("TR", 1), ("EN", 0)):
            app.set_language(code)
            self.assertEqual(app.language, code)
            # "ready" only shows while no scan has run; reset state first.
            app._state = "ready"
            app._report = None
            app._translate()
            # Static labels visible on screen.
            texts = set()
            for widget in walk_widgets(app):
                try:
                    value = widget.cget("text")
                except tk.TclError:
                    continue
                if isinstance(value, str) and value.strip():
                    texts.add(value)
            for key in ("subtitle", "hero", "folder", "browse", "scan", "stop",
                        "scanned", "groups", "copies", "space", "results",
                        "open_short", "export_short", "select_short",
                        "empty", "empty_help", "ready", "safe"):
                self.assertIn(WORDS[key][idx], texts, f"{code}:{key}")
            # Table headings (not separate widgets).
            for column, key in (("#0", "path"), ("size", "size"),
                                ("count", "count"), ("hash", "hash")):
                self.assertEqual(app.tree.heading(column)["text"], WORDS[key][idx])
            # Status line follows each scan state.
            for state in ("discovering", "hashing", "stopping", "cancelled",
                          "failed", "finished"):
                app._state = state
                app._translate()
                self.assertEqual(app.status_title.cget("text"), WORDS[state][idx])
            # Empty overlay switches with report content.
            app._report = None
            app._translate()
            self.assertEqual(app.empty_title.cget("text"), WORDS["empty"][idx])
            app._report = ScanReport(root="x", scanned_at="now")
            app._translate()
            self.assertEqual(app.empty_title.cget("text"), WORDS["none"][idx])
            self.assertEqual(app.empty_help.cget("text"), WORDS["none_help"][idx])
            app._report = None
        # Error dialogs use the active language.
        app.set_language("TR")
        with patch("filedna.gui.messagebox.showerror") as shown:
            app.folder.set(r"C:\böyle-bir-klasör-yok-12345")
            app._start_scan()
        shown.assert_called_once_with(WORDS["scan_error"][1], WORDS["invalid"][1])
        app.set_language("EN")

    def test_cancel_scan_and_progress(self):
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import os
            for i in range(60):
                (root / f"f-{i:02d}.bin").write_bytes(os.urandom(32 * 1024))
            import filedna.scanner as scanner_module
            original = scanner_module._hash_stable_file

            def slow_hash(path, expected, cancelled):
                time.sleep(0.05)
                return original(path, expected, cancelled)

            with patch.object(scanner_module, "_hash_stable_file",
                              side_effect=slow_hash):
                app.folder.set(str(root))
                app._start_scan()
                self.assertTrue(app._worker.is_alive())
                time.sleep(0.5)
                # UI stays responsive while the worker runs.
                app.update()
                self.assertIn(app.status_title.cget("text"),
                              (WORDS["discovering"][0], WORDS["hashing"][0]))
                app._cancel_scan()
                stopped = self.pump_until(
                    lambda: app.status_title.cget("text") == WORDS["cancelled"][0],
                    timeout=30.0)
                self.assertTrue(stopped, app.status_title.cget("text"))
                self.assertEqual(list(app.tree.get_children()), [])
                self.assertTrue(app.scan_button.enabled)
                self.assertFalse(app.stop_button.enabled)

    def test_progress_reaches_full_on_small_scan(self):
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"duplicate")
            (root / "b.txt").write_bytes(b"duplicate")
            app.folder.set(str(root))
            app._start_scan()
            done = self.pump_until(lambda: app._report is not None, timeout=15.0)
            self.assertTrue(done, "scan did not finish")
            self.assertEqual(app.percent.cget("text"), "100%")
            self.assertEqual(app._report.duplicate_files, 1)

    def test_close_mid_scan_is_tcl_clean(self):
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import os
            for i in range(80):
                (root / f"g-{i:02d}.bin").write_bytes(os.urandom(16 * 1024))
            import filedna.scanner as scanner_module
            original = scanner_module._hash_stable_file

            def slow_hash(path, expected, cancelled):
                time.sleep(0.05)
                return original(path, expected, cancelled)

            with patch.object(scanner_module, "_hash_stable_file",
                              side_effect=slow_hash):
                app.folder.set(str(root))
                app._start_scan()
                time.sleep(0.3)
                try:
                    self.close_app()
                except tk.TclError as error:
                    self.fail(f"_close raised TclError: {error}")
                self.assertIsNone(app._after_id)
                worker = app._worker
            if worker is not None:
                worker.join(timeout=15.0)

    def test_open_link_uses_exact_urls(self):
        app = self.app
        opened = []
        with patch.object(gui_module.webbrowser, "open",
                          side_effect=lambda url, **kw: opened.append(url) or True):
            app._open_link(gui_module.GITHUB_PROFILE)
            app._open_link(gui_module.GITHUB_REPO)
        self.assertEqual(opened, [gui_module.GITHUB_PROFILE, gui_module.GITHUB_REPO])
        with patch.object(gui_module.webbrowser, "open", return_value=False), \
             patch("filedna.gui.messagebox.showwarning") as warned:
            app._open_link(gui_module.GITHUB_REPO)
        warned.assert_called_once()

    def test_open_selected_launches_locator(self):
        import subprocess
        from filedna.gui import ActionButton
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kopya.txt"
            target.write_bytes(b"duplicate")
            (Path(tmp) / "kopya2.txt").write_bytes(b"duplicate")
            app.folder.set(str(Path(tmp)))
            app._start_scan()
            self.assertTrue(self.pump_until(lambda: app._report is not None, timeout=15.0))
            rows = [row for row in app._row_paths]
            self.assertTrue(rows)
            app.tree.selection_set(rows[0])
            app._on_selection()
            self.assertTrue(app.open_button.enabled)
            with patch.object(subprocess, "Popen") as popen:
                app._open_selected()
            popen.assert_called_once()
            args = popen.call_args[0][0]
            self.assertIn(str(target.parent), args[-1] if isinstance(args, list) else args)

    def test_repeated_help_open_close_with_language_switch(self):
        from filedna.gui import HELP_STEPS
        app = self.app
        for _ in range(5):
            app._open_help()
            dialog = app._help_window
            self.assertIsNotNone(dialog)
            app._dismiss_help()
            self.assertIsNone(app._help_window)
        app._open_help()
        dialog = app._help_window
        app.set_language("TR")
        self.assertIn("nasıl kullanılır", dialog.title())
        self.assertEqual(app._help_text_widgets[0][0]["text"], HELP_STEPS["TR"][0][0])
        app.set_language("EN")
        self.assertEqual(app._help_text_widgets[0][0]["text"], HELP_STEPS["EN"][0][0])
        app._dismiss_help()
        self.assertIsNone(app._help_window)

    def test_stop_preserves_cancelled_status(self):
        import filedna.scanner as scanner_module
        from filedna.gui import WORDS
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import os
            for i in range(60):
                (root / f"s-{i:02d}.bin").write_bytes(os.urandom(32 * 1024))
            original = scanner_module._hash_stable_file

            def slow_hash(path, expected, cancelled):
                time.sleep(0.05)
                return original(path, expected, cancelled)

            with patch.object(scanner_module, "_hash_stable_file",
                              side_effect=slow_hash):
                app.folder.set(str(root))
                app._start_scan()
                time.sleep(0.5)
                app._cancel_scan()
                stopped = self.pump_until(
                    lambda: app.status_title.cget("text") == WORDS["cancelled"][0],
                    timeout=30.0)
                self.assertTrue(stopped, app.status_title.cget("text"))
                # Late progress events from the dying worker must not corrupt it.
                for _ in range(5):
                    app.update()
                    time.sleep(0.05)
                self.assertEqual(app.status_title.cget("text"), WORDS["cancelled"][0])

    def test_sequential_scans_same_session(self):
        app = self.app
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"duplicate")
            (root / "b.txt").write_bytes(b"duplicate")
            for round_no in range(3):
                app.folder.set(str(root))
                app._start_scan()
                done = self.pump_until(lambda: app._report is not None, timeout=15.0)
                self.assertTrue(done, f"tur {round_no} bitmedi")
                self.assertEqual(app._report.duplicate_files, 1)
                self.assertEqual(len(app.tree.get_children()), 1)
                self.assertEqual(app.percent.cget("text"), "100%")
            # Yeni içerik: sonuçlar eskisini yansıtmamalı.
            (root / "a.txt").write_bytes(b"degisti-artik-tek")
            (root / "b.txt").write_bytes(b"tamamen-farkli-icerik")
            app._start_scan()
            done = self.pump_until(lambda: app._report is not None and
                                   len(app.tree.get_children()) == 0, timeout=15.0)
            self.assertTrue(done, "farklı içerik taraması bitmedi")
            self.assertEqual(app._report.groups, [])

    def test_dwm_failure_is_safe(self):
        app = self.app
        self.assertIsInstance(gui_module._apply_windows_caption(app), bool)
        with patch.object(gui_module.ctypes.windll.user32, "GetParent",
                          side_effect=OSError("DWM yok")):
            self.assertFalse(gui_module._apply_windows_caption(app))

    def test_action_button_keyboard_activates(self):
        from filedna.gui import ActionButton
        app = self.app
        calls = []
        button = ActionButton(app, lambda: calls.append(1))
        button.pack()
        # Keyboard dispatch needs a mapped window: briefly show it.
        app.deiconify()
        app.update()
        button.focus_force()
        app.update()
        button.event_generate("<Return>")
        button.event_generate("<space>")
        app.update()
        self.assertEqual(calls, [1, 1])
        button.enable(False)
        button.event_generate("<Return>")
        app.update()
        self.assertEqual(calls, [1, 1])
        button.destroy()
        app.withdraw()
        app.update()


if __name__ == "__main__":
    unittest.main()
