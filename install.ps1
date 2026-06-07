# Rokct Protocol Installer (Windows PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$ProtocolDir = "The-Rokct-Protocol"
$RepoUrl = "https://github.com/RokctAI/The-Rokct-Protocol.git"

Write-Host "[install] Rokct Protocol Setup (Workspace Mode)"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[install] ERROR: git is required but not installed."
    exit 1
}

if (-not (Test-Path $ProtocolDir)) {
    Write-Host "[install] Cloning The-Rokct-Protocol..."
    git clone --depth 1 $RepoUrl $ProtocolDir
} else {
    Write-Host "[install] The-Rokct-Protocol already exists, pulling latest..."
    Set-Location $ProtocolDir
    git pull --ff-only
}

Write-Host "[install] Running local workspace init..."
Set-Location $ProtocolDir
python profiles/local/initiate.py

Write-Host "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
