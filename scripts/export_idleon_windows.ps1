Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
pip install -e .

$bundledLevelDbUtil = Join-Path $RootDir "tools\leveldbutil.exe"
if ((-not $env:IDLEON_LEVELDBUTIL) -and (Test-Path $bundledLevelDbUtil)) {
    $env:IDLEON_LEVELDBUTIL = $bundledLevelDbUtil
}

if ((-not $env:IDLEON_LEVELDBUTIL) -and (-not (Get-Command leveldbutil.exe -ErrorAction SilentlyContinue))) {
    Write-Host "leveldbutil.exe not found. Put it in tools\\leveldbutil.exe or set IDLEON_LEVELDBUTIL."
}

python -m idleon_reader --info
python -m idleon_reader --csv exports\latest
