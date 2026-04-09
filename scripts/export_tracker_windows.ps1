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
    Invoke-NativeOrThrow powershell -ExecutionPolicy Bypass -File .\scripts\install_tracker_windows.ps1
}

if (-not (Test-Path ".venv")) {
    throw "Virtual environment directory is missing after installation: $RootDir\.venv"
}

$ActivateScript = Join-Path $RootDir ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    throw "Virtual environment activation script not found: $ActivateScript"
}

. $ActivateScript
try {
    Invoke-NativeOrThrow python -c "import idleon_reader"
}
catch {
    Invoke-NativeOrThrow python -m pip install -e .
}

$cmd = @("-m", "idleon_reader", "--csv", $OutputDir) + $ExtraArgs

Invoke-NativeOrThrow python @cmd
