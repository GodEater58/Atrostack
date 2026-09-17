param([string]$Version = '1.4.0_preview')

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root 'build'
$PackageName = "AstroStack_${Version}_Windows_x64"
$PackageRoot = Join-Path $Build $PackageName
$Runtime = Join-Path $PackageRoot 'runtime'
$Wheelhouse = Join-Path $Build 'wheelhouse'
$ZipOutput = Join-Path $Root ("{0}.zip" -f $PackageName)
$HashOutput = "$ZipOutput.sha256.txt"

if (-not (Get-Command go.exe -ErrorAction SilentlyContinue)) { throw 'Go mancante.' }
if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) { throw 'Python di build mancante.' }

if (Test-Path -LiteralPath $Build) { Remove-Item -LiteralPath $Build -Recurse -Force }
Remove-Item -LiteralPath $ZipOutput,$HashOutput -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $PackageRoot,$Runtime,$Wheelhouse,(Join-Path $PackageRoot 'logs') -Force | Out-Null

Write-Host '[1/6] Compilo AstroStack.exe...'
Push-Location (Join-Path $Root 'launcher')
try {
    $env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
    go build -trimpath -ldflags '-s -w -H=windowsgui' -o (Join-Path $PackageRoot 'AstroStack.exe') .
    if ($LASTEXITCODE) { throw 'Build launcher fallita.' }
} finally { Pop-Location }

Write-Host '[2/6] Copio l applicazione...'
Copy-Item -LiteralPath (Join-Path $Root 'app') -Destination (Join-Path $PackageRoot 'app') -Recurse

Write-Host '[3/6] Preparo Python embeddable privato...'
$RuntimeZip = Join-Path $Build 'python-embed.zip'
Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile $RuntimeZip -UseBasicParsing
Expand-Archive -LiteralPath $RuntimeZip -DestinationPath $Runtime
@('python312.zip','.','Lib\site-packages','..\app','import site') | Set-Content -LiteralPath (Join-Path $Runtime 'python312._pth') -Encoding ascii

Write-Host '[4/6] Includo le dipendenze...'
$Req = Join-Path $Root 'app\requirements.txt'
python -m pip download --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp --abi cp312 --dest $Wheelhouse -r $Req
if ($LASTEXITCODE) { throw 'Download wheel fallito.' }
python -m pip install --no-index --no-compile --only-binary=:all: --find-links $Wheelhouse --target (Join-Path $Runtime 'Lib\site-packages') -r $Req
if ($LASTEXITCODE) { throw 'Preparazione librerie fallita.' }

Write-Host '[5/6] Verifico il pacchetto portable...'
& (Join-Path $Runtime 'python.exe') (Join-Path $PackageRoot 'app\verify_runtime.py')
if ($LASTEXITCODE) { throw 'Verifica runtime privato fallita.' }
if (-not (Test-Path -LiteralPath (Join-Path $Runtime 'pythonw.exe'))) { throw 'pythonw.exe mancante dal runtime.' }
if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot 'AstroStack.exe'))) { throw 'AstroStack.exe mancante.' }

$DebugCmd = @'
@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONNOUSERSITE=1
set PYTHONDONTWRITEBYTECODE=1
runtime\python.exe app\main.py %*
if errorlevel 1 pause
'@
Set-Content -LiteralPath (Join-Path $PackageRoot 'AstroStack-Debug.cmd') -Value $DebugCmd -Encoding ascii

$Readme = @"
AstroStack $Version - Windows x64 portable

AVVIO
1. Estrai completamente lo ZIP in una cartella.
2. Avvia AstroStack.exe.
3. Non serve installare Python e non serve un setup.

IMPORTANTE
- Non avviare AstroStack direttamente dentro lo ZIP: prima estrailo.
- Mantieni insieme AstroStack.exe, app e runtime.
- In caso di problemi controlla logs\AstroStack.log.
- AstroStack-Debug.cmd apre la console ed e utile solo per la diagnostica.

Il runtime Python e le dipendenze necessarie sono incluse nella cartella runtime.
"@
Set-Content -LiteralPath (Join-Path $PackageRoot 'README.txt') -Value $Readme -Encoding utf8

Write-Host '[6/6] Creo ZIP e checksum SHA-256...'
Compress-Archive -Path $PackageRoot -DestinationPath $ZipOutput -CompressionLevel Optimal -Force
$Hash = (Get-FileHash -LiteralPath $ZipOutput -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $(Split-Path $ZipOutput -Leaf)" | Set-Content -LiteralPath $HashOutput -Encoding ascii

Write-Host "Pacchetto: $ZipOutput"
Write-Host "Checksum: $HashOutput"
