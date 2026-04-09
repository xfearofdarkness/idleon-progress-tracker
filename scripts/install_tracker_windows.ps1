Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeOrThrow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE: $Command $($Arguments -join ' ')"
    }
}

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' not found."
}

if (-not (Test-Path ".venv")) {
    Invoke-NativeOrThrow py -3 -m venv .venv
}

if (-not (Test-Path ".venv")) {
    throw "Virtual environment directory was not created: $RootDir\.venv"
}

$ActivateScript = Join-Path $RootDir ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    throw "Virtual environment activation script not found: $ActivateScript"
}

. $ActivateScript

Invoke-NativeOrThrow python -m pip install --upgrade pip setuptools wheel
Invoke-NativeOrThrow python -m pip install -e .

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
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\export_tracker_windows.ps1"
