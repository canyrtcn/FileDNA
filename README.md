# FileDNA

![FileDNA icon](assets/filedna.svg)

**Find duplicate files by content, not by filename.**

FileDNA is a lightweight, read-only duplicate file finder for Windows with a clean desktop GUI and a scriptable CLI. It groups files by size first and only computes SHA-256 hashes for files that *could* be duplicates.

> **Status:** v0.1.0 source candidate. Windows executable build and test execution are reserved for the separate Hermes / Muse Spark validation stage. This is **not yet a verified release**.

## Features

- **Content-based detection:** different filenames, same bytes, same group.
- **Efficient scanning:** checks file sizes first and hashes only candidates, in 1 MiB streaming chunks.
- **Read-only operation:** never deletes, moves, renames, or modifies scanned files.
- **Windows-friendly GUI:** graphite dark theme, responsive cards, background scanning, cancellation, result groups, progress, and JSON export.
- **English-first interface:** EN by default, optional Turkish (TR) toggle; the alternate language appears as a smaller helper label.
- **CLI and machine-readable JSON:** useful for automation and later integration.
- **Project identity:** the desktop footer displays the version and clickable links to [@canyrtcn](https://github.com/canyrtcn) and the [FileDNA repository](https://github.com/canyrtcn/FileDNA).
- **Filesystem awareness:** skips symbolic links and does not treat additional hardlink names as new physical copies.
- **Basic race protection:** rejects files that change during scanning or hashing.
- **Transparent warnings:** unreadable files and folders are reported; scans with errors should not be treated as complete.

## Quick start

**Run the GUI directly (no third-party Python dependencies):**

The Python interface uses Tkinter; without an icon build, the application shows a simple built-in fallback icon. The Windows build generates the complete FileDNA icon automatically.

```powershell
py -3 run.py
```

Or install the package in editable mode (requires setuptools):

```powershell
py -3 -m pip install -e .
filedna-gui
filedna --version
filedna "C:\Users\YourName\Downloads" --json report.json
```

**Command line without installation** (from the repo root):

```powershell
$env:PYTHONPATH = 'src'
py -3 -m filedna "C:\Users\YourName\Downloads" --json report.json
```

## Windows icon and standalone build

The vector icon source is [`assets/filedna.svg`](assets/filedna.svg). The deterministic Pillow-based generator `scripts/make_icon.py` creates `assets/filedna.png` and multi-resolution `assets/filedna.ico`. `scripts/build.ps1` installs the *build-only* dependency Pillow, generates these assets, then bundles both into the PyInstaller executable (`--icon` and `--add-data`). No third-party GUI dependency is required when running the executable.

Run on Windows:

```powershell
.\scripts\test.ps1
.\scripts\build.ps1
```

Source-code tests can also be run with `python -m unittest discover -s tests -v`. GUI integration tests skip if no graphical display is available.

## About and links

The application window title and footer display the current version from `src/filedna/__init__.py` (currently `0.1.0`). Two footer links (including the visible username **@canyrtcn**) open the [GitHub author profile](https://github.com/canyrtcn) and the [private source repository](https://github.com/canyrtcn/FileDNA) in the default browser. The repository link requires a GitHub account with access while the project remains private.

## How it works

```mermaid
flowchart TD
  A[Select directory] --> B[Recursive file discovery]
  B --> C[Skip symlinks and hardlink aliases]
  C --> D[Group files by exact byte size]
  D --> E{Size group has 2+ files?}
  E -- No --> F[No hashing needed]
  E -- Yes --> G[Stream SHA-256 content]
  G --> H[Check file stability]
  H --> I[Group matching size + SHA-256]
  I --> J[Display results and export JSON]
```

The *potentially reclaimable* space is calculated as `size × (number of independent matching files − 1)` per group. This is an **estimate**, not a deletion instruction. FileDNA makes no determination about which copy should be retained.

## Project layout

```text
FileDNA/
├── run.py                    # GUI entry point / PyInstaller target
├── src/filedna/
│   ├── scanner.py            # Read-only duplicate-finding engine
│   ├── gui.py                # Tkinter desktop application
│   ├── cli.py                # CLI + report export
│   └── __main__.py           # python -m filedna
├── tests/                    # unittest coverage
├── scripts/
│   ├── test.ps1              # Windows testing script (for Hermes)
│   ├── make_icon.py          # Generates PNG + ICO from vector-inspired geometry
│   └── build.ps1             # Windows PyInstaller build (for Hermes)
├── assets/filedna.svg       # Vector icon source
└── pyproject.toml
```

## Testing & packaging (next stage: Hermes / Muse Spark)

The core application was previously validated on Windows by Hermes / Muse Spark, but **the redesigned GUI, localization and new icon-enabled build still require a fresh Windows validation**. Do not reuse older EXE test results as proof for the new interface. Required:

```powershell
.\scripts\test.ps1
.\scripts\build.ps1
```

Expected executable location once the build succeeds: `dist\FileDNA.exe`.

### Suggested acceptance checklist

- Same-content files with different filenames are grouped together.
- Files with the same size but different contents are not grouped.
- Empty files, nested folders, and unreadable files are handled.
- Symlink targets and hardlink aliases do not inflate reclaimable space.
- Cancel during hashing stops the scan without changing files.
- The GUI stays responsive during large scans.
- JSON contains groups, SHA-256, warnings, and totals.
- The Windows `.exe` launches without a console and can scan a sample directory.
- The taskbar/title bar display the actual FileDNA ICO, English is selected by default, TR switches labels, and GitHub @canyrtcn / Repository links work.
- Compare `report.json` output from Python and the GUI export.
- Review permissions, UNC/network paths, long paths, and Unicode names.

## Limitations and safety

- **No cleanup action is offered.** Results are advisory; deleting duplicates safely is a separate problem.
- A successful SHA-256 match is extremely strong evidence of identical content, but the tool does not perform an additional byte-for-byte verification pass after hashing.
- Files can be changing while a directory is being traversed. FileDNA performs basic stat checks, not a filesystem snapshot; race conditions remain possible.
- Symbolic links are skipped. Hardlink aliases on the same device are skipped where inode information is available.
- Protected directories can produce access errors. Review the report's `errors` list before trusting the scan as exhaustive.
- Exported JSON can contain **full personal file paths**. Treat reports as private; do not post sample reports from your real machine publicly.
- Scanning external drives or network shares may be slow. Large files are streamed rather than loaded fully into memory.

## License

MIT License. See [LICENSE](LICENSE). Packaging output, virtual environments, caches and local reports are excluded using [.gitignore](.gitignore).

## Repository

Private GitHub repository: [`canyrtcn/FileDNA`](https://github.com/canyrtcn/FileDNA). For the Hermes / Muse Spark verification stage on Windows, clone the repository to `C:\Hermes_Win\AgentWorkspace\FileDNA` before running `scripts/test.ps1` and `scripts/build.ps1`. These scripts have **not** yet been verified on Windows.
