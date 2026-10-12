"""FileDNA command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scanner import ScanCancelled, scan_directory


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.0f} B" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find duplicate files without deleting anything.")
    parser.add_argument("directory", help="Directory to scan recursively")
    parser.add_argument("--json", dest="json_path", metavar="FILE", help="Export the report to a JSON file")
    args = parser.parse_args(argv)
    try:
        report = scan_directory(args.directory)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, ScanCancelled):
        print("Scan cancelled.", file=sys.stderr)
        return 130

    print(f"Directory: {report.root}")
    print(f"Files inspected: {report.examined_files:,}")
    print(f"Files hashed: {report.hashed_files:,}")
    print(f"Duplicate groups: {len(report.groups):,}")
    print(f"Redundant files: {report.duplicate_files:,}")
    print(f"Potentially reclaimable: {format_size(report.reclaimable_bytes)}")
    for number, group in enumerate(report.groups, 1):
        print(f"\n[{number}] {format_size(group.size_bytes)}  SHA-256: {group.sha256}")
        for path in group.paths:
            print(f"  {path}")
    if report.errors:
        print(f"\nWarnings ({len(report.errors)}):", file=sys.stderr)
        for issue in report.errors:
            print(f"- {issue['path']}: {issue['error']}", file=sys.stderr)

    if args.json_path:
        destination = Path(args.json_path)
        try:
            destination.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            print(f"Could not save JSON report: {exc}", file=sys.stderr)
            return 2
        print(f"\nJSON report: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
