"""CLI tests. Intended for the Hermes/Muse verification stage."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from filedna import __version__
from filedna.cli import format_size, main


class CLITests(unittest.TestCase):
    def test_version_without_directory(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit_ctx:
            main(["--version"])
        self.assertEqual(exit_ctx.exception.code, 0)
        self.assertIn(f"FileDNA {__version__}", output.getvalue())

    def test_byte_formatting(self) -> None:
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1024), "1.00 KiB")

    def test_scan_and_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").write_bytes(b"duplicate")
            (root / "b").write_bytes(b"duplicate")
            output = root / "report.json"
            self.assertEqual(main([str(root), "--json", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["duplicate_files"], 1)

    def test_missing_root_returns_error_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main([str(Path(tmp) / "nope")]), 2)


if __name__ == "__main__":
    unittest.main()
