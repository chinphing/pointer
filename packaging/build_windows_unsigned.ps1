Param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$RootDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RootDir

Write-Host "[1/5] Upgrade pip"
& $PythonExe -m pip install --upgrade pip

Write-Host "[2/5] Install dependencies"
& $PythonExe -m pip install -r requirements.txt -r requirements2.txt pyinstaller

Write-Host "[3/5] Build Pointer.exe with PyInstaller"
& $PythonExe -m PyInstaller packaging/pyinstaller/pointer.spec --noconfirm --clean

Write-Host "[4/5] Ensure Inno Setup (ISCC) is available"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    throw "Inno Setup not found. Install it first, then re-run. Expected path: $iscc"
}

Write-Host "[5/5] Build unsigned installer"
& $iscc "packaging/windows/pointer.iss"

Write-Host "Done: dist/Pointer/ and dist/Pointer-Setup.exe"
