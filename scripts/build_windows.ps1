$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$specPath = Join-Path $projectRoot "packaging\wiim-scrobbler.spec"
$installerScript = Join-Path $projectRoot "packaging\wiim-scrobbler.iss"

Set-Location $projectRoot

Write-Host "Installing package build requirements..."
python -m pip install -e ".[dev,build]"

Write-Host "Building executable with PyInstaller..."
python -m PyInstaller --clean --noconfirm $specPath

$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $candidatePaths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            $iscc = $candidate
            break
        }
    }
}
if (-not $iscc) {
    throw "ISCC.exe was not found. Install Inno Setup 6 and rerun this script."
}

Write-Host "Building installer with Inno Setup..."
& $iscc $installerScript

Write-Host "Build complete."
