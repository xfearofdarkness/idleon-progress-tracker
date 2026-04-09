Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$OutputDir = "exports\latest"
$ExtraArgs = @()
if ($args.Count -ge 1 -and -not $args[0].StartsWith("--")) {
    $OutputDir = $args[0]
    if ($args.Count -ge 2) {
        $ExtraArgs = $args[1..($args.Count - 1)]
    }
}
elseif ($args.Count -ge 1) {
    $ExtraArgs = $args
}

if (-not (Test-Path ".venv")) {
    powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1 | Out-Null
}

. .\.venv\Scripts\Activate.ps1
python -c "import idleon_reader" 2>$null
if ($LASTEXITCODE -ne 0) {
    python -m pip install -e . | Out-Null
}

$cmd = @("-m", "idleon_reader", "--csv", $OutputDir) + $ExtraArgs

python @cmd
