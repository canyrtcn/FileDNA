"""Edge-case tests for the Hermes / Muse Spark verification stage.

Covers acceptance items not covered by test_scanner.py / test_cli.py:
SHA-256 correctness, multi-chunk large files, Unicode/Turkish paths,
permission failures during hashing, file mutation races, and scan integrity.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import filedna.scanner as scanner_module
from filedna.scanner import _hash_stable_file, scan_directory


class EdgeCaseTests(unittest.TestCase):
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

    def test_sha256_matches_hashlib(self) -> None:
        content = "FileDNA SHA-256 doğrulama içeriği 🧬".encode("utf-8")
        self.make("orijinal.txt", content)
        self.make("kopya.txt", content)
        report = scan_directory(self.root)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.groups[0].sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(report.groups[0].size_bytes, len(content))

    def test_large_multi_chunk_duplicates(self) -> None:
        # 3 MiB forces multi-chunk streaming (CHUNK_SIZE is 1 MiB).
        payload = os.urandom(3 * 1024 * 1024)
        first = self.make("buyuk-1.bin", payload)
        second = self.make("alt/buyuk-2.bin", payload)
        self.make("benzersiz.bin", os.urandom(3 * 1024 * 1024))
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (first, second)}
        report = scan_directory(self.root)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.groups[0].size_bytes, len(payload))
        self.assertEqual(report.groups[0].sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(report.reclaimable_bytes, len(payload))
        # Integrity: scanned files are byte-identical after the scan.
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_unicode_turkish_paths(self) -> None:
        content = "Türkçe karakterli yol testi: ğüşiöç ÜĞİŞÖÇ ıİ".encode("utf-8")
        first = self.make("Ğüşiöç Türkçe — dosya №1.txt", content)
        second = self.make("alt klasör/ÜĞİŞÖÇ ikinci dosya.txt", content)
        report = scan_directory(self.root)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.groups[0].paths, sorted([str(first), str(second)], key=str.casefold))
        # JSON round-trip must preserve the exact Unicode paths.
        payload = json.loads(json.dumps(report.to_dict(), ensure_ascii=False))
        self.assertEqual(len(payload["groups"]), 1)
        self.assertIn(str(first), payload["groups"][0]["paths"])
        self.assertIn(str(second), payload["groups"][0]["paths"])
        for key in ("root", "scanned_at", "examined_files", "groups", "errors",
                    "duplicate_files", "reclaimable_bytes"):
            self.assertIn(key, payload)

    def test_hash_permission_error_is_reported(self) -> None:
        self.make("ok1.bin", b"shared-bytes-1234!")
        self.make("ok2.bin", b"shared-bytes-1234!")
        locked = self.make("locked.bin", b"shared-bytes-1234!")
        real_open = os.open

        def fake_open(path, flags, *args, **kwargs):
            if os.fspath(path) == str(locked):
                raise PermissionError(13, "Permission denied", os.fspath(path))
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(scanner_module.os, "open", side_effect=fake_open):
            report = scan_directory(self.root)
        # Healthy files are still grouped; the failure is visible, not hidden.
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.duplicate_files, 1)
        self.assertTrue(any("locked.bin" in entry["path"] for entry in report.errors))
        payload = report.to_dict()
        self.assertTrue(any("locked.bin" in entry["path"] for entry in payload["errors"]))

    def test_stale_stat_rejected_before_hashing(self) -> None:
        target = self.make("race.bin", b"A" * 100)
        stale = target.stat()
        target.write_bytes(b"B" * 100)  # same size, new content and mtime
        # NTFS can coalesce rapid rewrites onto one timestamp tick, which would
        # make the race undetectable by stat; force a distinct mtime so the test
        # deterministically exercises the stale-stat rejection path.
        os.utime(target, ns=(stale.st_atime_ns, stale.st_mtime_ns + 2_000_000_000))
        with self.assertRaises(OSError):
            _hash_stable_file(target, stale, None)

    def test_mutation_during_scan_excluded(self) -> None:
        first = self.make("a.bin", b"Z" * 64)
        second = self.make("b.bin", b"Z" * 64)
        real_hash = scanner_module._hash_stable_file
        mutated = {"done": False}

        def mutating_hash(path, expected, cancelled):
            if not mutated["done"]:
                mutated["done"] = True
                # Change the not-yet-hashed file (same size, new content).
                second.write_bytes(b"Q" * 64)
                # Force a distinct mtime: rapid rewrites can share a timestamp
                # tick, which stat-based race detection cannot observe.
                fresh = second.stat()
                os.utime(second, ns=(fresh.st_atime_ns, fresh.st_mtime_ns + 2_000_000_000))
            return real_hash(path, expected, cancelled)

        with mock.patch.object(scanner_module, "_hash_stable_file", side_effect=mutating_hash):
            report = scan_directory(self.root)
        self.assertTrue(mutated["done"])
        # The changed file must not form a group; the incident must be reported.
        self.assertEqual(report.groups, [])
        self.assertTrue(report.errors)
        self.assertEqual(report.examined_files, 2)
        # Scanner never repairs or rewrites: the mutated content stays as written.
        self.assertEqual(second.read_bytes(), b"Q" * 64)
        self.assertEqual(first.read_bytes(), b"Z" * 64)


if __name__ == "__main__":
    unittest.main()
