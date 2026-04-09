Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$OutputDir = if ($args.Count -ge 1) { $args[0] } else { "exports\latest" }
$AppendMode = if ($args.Count -ge 2) { $args[1] } else { "" }

if (-not (Test-Path ".venv")) {
    powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1 | Out-Null
}

. .\.venv\Scripts\Activate.ps1
python -c "import idleon_reader" 2>$null
if ($LASTEXITCODE -ne 0) {
    python -m pip install -e . | Out-Null
}

$cmd = @("-m", "idleon_reader", "--csv", $OutputDir)
if ($AppendMode -eq "--append") {
    $cmd += "--append"
}

python @cmd
