"""Release hygiene check for tracked source files.

Runs without third-party packages. This is a precautionary pattern scan, not a
substitute for credential rotation or an audit of all historical git objects.
It deliberately reports locations without printing candidate secret values.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENSITIVE_NAMES = {
    ".env", ".env.local", ".env.production", ".envrc",
    "credentials.json", "secrets.json", "report.json",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".har"}

CHECKS = (
    (
        "credential signature",
        re.compile(
            r"(?:sk-[A-Za-z0-9_-]{16,}|"
            r"gh[pousr]_[A-Za-z0-9]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,}|"
            r"AKIA[A-Z0-9]{16}|"
            r"AIza[0-9A-Za-z_-]{35}|"
            r"xox[baprs]-[A-Za-z0-9-]{10,}|"
            r"\b[0-9]{8,10}:[A-Za-z0-9_-]{30,}\b)"
        ),
    ),
    (
        "private key marker",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    ),
    (
        "literal credential assignment",
        re.compile(
            r"\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|password|passwd)"
            r"\s*[:=]\s*['\"][A-Za-z0-9/+=._:-]{16,}['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "machine-specific user path",
        re.compile(
            r"\b[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]"
            r"[^\\/<>:\"'\s]+",
            re.IGNORECASE,
        ),
    ),
    (
        "machine-specific workspace path",
        re.compile(
            r"\b[A-Za-z]:[\\/][^\\/<>:\"'\s]+[\\/]"
            r"[^\\/<>:\"'\s]+[\\/]",
            re.IGNORECASE,
        ),
    ),
)


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    )
    return [
        ROOT / path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\x00") if path
    ]


def inspect(path: Path) -> list[tuple[str, int]]:
    relative = path.relative_to(ROOT)
    name = relative.name.casefold()
    errors: list[tuple[str, int]] = []
    if (
        name in SENSITIVE_NAMES
        or relative.suffix.casefold() in SENSITIVE_SUFFIXES
        or (name.startswith("filedna-report") and name.endswith(".json"))
        or "handoff" in name
    ):
        errors.append(("private/generated file tracked", 0))
    data = path.read_bytes()
    if b"\x00" in data:
        errors.append(("binary file requires separate review", 0))
        return errors
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(("non-UTF-8 source requires separate review", 0))
        return errors
    for line_no, line in enumerate(source.splitlines(), 1):
        for label, pattern in CHECKS:
            if pattern.search(line):
                errors.append((label, line_no))
    return errors


def main() -> int:
    try:
        files = tracked_paths()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Repository audit unavailable: {type(exc).__name__}", file=sys.stderr)
        return 2

    findings = []
    for path in files:
        try:
            for label, line_no in inspect(path):
                findings.append((path.relative_to(ROOT), line_no, label))
        except OSError:
            findings.append((path.relative_to(ROOT), 0, "unreadable tracked file"))

    for file, line_no, label in findings:
        location = f"{file}:{line_no}" if line_no else str(file)
        print(f"CHECK: {location}: {label}", file=sys.stderr)
    if findings:
        print(f"Repository check blocked: {len(findings)} finding(s).", file=sys.stderr)
        return 1
    print(f"Repository check passed: {len(files)} tracked files reviewed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
