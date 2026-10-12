# Intended for Windows PowerShell, run from any current directory.
# Requires Python 3.10+ and internet for first-time dependency installation.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
}
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
& $python -m pip install -e . pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name FileDNA --paths src run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host "EXE generated: $(Join-Path (Get-Location) 'dist\FileDNA.exe')"
