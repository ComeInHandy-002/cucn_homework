param(
    [switch]$Gpu,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
Set-Location $ProjectRoot

function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File exited with code $LASTEXITCODE" }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/"
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Checked "uv" @("venv", ".venv", "--python", "3.12.13")
}
if (-not $SkipInstall) {
    $env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"
    Invoke-Checked "uv" @("pip", "install", "--python", ".venv\Scripts\python.exe", "-r", "requirements-dev.txt")
    if ($Gpu) {
        Write-Host "Installing CUDA 12.6 PyTorch wheels; this downloads several GB."
        Invoke-Checked "uv" @("pip", "install", "--python", ".venv\Scripts\python.exe", "--default-index", "https://download.pytorch.org/whl/cu126", "--index", "https://pypi.org/simple", "--index-strategy", "unsafe-best-match", "--reinstall", "torch==2.6.0+cu126", "torchvision==0.21.0+cu126")
    }
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}
Invoke-Checked ".venv\Scripts\python.exe" @("scripts\check_environment.py")
Write-Host "Environment setup complete. Start with: .venv\Scripts\python.exe -m uvicorn app.main:app --reload"
