# FileDNA — Hermes / Muse Spark 1.3 handoff

## Scope

Verify the latest FileDNA v0.1.0 compact results-first Tkinter layout, dark Windows title bar, EN/TR `?` Help, multi-selection, safe Recycle Bin workflow and freshly built EXE. The visual change keeps the scanner/cleanup engine intact. The source has already been changed in GitHub; do not redesign it again unless tests uncover a defect. Scanning stays read-only. New manual Recycle Bin cleanup is opt-in, confirm-first, and must never fall back to permanent deletion. No automated cleanup is permitted.

## Workspace / source

- Private repo: `https://github.com/canyrtcn/FileDNA`
- Target Windows checkout: `C:\Hermes_Win\AgentWorkspace\FileDNA`
- If the directory is absent, create its parent and clone with GitHub authentication; if it already contains a checkout, verify `origin` is `canyrtcn/FileDNA`, preserve any local changes, and update safely. Never delete or overwrite unrelated files.
- Read the project README and LICENSE. `.gitignore` excludes local build output, caches and reports.

## Required sequence (do not skip gates)

1. Verify the correct private repository checkout and inspect the repository structure, scanner behavior, Windows entry point, and test suite. Report any blockers before proceeding.
2. Run `scripts/test.ps1` including `tests/test_gui_ui.py`, `tests/test_gui_amber.py`, `tests/test_gui_help_titlebar.py`, `tests/test_cleanup.py`, `tests/test_gui_selection.py`, `tests/test_gui_extra.py` and new `tests/test_gui_compact.py`. Preserve local untracked `tests/test_gui_extra.py` and `tests/test_edgecases.py`, if present. Fix issues and re-run until all tests pass. Do not proceed while tests fail.
3. Add focused tests for discovered edge cases (file mutation, missing survivor, symlink/junction, permissions, recycle failures, Unicode paths, multiselect, filter and no-op on confirmation cancellation). Use an injected/mocked trash function for unit tests. Re-run tests and complete this gate before visual QA.
4. Before building, verify the results table has significantly more vertical space than the prior GUI (compact 40px buttons, 82px metrics, 48px status); test Ctrl+F to focus filter, F5 scan, F1 Help, visible keyboard focus, single-line EN/TR buttons without clipping, right-click dark menu, Treeview hover/pressed heading (never white), Ctrl+click, Shift+click, Ctrl+A keeping one copy, Ctrl+C, Delete confirmation and live case-insensitive filtering; also test a real Windows dark caption and all three title bar controls (minimize/maximize/close) without altering the OS theme. Test the `?` Help twice, active EN/TR toggle, read-only warning, Help close while scanning, then open the running GUI and compare its amber palette / rounded fields, cards, buttons, table panel and status area against the supplied design reference. Verify 950×690 and 1920×1080 at 100% and 125% DPI where permitted; explicitly disclose skipped DPI checks. Then run `scripts/build.ps1`; it must regenerate the amber PNG and ICO with `scripts/make_icon.py` and produce `dist/FileDNA.exe`. Do not proceed if a required gate fails.
5. Smoke-test the *newly built* amber executable on a temporary folder with known duplicates and unique files. For the recycle action, create fresh disposal-only fixture files, test Cancel first, then with explicit approval move ONLY those fixtures to the real Recycle Bin, verify survivor remains and that a restore is possible. Never recycle user-owned files. If safe fixture testing is not possible, stop and report a blocker. Check repeated scans/cancel during hashing, no stale events, and TR group labels after results. Verify GUI responsiveness, folder browsing, scan, stop, JSON export, `v0.1.0` in the GUI, taskbar/titlebar app icon, `EN` default, `TR` toggle, and clickable GitHub `@canyrtcn` / repository links. Check `filedna --version` or `python -m filedna --version`. Do not delete source files.
6. Report: Python version, exact test pass/fail/skip counts, visual screenshots EN/TR, specific controls checked, build log summary, EXE path/size and SHA-256, outstanding issues. Keep local changes; request approval before pushing them to GitHub. Stop before creating a public release or changing repository visibility.

## Acceptance criteria

- Size-first hashing and SHA-256 content grouping are correct.
- Scanning **never modifies files**. Manual cleanup only sends explicitly selected files to Recycle Bin after user confirmation; permanent-delete fallback is prohibited.
- Errors are not hidden; permission failures are visible in JSON.
- Existing files are unchanged before vs. after scans.
- Build produces a Windows executable that starts and works on a test folder.
- Version is visible in the title and footer; EN and TR show correct primary/secondary labels; @canyrtcn and repo URLs open correctly; PNG/ICO resources are embedded.
- Prior blue UI EXE hash and screenshots do not verify the amber/rounded redesign. Windows screenshot/EXE validation must be repeated.
- Native Tk Canvas rounded corners must be visibly real. Verify layout at 950×660, 1220×780 and maximized sizes, including minimum results table height and title/header balance.
- Generated ICO/PNG should use amber/gold, with no bright-blue legacy logo left.
- Default caption is requested dark via Windows DWM; if unsupported, log OS build and return status without calling it verified.
- Help dialog must not create leaked Tk timers, frozen windows or cross-thread Tk operations.
- Selected file references can be managed via right-click, Ctrl/Shift, Ctrl+A, Ctrl+C and Delete; multiple groups, filter state and reference-copy protection are correctly handled.
- **No actual cleanup of non-fixture files.** Recycle Bin action must preserve one real verified copy and gracefully report unsupported destinations or partial failures.
- Explicitly test that Muse's prior local GC/test-teardown stabilization remains in place and that repeated GUI tests do not produce Tcl_AsyncDelete.
- Stop if a stage cannot be completed; do not silently proceed to later stages.
- No repo publication, release, visibility change, or destructive action without explicit user approval.
