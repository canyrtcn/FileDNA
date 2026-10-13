"""Conservative, opt-in duplicate cleanup.

Scanning remains read-only. Only an explicit, confirmed user action calls
send2trash. A whole duplicate group can never be discarded: at least one
verified file must remain in its scanned location. Unavailable trash support
fails closed; there is no permanent-delete fallback.
"""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .scanner import DuplicateGroup, ScanReport

CHUNK = 1024 * 1024


class UnsafeSelection(ValueError):
    """Selection would discard a full group or contain non-scanned paths."""


@dataclass(frozen=True)
class TrashPlan:
    paths: tuple[str, ...]
    bytes_total: int


@dataclass
class TrashResult:
    moved: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def select_extra_paths(report: ScanReport) -> tuple[str, ...]:
    """Safe convenience selection: leave the first path in every group untouched."""
    return tuple(path for group in report.groups for path in group.paths[1:])


def make_plan(report: ScanReport, chosen: Iterable[str]) -> TrashPlan:
    """Reject whole-group or unknown selection without touching the file system."""
    requested = set(chosen)
    if not requested:
        raise UnsafeSelection("No files are selected")
    seen: set[str] = set()
    size_by_path: dict[str, int] = {}
    for group in report.groups:
        members = set(group.paths)
        if len(members) != len(group.paths):
            raise UnsafeSelection("Duplicate path in a scan group")
        if len(requested & members) >= len(members):
            raise UnsafeSelection("Keep at least one file in every duplicate group")
        for path in group.paths:
            if path in seen:
                raise UnsafeSelection("File appears in multiple duplicate groups")
            seen.add(path)
            size_by_path[path] = group.size_bytes
    if not requested.issubset(seen):
        raise UnsafeSelection("Selection includes a path outside the scan results")
    # Deterministic ordering from the report, not arbitrary set ordering.
    ordered = tuple(p for g in report.groups for p in g.paths if p in requested)
    return TrashPlan(ordered, sum(size_by_path[p] for p in ordered))


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError, RuntimeError):
        return False
    return True


def _verify_file(path: str, group: DuplicateGroup, root: Path) -> bool:
    item = Path(path)
    if not _within_root(item, root) or item.is_symlink() or not item.is_file():
        return False
    try:
        first = item.stat()
        if not stat.S_ISREG(first.st_mode) or first.st_size != group.size_bytes:
            return False
        digest = hashlib.sha256()
        with item.open("rb") as handle:
            start = os.fstat(handle.fileno())
            if (start.st_size != first.st_size or
                start.st_mtime_ns != first.st_mtime_ns or
                start.st_ino != first.st_ino):
                return False
            while True:
                chunk = handle.read(CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
            finish = os.fstat(handle.fileno())
        if (finish.st_size != start.st_size or
            finish.st_mtime_ns != start.st_mtime_ns or
            finish.st_ino != start.st_ino):
            return False
        return digest.hexdigest() == group.sha256
    except (OSError, ValueError):
        return False


def move_to_trash(
    report: ScanReport,
    plan: TrashPlan,
    *,
    trash: Callable[[str], None] | None = None,
) -> TrashResult:
    """Re-validate selected bytes AND a surviving copy immediately before trashing.

    Errors are accumulated without deleting further files from a group once a
    verified survivor becomes unavailable. No permanent deletion is performed.
    """
    checked = make_plan(report, plan.paths)
    if checked != plan:
        raise UnsafeSelection("Cleanup plan was modified")
    if trash is None:
        # Lazy import means read-only scanning still works if installed without
        # the cleanup dependency. Never silently fall back to os.unlink.
        try:
            from send2trash import send2trash
        except ImportError as exc:
            raise RuntimeError("Send2Trash is required for safe recycling") from exc
        trash = send2trash

    root = Path(report.root)
    groups_by_path = {p: g for g in report.groups for p in g.paths}
    selected = set(plan.paths)
    result = TrashResult()
    for filename in plan.paths:
        group = groups_by_path[filename]
        # Preserve an unselected duplicate, NOT merely any previously scanned path.
        survivors = [p for p in group.paths if p not in selected]
        if not any(_verify_file(p, group, root) for p in survivors):
            result.errors[filename] = "No unchanged matching copy remains; skipped"
            continue
        if not _verify_file(filename, group, root):
            result.errors[filename] = "File changed, moved, or became unsafe; skipped"
            continue
        # Non-atomic by nature: verify again immediately prior to the native
        # system recycling call; report a failure if recycling is unsupported.
        try:
            trash(filename)
            result.moved.append(filename)
        except (OSError, ValueError, RuntimeError) as exc:
            result.errors[filename] = str(exc)
    return result
