# FileDNA — Hermes / Muse Spark 1.3 handoff

## Scope

Verify the amber/graphite v0.1.0 redesign, rounded Tk Canvas controls, bilingual GUI, refreshed amber icon and newly built EXE on Windows. The source has already been changed in GitHub; do not redesign it again unless tests uncover a defect. This repo intentionally contains no auto-delete feature. Preserve the read-only safety guarantee.

## Workspace / source

- Private repo: `https://github.com/canyrtcn/FileDNA`
- Target Windows checkout: `C:\Hermes_Win\AgentWorkspace\FileDNA`
- If the directory is absent, create its parent and clone with GitHub authentication; if it already contains a checkout, verify `origin` is `canyrtcn/FileDNA`, preserve any local changes, and update safely. Never delete or overwrite unrelated files.
- Read the project README and LICENSE. `.gitignore` excludes local build output, caches and reports.

## Required sequence (do not skip gates)

1. Verify the correct private repository checkout and inspect the repository structure, scanner behavior, Windows entry point, and test suite. Report any blockers before proceeding.
2. Run `scripts/test.ps1` including `tests/test_gui_ui.py` and new `tests/test_gui_amber.py`. Preserve local untracked `tests/test_gui_extra.py` and `tests/test_edgecases.py`, if present. Fix issues and re-run until all tests pass. Do not proceed while tests fail.
3. Add focused tests for discovered edge cases (file mutation, insufficient permissions, Windows hardlink/symlink behavior, progress/cancellation, Unicode paths) as appropriate. Re-run tests.
4. Before building, open the running GUI and compare its amber palette / rounded fields, cards, buttons, table panel and status area against the supplied design reference. Verify 950×690 and 1920×1080 at 100% and 125% DPI where permitted; explicitly disclose skipped DPI checks. Then run `scripts/build.ps1`; it must regenerate the amber PNG and ICO with `scripts/make_icon.py` and produce `dist/FileDNA.exe`. Do not proceed if a required gate fails.
5. Smoke-test the *newly built* amber executable on a temporary folder with known duplicates and unique files. Verify GUI responsiveness, folder browsing, scan, stop, JSON export, `v0.1.0` in the GUI, taskbar/titlebar app icon, `EN` default, `TR` toggle, and clickable GitHub `@canyrtcn` / repository links. Check `filedna --version` or `python -m filedna --version`. Do not delete source files.
6. Report: Python version, exact test pass/fail/skip counts, visual screenshots EN/TR, specific controls checked, build log summary, EXE path/size and SHA-256, outstanding issues. Keep local changes; request approval before pushing them to GitHub. Stop before creating a public release or changing repository visibility.

## Acceptance criteria

- Size-first hashing and SHA-256 content grouping are correct.
- Files are **never deleted, moved, or renamed**.
- Errors are not hidden; permission failures are visible in JSON.
- Existing files are unchanged before vs. after scans.
- Build produces a Windows executable that starts and works on a test folder.
- Version is visible in the title and footer; EN and TR show correct primary/secondary labels; @canyrtcn and repo URLs open correctly; PNG/ICO resources are embedded.
- Prior blue UI EXE hash and screenshots do not verify the amber/rounded redesign. Windows screenshot/EXE validation must be repeated.
- Native Tk Canvas rounded corners must be visibly real, not merely color-swapped square frames.
- Generated ICO/PNG should use amber/gold, with no bright-blue legacy logo left.
- Stop if a stage cannot be completed; do not silently proceed to later stages.
- No repo publication, release, visibility change, or destructive action without explicit user approval.
