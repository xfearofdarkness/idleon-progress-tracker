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
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
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

function Remove-VenvIfPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RootPath
    )

    $venvPath = Join-Path $RootPath ".venv"
    if (Test-Path $venvPath) {
        Remove-Item -Recurse -Force $venvPath
    }
}

function Get-VenvCandidates {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += @{
            Command = "py"
            Arguments = @("-3", "-m", "venv", ".venv")
            Label = "py -3"
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += @{
            Command = "python"
            Arguments = @("-m", "venv", ".venv")
            Label = "python"
        }
    }
    return $candidates
}

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Candidates = Get-VenvCandidates
if ($Candidates.Count -eq 0) {
    throw "Neither 'py' nor 'python' was found on PATH."
}

if (-not (Test-WindowsVenv $RootDir)) {
    $existingBinPython = Join-Path $RootDir ".venv\bin\python"
    if (Test-Path (Join-Path $RootDir ".venv")) {
        Write-Host "Existing virtual environment is missing Windows Scripts/ and will be recreated."
        if (Test-Path $existingBinPython) {
            Write-Host "Detected a POSIX-style venv (.venv\\bin\\python), likely created by a non-Windows Python."
        }
    }

    $created = $false
    foreach ($candidate in $Candidates) {
        Remove-VenvIfPresent $RootDir
        try {
            Invoke-NativeOrThrow $candidate.Command @($candidate.Arguments)
        }
        catch {
            continue
        }

        if (Test-WindowsVenv $RootDir) {
            $created = $true
            break
        }
    }

    if (-not $created) {
        $candidateLabels = ($Candidates | ForEach-Object { $_.Label }) -join ", "
        throw "Could not create a Windows-compatible virtual environment with: $candidateLabels"
    }
}

if (-not (Test-WindowsVenv $RootDir)) {
    throw "Windows virtual environment is invalid: $RootDir\.venv"
}

$ActivateScript = Join-Path $RootDir ".venv\Scripts\Activate.ps1"
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
