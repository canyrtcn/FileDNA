# FileDNA — Hermes / Muse Spark 1.3 handoff

## Scope

Verify the existing FileDNA v0.1.0 source on Windows. Do not redesign the application unless tests uncover a defect. This repo intentionally contains no auto-delete feature. Preserve the read-only safety guarantee.

## Required sequence (do not skip gates)

1. Inspect the repository structure, scanner behavior, Windows entry point, and test suite. Report any blockers before proceeding.
2. Run `scripts/test.ps1` and fix failing tests or code. Re-run until all pass. Do not proceed while tests fail.
3. Add focused tests for discovered edge cases (file mutation, insufficient permissions, Windows hardlink/symlink behavior, progress/cancellation, Unicode paths) as appropriate. Re-run tests.
4. Run `scripts/build.ps1` to create `dist/FileDNA.exe`. Do not proceed if the build fails.
5. Smoke-test the built executable on a temporary folder with known duplicates and unique files. Verify GUI responsiveness, folder browsing, scan, stop, and JSON export. Do not delete source files.
6. Report: Python version, test summary, build log summary, resulting EXE path/size, artifact hash SHA-256, observed issues, and proposed fixes. Stop before creating a public release or changing repository visibility.

## Acceptance criteria

- Size-first hashing and SHA-256 content grouping are correct.
- Files are **never deleted, moved, or renamed**.
- Errors are not hidden; permission failures are visible in JSON.
- Existing files are unchanged before vs. after scans.
- Build produces a Windows executable that starts and works on a test folder.
- No repo publication, release, visibility change, or destructive action without explicit user approval.
