Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeOrThrow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [string[]] $Arguments = @()
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

function Get-PythonCommandSource {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return ""
    }
    return $command.Source
}

function Assert-UsablePython {
    $pythonSource = Get-PythonCommandSource
    if (-not $pythonSource) {
        throw "'python' was not found on PATH. Install Python 3.10+ and reopen PowerShell."
    }

    & python --version *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    if ($pythonSource -like "*WindowsApps*") {
        throw (
            "'python' currently points to the Microsoft Store alias ($pythonSource). " +
            "Install a real Python 3.10+ and disable the App execution aliases for python.exe/python3.exe " +
            "under Settings > Apps > Advanced app settings > App execution aliases."
        )
    }

    throw "'python' is on PATH but not usable: $pythonSource"
}

function Test-WindowsVenv {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RootPath
    )

    $activateScript = Join-Path $RootPath ".venv\Scripts\Activate.ps1"
    $pythonExe = Join-Path $RootPath ".venv\Scripts\python.exe"
    return (Test-Path $activateScript) -and (Test-Path $pythonExe)
}

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Assert-UsablePython

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

if (-not (Test-WindowsVenv $RootDir)) {
    Invoke-NativeOrThrow -Command powershell -Arguments @("-ExecutionPolicy", "Bypass", "-File", ".\\scripts\\install_tracker_windows.ps1")
}

$ActivateScript = Join-Path $RootDir ".venv\Scripts\Activate.ps1"
if (-not (Test-WindowsVenv $RootDir)) {
    throw "Windows virtual environment is invalid after installation: $RootDir\.venv"
}

. $ActivateScript
try {
    Invoke-NativeOrThrow -Command python -Arguments @("-c", "import idleon_reader")
}
catch {
    Invoke-NativeOrThrow -Command python -Arguments @("-m", "pip", "install", "-e", ".")
}

$cmd = @("-m", "idleon_reader", "--csv", $OutputDir) + $ExtraArgs

Invoke-NativeOrThrow -Command python -Arguments $cmd
