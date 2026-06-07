# Rokct Protocol Installer (Windows PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$ProtocolRaw = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
$InitPath = "profiles/local/initiate.py"

Write-Host "[install] Rokct Protocol Setup (Standalone)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[install] ERROR: python is required but not installed."
    exit 1
}

New-Item -ItemType Directory -Force -Path ".rokct" | Out-Null

Write-Host "[install] Fetching initiate.py from protocol..."
Invoke-WebRequest -Uri "$ProtocolRaw/$InitPath" -OutFile ".rokct/initiate.py"

Write-Host "[install] Running init..."
python .rokct/initiate.py

Write-Host "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
