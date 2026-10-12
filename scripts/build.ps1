# Standalone Windows GUI EXE build with a dedicated FileDNA icon.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
}
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m pip install -e . pyinstaller pillow
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }

& $python scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'FileDNA icon generation failed' }
$icon = Join-Path (Get-Location) 'assets\filedna.ico'
$assets = Join-Path (Get-Location) 'assets'
if (-not (Test-Path $icon)) { throw "Missing icon: $icon" }

$pyArgs = @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
    '--windowed', '--name', 'FileDNA', '--paths', 'src',
    '--icon', "$icon", '--add-data', ($assets + ';assets'), 'run.py')
& $python @pyArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host "EXE generated: $(Join-Path (Get-Location) 'dist\FileDNA.exe')"
