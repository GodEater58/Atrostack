param([string]$Version = '1.4.0_preview')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root 'build'
$Setup = Join-Path $Root 'setup'
$Payload = Join-Path $Build 'payload'
$Runtime = Join-Path $Payload 'runtime'
$Wheelhouse = Join-Path $Build 'wheelhouse'
$Output = Join-Path $Root ("AstroStack_Setup_Offline_{0}.exe" -f $Version)
if (-not (Get-Command go.exe -ErrorAction SilentlyContinue)) { throw 'Go mancante.' }
if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) { throw 'Python di build mancante.' }
if ([IO.Path]::GetFullPath($Build) -ne [IO.Path]::GetFullPath((Join-Path $Root 'build'))) { throw 'Percorso build non valido.' }
if (Test-Path -LiteralPath $Build) { Remove-Item -LiteralPath $Build -Recurse -Force }
New-Item -ItemType Directory -Path $Runtime,$Wheelhouse -Force | Out-Null
Write-Host '[1/5] Compilo il launcher...'
Push-Location (Join-Path $Root 'launcher')
try {
    $env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
    go build -trimpath -ldflags '-s -w -H=windowsgui' -o (Join-Path $Payload 'AstroStack.exe') .
    if ($LASTEXITCODE) { throw 'Build launcher fallita.' }
} finally { Pop-Location }
Copy-Item -LiteralPath (Join-Path $Root 'app') -Destination (Join-Path $Payload 'app') -Recurse
Write-Host '[2/5] Preparo Python embeddable privato...'
$RuntimeZip = Join-Path $Build 'python-embed.zip'
Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile $RuntimeZip -UseBasicParsing
Expand-Archive -LiteralPath $RuntimeZip -DestinationPath $Runtime
# Explicit isolated search paths: no registry, PYTHONPATH or user packages.
@('python312.zip','.','Lib\site-packages','..\app','import site') | Set-Content -LiteralPath (Join-Path $Runtime 'python312._pth') -Encoding ascii
Write-Host '[3/5] Includo le dipendenze durante la build...'
$Req = Join-Path $Root 'app\requirements.txt'
python -m pip download --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp --abi cp312 --dest $Wheelhouse -r $Req
if ($LASTEXITCODE) { throw 'Download wheel fallito.' }
python -m pip install --no-index --no-compile --only-binary=:all: --find-links $Wheelhouse --target (Join-Path $Runtime 'Lib\site-packages') -r $Req
if ($LASTEXITCODE) { throw 'Preparazione librerie fallita.' }
& (Join-Path $Runtime 'python.exe') (Join-Path $Payload 'app\verify_runtime.py')
if ($LASTEXITCODE) { throw 'Verifica runtime privato fallita.' }
Write-Host '[4/5] Compilo il setup con il payload completo...'
$PayloadZip = Join-Path $Setup 'payload.zip'
Compress-Archive -Path (Join-Path $Payload '*') -DestinationPath $PayloadZip -CompressionLevel Optimal -Force
Push-Location $Setup
try {
    go build -trimpath -ldflags '-s -w -H=windowsgui' -o $Output .
    if ($LASTEXITCODE) { throw 'Build setup fallita.' }
} finally { Pop-Location }
Write-Host '[5/5] Creo checksum SHA-256...'
$Hash = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $(Split-Path $Output -Leaf)" | Set-Content -LiteralPath "$Output.sha256.txt" -Encoding ascii
Write-Host $Output
