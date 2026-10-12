# FileDNA — Hermes / Muse Spark 1.3 handoff

## Scope

Verify the newly redesigned FileDNA v0.1.0 English/Turkish GUI, icon and build on Windows. The source has already been changed in GitHub; do not redesign it again unless tests uncover a defect. This repo intentionally contains no auto-delete feature. Preserve the read-only safety guarantee.

## Workspace / source

- Private repo: `https://github.com/canyrtcn/FileDNA`
- Target Windows checkout: `C:\Hermes_Win\AgentWorkspace\FileDNA`
- If the directory is absent, create its parent and clone with GitHub authentication; if it already contains a checkout, verify `origin` is `canyrtcn/FileDNA`, preserve any local changes, and update safely. Never delete or overwrite unrelated files.
- Read the project README and LICENSE. `.gitignore` excludes local build output, caches and reports.

## Required sequence (do not skip gates)

1. Verify the correct private repository checkout and inspect the repository structure, scanner behavior, Windows entry point, and test suite. Report any blockers before proceeding.
2. Install and run `scripts/test.ps1` including `tests/test_gui_ui.py` and fix failing tests or code. Re-run until all pass. Do not proceed while tests fail.
3. Add focused tests for discovered edge cases (file mutation, insufficient permissions, Windows hardlink/symlink behavior, progress/cancellation, Unicode paths) as appropriate. Re-run tests.
4. Run `scripts/build.ps1`. It must generate the PNG and ICO using `scripts/make_icon.py`, then create `dist/FileDNA.exe` with both assets embedded. Do not proceed if the build fails.
5. Smoke-test the *newly built* executable on a temporary folder with known duplicates and unique files. Verify GUI responsiveness, folder browsing, scan, stop, JSON export, `v0.1.0` in the GUI, taskbar/titlebar app icon, `EN` default, `TR` toggle, and clickable GitHub `@canyrtcn` / repository links. Check `filedna --version` or `python -m filedna --version`. Do not delete source files.
6. Report: Python version, test summary, build log summary, resulting EXE path/size, artifact hash SHA-256, observed issues, and proposed fixes. Stop before creating a public release or changing repository visibility.

## Acceptance criteria

- Size-first hashing and SHA-256 content grouping are correct.
- Files are **never deleted, moved, or renamed**.
- Errors are not hidden; permission failures are visible in JSON.
- Existing files are unchanged before vs. after scans.
- Build produces a Windows executable that starts and works on a test folder.
- Version is visible in the title and footer; EN and TR show correct primary/secondary labels; @canyrtcn and repo URLs open correctly; PNG/ICO resources are embedded.
- Previous EXE hash and GUI test reports apply only to the old UI, not this redesigned version.
- Stop if a stage cannot be completed; do not silently proceed to later stages.
- No repo publication, release, visibility change, or destructive action without explicit user approval.
