# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

param(
    [ValidateSet("lab", "smart-contract-basic", "smart-contract-static")]
    [string]$Profile = "lab",
    [string]$VenvDir = ".venv",
    [string[]]$ManagedSolcVersions = @("0.8.20", "0.8.24", "0.8.25", "0.8.30"),
    [switch]$SkipManagedSolc,
    [switch]$RunDoctor = $true
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$localState = Join-Path $root ".ellipticzero"
$localTmp = Join-Path $localState "tmp"
$localPipCache = Join-Path $localState "pip-cache"
New-Item -ItemType Directory -Force -Path $localTmp | Out-Null
New-Item -ItemType Directory -Force -Path $localPipCache | Out-Null
$env:TMP = $localTmp
$env:TEMP = $localTmp
$env:PIP_CACHE_DIR = $localPipCache
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    throw "VenvDir must not be empty."
}

$venvPath = if ([System.IO.Path]::IsPathRooted($VenvDir)) {
    $VenvDir
} else {
    Join-Path $root $VenvDir
}

$profileExtras = @{
    "lab"                   = "lab"
    "smart-contract-basic"  = "smart_contract_basic"
    "smart-contract-static" = "smart_contract_static"
}

function Write-Step([string]$message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Preparing local environment: $venvPath"
$venvPython = Join-Path $venvPath "Scripts\\python.exe"
if (-not (Test-Path $venvPython)) {
    python -m venv $venvPath
}

$python = $venvPython

Write-Step "Upgrading pip"
& $python -m pip install --disable-pip-version-check --upgrade pip

Write-Step "Installing project profile: $Profile"
$selectedExtra = $profileExtras[$Profile]
& $python -m pip install --disable-pip-version-check -e ".[${selectedExtra}]"

if (-not $SkipManagedSolc) {
    Write-Step "Provisioning managed Solidity compiler"
    $bootstrapArgs = @(".\scripts\bootstrap_smart_contract_toolchain.py")
    foreach ($version in $ManagedSolcVersions) {
        if ($version) {
            $bootstrapArgs += @("--solc-version", $version)
        }
    }
    & $python @bootstrapArgs
}

Write-Step "Checking optional local research tools"
$sagePath = $null
try {
    $sagePath = (Get-Command sage -ErrorAction Stop).Source
} catch {
    $sagePath = $null
}

if ($sagePath) {
    Write-Host "Sage detected: $sagePath" -ForegroundColor Green
} else {
    Write-Host "Sage not detected. SymPy / Hypothesis / z3-based paths are ready; Sage remains optional." -ForegroundColor Yellow
}

if ($RunDoctor) {
    Write-Step "Running system doctor"
    & $python -m app.main --doctor
}

Write-Step "Done"
Write-Host "Local lab environment is ready in: $venvPath" -ForegroundColor Green
Write-Host "All Python-installable research dependencies are now local to this project folder." -ForegroundColor Gray
Write-Host "Run interactive console with:" -ForegroundColor Gray
Write-Host "  & `"$python`" -m app.main --interactive" -ForegroundColor White
