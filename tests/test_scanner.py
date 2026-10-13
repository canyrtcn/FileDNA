"""Read-only scanner behavior and duplicate-detection regression tests."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from filedna.scanner import ScanCancelled, scan_directory


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make(self, filename: str, content: bytes) -> Path:
        p = self.root / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return p

    def test_equal_content_different_names_matches(self) -> None:
        self.make("alpha.txt", b"same")
        self.make("folder/bravo.bin", b"same")
        self.make("unique.bin", b"different")
        report = scan_directory(self.root)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.groups[0].size_bytes, 4)
        self.assertEqual(report.duplicate_files, 1)
        self.assertEqual(report.reclaimable_bytes, 4)
        self.assertEqual(report.candidate_files, 2)
        self.assertEqual(report.hashed_files, 2)

    def test_same_size_different_content_not_duplicate(self) -> None:
        self.make("a", b"abc")
        self.make("b", b"xyz")
        self.assertEqual(scan_directory(self.root).groups, [])

    def test_empty_files_count_as_duplicates(self) -> None:
        self.make("a", b"")
        self.make("b", b"")
        report = scan_directory(self.root)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.reclaimable_bytes, 0)

    def test_empty_directory(self) -> None:
        report = scan_directory(self.root)
        self.assertEqual(report.examined_files, 0)
        self.assertEqual(report.groups, [])
        self.assertEqual(report.hashed_files, 0)

    def test_json_report_structure(self) -> None:
        self.make("a", b"x")
        self.make("b", b"x")
        payload = json.loads(json.dumps(scan_directory(self.root).to_dict()))
        self.assertEqual(payload["duplicate_files"], 1)
        self.assertEqual(len(payload["groups"][0]["sha256"]), 64)
        self.assertEqual(len(payload["groups"][0]["paths"]), 2)

    def test_files_are_not_modified(self) -> None:
        item = self.make("a.txt", b"safe content")
        self.make("b.txt", b"safe content")
        before = (item.read_bytes(), item.stat().st_mtime_ns)
        scan_directory(self.root)
        self.assertEqual((item.read_bytes(), item.stat().st_mtime_ns), before)

    def test_cancellation(self) -> None:
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(ScanCancelled):
            scan_directory(self.root, cancel_event=cancel)

    def test_progress_phases(self) -> None:
        self.make("a", b"x")
        self.make("b", b"x")
        updates = []
        scan_directory(self.root, progress=lambda phase, current, total: updates.append((phase, current, total)))
        self.assertTrue(any(phase == "hashing" and total == 2 for phase, _, total in updates))
        self.assertEqual(updates[-1][0], "complete")

    def test_rejects_missing_directory(self) -> None:
        with self.assertRaises(ValueError):
            scan_directory(self.root / "does-not-exist")

    @unittest.skipUnless(hasattr(os, "symlink"), "Symlinks unavailable")
    def test_symlink_is_excluded(self) -> None:
        source = self.make("a.txt", b"x")
        self.make("b.txt", b"x")
        try:
            (self.root / "alias.txt").symlink_to(source)
        except (NotImplementedError, OSError):
            self.skipTest("Symlinks unavailable under current permissions")
        report = scan_directory(self.root)
        self.assertEqual(report.duplicate_files, 1)
        self.assertEqual(report.skipped_symlinks, 1)

    def test_hardlink_is_not_extra_copy(self) -> None:
        source = self.make("a.txt", b"x")
        try:
            os.link(source, self.root / "hardlink.txt")
        except (NotImplementedError, OSError):
            self.skipTest("Hardlinks unavailable")
        report = scan_directory(self.root)
        self.assertEqual(report.duplicate_files, 0)
        self.assertEqual(report.skipped_hardlinks, 1)

    def test_multiple_groups_and_sort_by_savings(self) -> None:
        self.make("a", b"abc")
        self.make("b", b"abc")
        self.make("c", b"0123456789")
        self.make("d", b"0123456789")
        report = scan_directory(self.root)
        self.assertEqual([g.size_bytes for g in report.groups], [10, 3])
        self.assertEqual(report.reclaimable_bytes, 13)


if __name__ == "__main__":
    unittest.main()
