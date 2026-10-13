"""No real files are recycled by this test suite; trash calls are injected."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from filedna.cleanup import (
    UnsafeSelection, make_plan, move_to_trash, select_extra_paths,
)
from filedna.scanner import DuplicateGroup, ScanReport


class RecycleSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.paths = [self.root / n for n in ("a.txt", "b.txt", "c.txt")]
        for item in self.paths:
            item.write_bytes(b"test-file")
        digest = hashlib.sha256(b"test-file").hexdigest()
        self.report = ScanReport(str(self.root), "2026-10-13")
        self.report.groups = [
            DuplicateGroup(digest, 9, [str(p) for p in self.paths])
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_select_extras_leaves_one(self):
        choices = select_extra_paths(self.report)
        self.assertEqual(choices, tuple(str(p) for p in self.paths[1:]))
        self.assertEqual(make_plan(self.report, choices).bytes_total, 18)

    def test_explicit_select_all_rejected(self):
        with self.assertRaises(UnsafeSelection):
            make_plan(self.report, [str(p) for p in self.paths])

    def test_unknown_path_rejected(self):
        with self.assertRaises(UnsafeSelection):
            make_plan(self.report, [str(self.root / "unknown")])

    def test_empty_selection_rejected(self):
        with self.assertRaises(UnsafeSelection):
            make_plan(self.report, [])

    def test_valid_recycling_uses_injected_trash_only(self):
        called = []
        plan = make_plan(self.report, [str(self.paths[1])])
        result = move_to_trash(self.report, plan, trash=called.append)
        self.assertEqual(called, [str(self.paths[1])])
        self.assertEqual(result.moved, called)
        self.assertFalse(result.errors)
        self.assertTrue(all(p.exists() for p in self.paths))

    def test_mutated_selected_file_never_sent(self):
        plan = make_plan(self.report, [str(self.paths[1])])
        self.paths[1].write_bytes(b"changed!!")
        called = []
        result = move_to_trash(self.report, plan, trash=called.append)
        self.assertFalse(called)
        self.assertIn(str(self.paths[1]), result.errors)

    def test_modified_only_survivor_blocks_cleanup(self):
        plan = make_plan(self.report, [str(p) for p in self.paths[1:]])
        self.paths[0].write_bytes(b"not-same!")
        called = []
        result = move_to_trash(self.report, plan, trash=called.append)
        self.assertFalse(called)
        self.assertEqual(len(result.errors), 2)

    def test_recycle_exception_is_reported_not_retried_as_delete(self):
        plan = make_plan(self.report, [str(self.paths[1])])
        def fail(_path):
            raise OSError("Recycle bin unavailable")
        result = move_to_trash(self.report, plan, trash=fail)
        self.assertEqual(result.moved, [])
        self.assertIn("Recycle bin unavailable", result.errors[str(self.paths[1])])

    def test_target_symlink_rejected(self):
        plan = make_plan(self.report, [str(self.paths[1])])
        try:
            self.paths[1].unlink()
            self.paths[1].symlink_to(self.paths[2])
        except (OSError, NotImplementedError):
            self.skipTest("Cannot create symlink here")
        called = []
        result = move_to_trash(self.report, plan, trash=called.append)
        self.assertFalse(called)
        self.assertIn(str(self.paths[1]), result.errors)

    def test_switching_to_a_different_file_same_size_rejected(self):
        plan = make_plan(self.report, [str(self.paths[1])])
        self.paths[1].write_bytes(b"DIFFERENT")
        called = []
        result = move_to_trash(self.report, plan, trash=called.append)
        self.assertFalse(called)
        self.assertIn(str(self.paths[1]), result.errors)


if __name__ == "__main__":
    unittest.main()
