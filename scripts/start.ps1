param([switch]$Wsl)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($Wsl) {
    $linuxRoot = (wsl wslpath -a $projectRoot).Trim()
    wsl -- bash "$linuxRoot/scripts/local.sh"
} else {
    python scripts/bootstrap.py
}
if ($LASTEXITCODE -ne 0) { throw 'BOREAL startup failed; inspect the preceding error.' }
