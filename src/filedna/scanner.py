"""Read-only duplicate detection engine.

Files are bucketed by byte size before hashing, which avoids reading files
whose size is unique. Symlinks and extra hardlink names are not counted as
independent copies. Files that change during hashing are excluded.
"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Callable

CHUNK_SIZE = 1024 * 1024
ProgressCallback = Callable[[str, int, int], None]


class ScanCancelled(Exception):
    """Raised if cancellation was requested."""


@dataclass(frozen=True)
class DuplicateGroup:
    sha256: str
    size_bytes: int
    paths: list[str]

    @property
    def reclaimable_bytes(self) -> int:
        return self.size_bytes * (len(self.paths) - 1)


@dataclass
class ScanReport:
    root: str
    scanned_at: str
    examined_files: int = 0
    candidate_files: int = 0
    hashed_files: int = 0
    skipped_symlinks: int = 0
    skipped_hardlinks: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    groups: list[DuplicateGroup] = field(default_factory=list)

    @property
    def duplicate_files(self) -> int:
        return sum(len(g.paths) - 1 for g in self.groups)

    @property
    def reclaimable_bytes(self) -> int:
        return sum(g.reclaimable_bytes for g in self.groups)

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "groups"},
            "duplicate_files": self.duplicate_files,
            "reclaimable_bytes": self.reclaimable_bytes,
            "groups": [
                {
                    "sha256": g.sha256,
                    "size_bytes": g.size_bytes,
                    "reclaimable_bytes": g.reclaimable_bytes,
                    "paths": g.paths,
                }
                for g in self.groups
            ],
        }


def _changed(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_size != second.st_size
        or first.st_mtime_ns != second.st_mtime_ns
        or (first.st_ino and second.st_ino and first.st_ino != second.st_ino)
        or first.st_dev != second.st_dev
    )


def _hash_stable_file(path: Path, expected: os.stat_result, cancelled: Event | None) -> str:
    # Open first, then compare the opened descriptor against the initial stat;
    # this detects common file-replacement races before reading.
    digest = hashlib.sha256()
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | nofollow
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            before = os.fstat(handle.fileno())
            if _changed(expected, before):
                raise OSError("File changed since discovery")
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise ScanCancelled()
                data = handle.read(CHUNK_SIZE)
                if not data:
                    break
                digest.update(data)
            after = os.fstat(handle.fileno())
            if _changed(before, after):
                raise OSError("File changed while hashing")
    finally:
        if fd >= 0:
            os.close(fd)
    return digest.hexdigest()


def scan_directory(
    root: str | Path,
    *,
    cancel_event: Event | None = None,
    progress: ProgressCallback | None = None,
) -> ScanReport:
    """Scan a directory without modifying files.

    progress receives (phase, current, total), with total=0 during discovery.
    Raises ScanCancelled on cancellation; unexpected filesystem errors are
    collected in report.errors so that other files can still be processed.
    """
    directory = Path(root).expanduser().absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Choose an existing directory that is not a symlink")

    report = ScanReport(root=str(directory), scanned_at=datetime.now(timezone.utc).isoformat())
    by_size: dict[int, list[tuple[Path, os.stat_result]]] = defaultdict(list)
    seen_inodes: set[tuple[int, int]] = set()

    def check_cancel() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled()

    def announce(phase: str, current: int, total: int = 0) -> None:
        if progress is not None:
            progress(phase, current, total)

    def walk_error(exc: OSError) -> None:
        report.errors.append({"path": str(exc.filename or directory), "error": str(exc)})

    announce("discovering", 0)
    for folder, subdirs, files in os.walk(directory, followlinks=False, onerror=walk_error):
        check_cancel()
        base = Path(folder)
        # Symlinked subdirectories must not be traversed.
        safe_dirs = []
        for name in subdirs:
            child = base / name
            if child.is_symlink():
                report.skipped_symlinks += 1
            else:
                safe_dirs.append(name)
        subdirs[:] = safe_dirs

        for filename in files:
            check_cancel()
            path = base / filename
            try:
                if path.is_symlink():
                    report.skipped_symlinks += 1
                    continue
                stat = path.stat()
                if not path.is_file():
                    continue
                inode = (stat.st_dev, stat.st_ino)
                if stat.st_ino and inode in seen_inodes:
                    report.skipped_hardlinks += 1
                    continue
                if stat.st_ino:
                    seen_inodes.add(inode)
                report.examined_files += 1
                by_size[stat.st_size].append((path, stat))
            except OSError as exc:
                report.errors.append({"path": str(path), "error": str(exc)})
            if report.examined_files % 50 == 0:
                announce("discovering", report.examined_files)

    candidates = [
        (path, original)
        for same_size in by_size.values()
        if len(same_size) > 1
        for path, original in same_size
    ]
    report.candidate_files = len(candidates)
    by_identity: dict[tuple[int, str], list[str]] = defaultdict(list)
    total = len(candidates)
    announce("hashing", 0, total)
    for index, (path, original) in enumerate(candidates, 1):
        check_cancel()
        try:
            digest = _hash_stable_file(path, original, cancel_event)
            report.hashed_files += 1
            by_identity[(original.st_size, digest)].append(str(path))
        except ScanCancelled:
            raise
        except OSError as exc:
            report.errors.append({"path": str(path), "error": str(exc)})
        announce("hashing", index, total)

    report.groups = sorted(
        [
            DuplicateGroup(
                sha256=digest,
                size_bytes=size,
                paths=sorted(paths, key=str.casefold),
            )
            for (size, digest), paths in by_identity.items()
            if len(paths) > 1
        ],
        key=lambda group: (-group.reclaimable_bytes, group.paths[0].casefold()),
    )
    announce("complete", total, total)
    return report
