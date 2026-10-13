# Run the FileDNA unit and GUI regression suite on Windows.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
}
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
# Block test/build continuation if tracked source contains obvious secrets or local artifacts.
& $python scripts\check_repo.py
if ($LASTEXITCODE -ne 0) { throw 'Repository security check failed' }
& $python -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw 'Package install failed' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
