"""Regression tests for FileDNA's localized read-only desktop interface."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from filedna import __version__
from filedna.gui import FileDNAApp, GITHUB_PROFILE, GITHUB_REPO, WORDS


class GuiStaticTests(unittest.TestCase):
    def test_complete_english_turkish_dictionary(self):
        for key, entries in WORDS.items():
            with self.subTest(key=key):
                self.assertEqual(len(entries), 2)
                self.assertTrue(entries[0])
                self.assertTrue(entries[1])

    def test_correct_author_and_repository(self):
        self.assertEqual(GITHUB_PROFILE, "https://github.com/canyrtcn")
        self.assertEqual(GITHUB_REPO, "https://github.com/canyrtcn/FileDNA")


class GuiIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = FileDNAApp()
            self.app.withdraw()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._close()

    def test_english_default_turkish_toggle_and_version(self):
        self.assertEqual(self.app.language, "EN")
        self.assertIn(f"FileDNA v{__version__}", self.app.title())
        self.assertEqual(self.app.results_title["text"], "Duplicate files")
        self.app.set_language("TR")
        self.assertEqual(self.app.results_title["text"], "Bulunan kopyalar")
        self.app.set_language("EN")
        self.assertEqual(self.app.results_title["text"], "Duplicate files")

    def test_read_only_duplicate_scan_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = {"a.txt": b"duplicate", "b.txt": b"duplicate",
                        "different.txt": b"different"}
            for name, payload in original.items():
                (root / name).write_bytes(payload)
            self.app.folder.set(str(root))
            self.app._start_scan()
            deadline = time.monotonic() + 10.0
            while self.app._report is None and time.monotonic() < deadline:
                self.app.update()
                time.sleep(0.02)
            self.assertIsNotNone(self.app._report, "Scan did not finish")
            self.assertEqual(self.app._report.duplicate_files, 1)
            self.assertEqual(self.app.percent["text"], "100%")
            self.assertTrue(self.app.export_button.enabled)
            self.assertEqual(original, {
                name: (root / name).read_bytes() for name in original
            })
            report_path = root / "report.json"
            with patch("filedna.gui.filedialog.asksaveasfilename",
                       return_value=str(report_path)):
                self.app._export_json()
            import json
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["duplicate_files"], 1)


if __name__ == "__main__":
    unittest.main()
