# Rokct Protocol Installer (Windows PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
# The initiate.py fetch is pinned to this commit and its SHA-256 is verified
# before it is executed; a mismatch aborts the install.
$ProtocolRef = "a3a5843ad18f3d9d567627a50293776816371b39"
$InitiateSha256Local = "5bbb1d11b267b1d8b41a9960045606c27e3594b32dc0a0ffdf1bf241fee0d61a"
$InitiateSha256Web = "15c00a541bd1a25cd49efea14117de522c9b940893150aa8db09671a2e166857"

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
