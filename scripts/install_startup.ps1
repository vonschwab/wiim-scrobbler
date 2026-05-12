param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ConfigPath = (Join-Path (Resolve-Path "$PSScriptRoot\..").Path "config.yaml")
)

$ErrorActionPreference = "Stop"

$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $python) {
        throw "Could not find pythonw.exe or python.exe on PATH."
    }
    $pythonw = $python
}

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "WiiM Last.fm Scrobbler.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m wiim_lastfm.tray --config `"$ConfigPath`""
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = "Start WiiM Last.fm Scrobbler tray app"
$shortcut.Save()

Write-Host "Installed startup shortcut:"
Write-Host $shortcutPath
