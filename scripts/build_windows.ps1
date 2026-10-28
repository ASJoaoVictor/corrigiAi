# Run on Windows with Python 3.12 x64 and WiX 4 CLI on PATH.
param(
    [string]$PythonExecutable = 'python',
    [ValidateSet('postgres', 'sqlite-test')][string]$Edition = 'postgres'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'Este build precisa ser executado no Windows.' }
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    Get-Command $PythonExecutable -ErrorAction Stop | Out-Null
    Get-Command wix -ErrorAction Stop | Out-Null
    & $PythonExecutable -c "import sys, struct, tkinter; assert sys.version_info[:2] == (3, 12); assert struct.calcsize('P') == 8"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 com Tkinter é obrigatório.' }
    $BuildEnv = Join-Path $ProjectRoot '.venv-windows-build'
    if (!(Test-Path $BuildEnv)) { & $PythonExecutable -m venv $BuildEnv }
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente de build.' }
    $Python = Join-Path $BuildEnv 'Scripts\python.exe'
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Falha no pip.' }
    & $Python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyTorch CPU.' }
    & $Python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha nas dependências.' }
    & $Python -c "import torch; assert torch.version.cuda is None, 'CUDA não é permitido neste build'"
    if ($LASTEXITCODE -ne 0) { throw 'O build exige PyTorch CPU.' }
    $OldModels = $env:OCR_MODEL_DIR
    try {
        $env:OCR_MODEL_DIR = Join-Path $ProjectRoot 'build\ocr-models'
        & $Python scripts/prepare_ocr.py
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar OCR.' }
    } finally { $env:OCR_MODEL_DIR = $OldModels }
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam.' }
    $OldEdition = $env:CORRIGIAI_BUILD_SQLITE_TEST
    try {
        $env:CORRIGIAI_BUILD_SQLITE_TEST = if ($Edition -eq 'sqlite-test') { '1' } else { '0' }
        & $Python -m PyInstaller --noconfirm --clean corrigiai.spec
        if ($LASTEXITCODE -ne 0) { throw 'Falha no PyInstaller.' }
    } finally { $env:CORRIGIAI_BUILD_SQLITE_TEST = $OldEdition }
    & $Python scripts/windows_payload.py dist/corrigiAi build/Payload.wxs
    if ($LASTEXITCODE -ne 0) { throw 'Distribuição inválida.' }
    $AppVersion = & $Python -c "from app.runtime import VERSION; print(VERSION)"
    $ProductName = 'corrigiAi'
    $InstallName = 'corrigiAi'
    $UpgradeCode = '63EA7DDD-C428-42ED-A17D-8F7450BD9C1B'
    $Installer = 'dist/corrigiAi-Setup.msi'
    if ($Edition -eq 'sqlite-test') {
        $ProductName = 'corrigiAi Testes'
        $InstallName = 'corrigiAi Testes'
        $UpgradeCode = '2FC9D7DE-8DB2-44E2-9147-B82507091CBE'
        $Installer = 'dist/corrigiAi-Testes-Setup.msi'
        $AppPort = & $Python -c "from desktop.sqlite_test import TEST_PORT; print(TEST_PORT)"
    } else {
        $AppPort = & $Python -c "from app.runtime import DEFAULT_PORT; print(DEFAULT_PORT)"
    }
    & wix extension add WixToolset.Firewall.wixext/4.0.6
    if ($LASTEXITCODE -ne 0) { throw 'Falha na extensão WiX Firewall.' }
    & wix build packaging/windows/Package.wxs build/Payload.wxs -arch x64 -ext WixToolset.Firewall.wixext/4.0.6 -d "ProductName=$ProductName" -d "InstallName=$InstallName" -d "UpgradeCode=$UpgradeCode" -d "AppVersion=$AppVersion" -d "AppPort=$AppPort" -d "DistDir=$ProjectRoot\dist\corrigiAi" -o $Installer
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar MSI.' }
    Write-Host "Distribuição: dist/corrigiAi | Instalador: $Installer"
} finally { Pop-Location }
