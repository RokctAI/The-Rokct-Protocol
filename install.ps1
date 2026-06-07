# Rokct Protocol Installer (Windows PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$ProtocolRaw = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"

Write-Host "[install] Rokct Protocol Setup"
Write-Host "Select profile:"
Write-Host "  1) Local (desktop/CLI)"
Write-Host "  2) Web (cloud sandbox / AI agent)"
$choice = Read-Host "Enter 1 or 2"

switch ($choice) {
    { $_ -eq "2" } { $Profile = "web" }
    default { $Profile = "local" }
}

$InitFile = "profiles/$Profile/initiate.py"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[install] ERROR: python is required but not installed."
    exit 1
}

New-Item -ItemType Directory -Force -Path ".rokct" | Out-Null

Write-Host "[install] Fetching $Profile initiate.py from protocol..."
Invoke-WebRequest -Uri "$ProtocolRaw/$InitFile" -OutFile ".rokct/initiate.py"

Write-Host "[install] Running init..."
python .rokct/initiate.py

Write-Host "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
