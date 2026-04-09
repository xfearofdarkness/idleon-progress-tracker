Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' not found."
}

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel | Out-Null
python -m pip install -e . | Out-Null

$bundledLevelDbUtil = Join-Path $RootDir "tools\leveldbutil.exe"
if ((-not $env:IDLEON_LEVELDBUTIL) -and (Test-Path $bundledLevelDbUtil)) {
    $env:IDLEON_LEVELDBUTIL = $bundledLevelDbUtil
}

Write-Host "== IdleOn Tracker installed =="
Write-Host "Virtual environment: $RootDir\.venv"
Write-Host ""

if (-not (Test-Path $bundledLevelDbUtil) -and (-not (Get-Command leveldbutil.exe -ErrorAction SilentlyContinue))) {
    Write-Host "leveldbutil.exe not found."
    Write-Host "Place it in tools\leveldbutil.exe or set IDLEON_LEVELDBUTIL."
    Write-Host ""
}

Write-Host "Next steps:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python -m idleon_reader --info"
Write-Host "  python -m idleon_reader"
Write-Host "  python -m idleon_reader --csv exports\latest"
