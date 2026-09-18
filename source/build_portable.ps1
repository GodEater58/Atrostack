param([string]$Version = '1.4.0-preview')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = $PSScriptRoot
$Build = Join-Path $Root 'build-portable'
$Name = "AstroStack_${Version}_Windows_x64"
$Payload = Join-Path $Build $Name
$Runtime = Join-Path $Payload 'runtime'
$Wheelhouse = Join-Path $Build 'wheelhouse'
$Output = Join-Path $Root 'dist'
if (-not (Get-Command go.exe -ErrorAction SilentlyContinue)) { throw 'Go di build mancante.' }
if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) { throw 'Python di build mancante.' }
if (Test-Path -LiteralPath $Build) { Remove-Item -LiteralPath $Build -Recurse -Force }
New-Item -ItemType Directory -Path $Runtime,$Wheelhouse,$Output -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Root 'app') -Destination (Join-Path $Payload 'app') -Recurse
Get-ChildItem -LiteralPath (Join-Path $Payload 'app') -Directory -Filter '__pycache__' -Recurse | Remove-Item -Recurse -Force
Write-Host '[1/5] Launcher nativo Windows senza console'
Push-Location (Join-Path $Root 'launcher')
try {
    $env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
    go build -trimpath -ldflags '-s -w -H=windowsgui' -o (Join-Path $Payload 'AstroStack.exe') main.go
    if ($LASTEXITCODE) { throw 'Build launcher fallita.' }
} finally { Pop-Location }
Write-Host '[2/5] Runtime Python privato'
$RuntimeZip = Join-Path $Build 'python-embed.zip'
Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile $RuntimeZip
Expand-Archive -LiteralPath $RuntimeZip -DestinationPath $Runtime
@('python312.zip','.','Lib\site-packages','..\app','import site') | Set-Content -LiteralPath (Join-Path $Runtime 'python312._pth') -Encoding ascii
Write-Host '[3/5] Dipendenze incluse nel pacchetto'
$Req = Join-Path $Root 'app\requirements.txt'
python -m pip download --only-binary=:all: --dest $Wheelhouse -r $Req
if ($LASTEXITCODE) { throw 'Download wheel fallito.' }
python -m pip install --no-index --no-compile --only-binary=:all: --find-links $Wheelhouse --target (Join-Path $Runtime 'Lib\site-packages') -r $Req
if ($LASTEXITCODE) { throw 'Preparazione librerie fallita.' }
$PrivatePython = Join-Path $Runtime 'python.exe'
& $PrivatePython (Join-Path $Payload 'app\verify_runtime.py')
if ($LASTEXITCODE) { throw 'Verifica runtime privato fallita.' }
@'
ASTROSTACK 1.4 PREVIEW - WINDOWS 64 BIT

1. Estrai TUTTO lo ZIP in una cartella, ad esempio Documenti\AstroStack.
2. Apri AstroStack.exe. Non occorre installare Python o altre librerie.
3. Mantieni AstroStack.exe, app e runtime nella stessa cartella.

Home: nuovo stack, Editor standalone oppure progetto salvato.
Editor: apri RAW/FITS/TIFF/PNG/JPEG; modifica, confronta ed esporta.
Gli strumenti di elaborazione funzionano offline. I servizi astronomici
esterni facoltativi richiedono una connessione solo quando vengono usati.

I progetti .astrostack usano anche la cartella nomeprogetto_dati:
conserva entrambi quando sposti o copi un progetto.

Il pacchetto non modifica Python, PATH o il registro di installazione.
Le preferenze e i log dell'app vengono conservati nel profilo Windows.
In caso di errore all'avvio consulta %LOCALAPPDATA%\AstroStack\logs.

'@ | Set-Content -LiteralPath (Join-Path $Payload 'LEGGIMI.txt') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $Root 'PORTABLE_LICENSES.txt') -Destination $Payload
$env:ASTROSTACK_PAYLOAD = $Payload
python (Join-Path $Root 'portable_manifest.py')
if ($LASTEXITCODE) { throw 'Creazione manifest fallita.' }
Write-Host '[4/5] ZIP completo'
$env:ASTROSTACK_ARCHIVE = Join-Path $Output "$Name.zip"
python -c "import os,pathlib,zipfile; root=pathlib.Path(os.environ['ASTROSTACK_PAYLOAD']); out=pathlib.Path(os.environ['ASTROSTACK_ARCHIVE']); z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6); [z.write(p,p.relative_to(root.parent)) for p in sorted(root.rglob('*')) if p.is_file()]; z.close()"
if ($LASTEXITCODE) { throw 'Creazione ZIP fallita.' }
Write-Host '[5/5] SHA-256'
$Archive = $env:ASTROSTACK_ARCHIVE
$Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $(Split-Path $Archive -Leaf)" | Set-Content -LiteralPath "$Archive.sha256.txt" -Encoding ascii
Write-Host "ASTROSTACK_PORTABLE_BUILD_OK $Archive"
