"""FileDNA — read-only duplicate file detection."""

from .scanner import DuplicateGroup, ScanCancelled, ScanReport, scan_directory

__version__ = "0.1.0"
__all__ = ["DuplicateGroup", "ScanCancelled", "ScanReport", "scan_directory"]
