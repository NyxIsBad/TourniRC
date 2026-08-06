param([string]$Version = '1.0.0')

$ErrorActionPreference = 'Stop'

Push-Location $PSScriptRoot
try {
    npm.cmd ci
    npm.cmd run build
    python -m PyInstaller --noconfirm --clean TourniRC.spec
    Copy-Item PORTABLE_README.txt dist\TourniRC\README.txt
    Compress-Archive -Path dist\TourniRC -DestinationPath "dist\TourniRC-$Version-windows-x64.zip" -Force
    Write-Host "Portable build and ZIP created under dist\"
} finally {
    Pop-Location
}
