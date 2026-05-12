param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ConfigPath = (Join-Path (Resolve-Path "$PSScriptRoot\..").Path "config.yaml")
)

$ErrorActionPreference = "Stop"

$entrypoint = (Get-Command wiim-lastfm-tray.exe -ErrorAction SilentlyContinue).Source
if (-not $entrypoint) {
    throw "Could not find wiim-lastfm-tray.exe. Run python -m pip install -e . before installing startup."
}

$scriptsDir = Split-Path -Parent $entrypoint
$pythonw = Join-Path $scriptsDir "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $pythonw = Join-Path $scriptsDir "python.exe"
}
if (-not (Test-Path $pythonw)) {
    throw "Could not find pythonw.exe or python.exe next to wiim-lastfm-tray.exe."
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
