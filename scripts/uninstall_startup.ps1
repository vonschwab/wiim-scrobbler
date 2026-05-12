$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "WiiM Last.fm Scrobbler.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item -LiteralPath $shortcutPath -Force
    Write-Host "Removed startup shortcut:"
    Write-Host $shortcutPath
} else {
    Write-Host "Startup shortcut was not installed."
}
