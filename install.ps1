# Rokct Protocol Installer (Windows PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
# The initiate.py fetch is pinned to this commit and its SHA-256 is verified
# before it is executed; a mismatch aborts the install.
$ProtocolRef = "15f0befa044853caa915597e6921d7f98d3a4fbb"
$InitiateSha256Local = "1559fcdb3af8c62d6dfc289079261129d374e75361884ebe7f870763da675a2b"
$InitiateSha256Web = "4886115ceb5ba8212521c421afda6590749cec9458ce32164886f196e09617b8"

$ProtocolRaw = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/$ProtocolRef"

Write-Host "[install] Rokct Protocol Setup"
Write-Host "Are you a Human or an Agent?"
Write-Host "  H) Human"
Write-Host "  A) Agent"
$userType = Read-Host "Enter H or A"

if ($userType -eq "H") {
    $RokctProfile = "local"
}
elseif ($userType -eq "A") {
    Write-Host "Select Agent profile:"
    Write-Host "  1) Web (cloud sandbox / AI agent)"
    $choice = Read-Host "Enter 1"
    switch ($choice) {
        { "1" } { $RokctProfile = "web" }
        default { $RokctProfile = "web" }
    }
}
else {
    Write-Host "[install] Invalid input. Defaulting to Local."
    $RokctProfile = "local"
}

$InitFile = "profiles/$RokctProfile/initiate.py"
if ($RokctProfile -eq "web") {
    $InitiateSha256 = $InitiateSha256Web
}
else {
    $InitiateSha256 = $InitiateSha256Local
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[install] ERROR: python is required but not installed."
    exit 1
}

New-Item -ItemType Directory -Force -Path ".rokct" | Out-Null

Write-Host "[install] Fetching $RokctProfile initiate.py from protocol (ref $ProtocolRef)..."
Invoke-WebRequest -Uri "$ProtocolRaw/$InitFile" -OutFile ".rokct/initiate.py"

$ActualSha256 = (Get-FileHash -Path ".rokct/initiate.py" -Algorithm SHA256).Hash.ToLower()
if ($ActualSha256 -ne $InitiateSha256) {
    Write-Host "[install] ERROR: integrity check failed for $InitFile (ref $ProtocolRef)."
    Write-Host "[install]   expected sha256 $InitiateSha256"
    Write-Host "[install]   actual   sha256 $ActualSha256"
    Write-Host "[install] Refusing to execute unverified code."
    Remove-Item -Force ".rokct/initiate.py"
    exit 1
}

Write-Host "[install] Running init..."
python .rokct/initiate.py

Write-Host "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
