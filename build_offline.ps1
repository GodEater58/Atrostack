param(
    [string]$Version = '1.4.0_preview'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root 'build'
$Wheelhouse = Join-Path $Build 'wheelhouse'
$Setup = Join-Path $Root 'setup'
$Payload = Join-Path $Build 'payload'
$PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
$PythonInstaller = Join-Path $Setup 'python-runtime.exe'
$Output = Join-Path $Root ("AstroStack_Setup_Offline_{0}.exe" -f $Version)

Write-Host '=== AstroStack Offline Builder ===' -ForegroundColor Cyan
if (-not (Get-Command go.exe -ErrorAction SilentlyContinue)) {
    throw 'Go non trovato. Installa Go 1.23+ oppure usa la GitHub Action inclusa.'
}
if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
    throw 'Python non trovato. Serve solo per preparare il wheelhouse durante la build.'
}

Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Wheelhouse,$Payload -Force | Out-Null

Write-Host '[1/7] Compilo il launcher Windows...'
Push-Location (Join-Path $Root 'launcher')
$env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
go build -trimpath -ldflags '-s -w -H=windowsgui' -o (Join-Path $Payload 'AstroStack.exe') .
if ($LASTEXITCODE -ne 0) { throw 'Compilazione launcher fallita.' }
Pop-Location

Write-Host '[2/7] Copio AstroStack nel payload...'
Copy-Item (Join-Path $Root 'app') (Join-Path $Payload 'app') -Recurse

Write-Host '[3/7] Scarico il runtime Python Windows ufficiale...'
Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonInstaller -UseBasicParsing

Write-Host '[4/7] Scarico tutte le wheel Windows x64...'
$Req = Join-Path $Root 'app\requirements.txt'
python -m pip download --only-binary=:all: --platform win_amd64 --python-version 312 --implementation cp --abi cp312 --dest $Wheelhouse -r $Req
if ($LASTEXITCODE -ne 0) { throw 'Download wheel fallito.' }

python -m pip download --only-binary=:all: --platform win_amd64 --python-version 312 --implementation py3 --dest $Wheelhouse pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'Download toolchain pip fallito.' }

Write-Host '[5/7] Creo payload.zip e wheelhouse.zip...'
$PayloadZip = Join-Path $Setup 'payload.zip'
$WheelZip = Join-Path $Setup 'wheelhouse.zip'
Remove-Item $PayloadZip,$WheelZip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Payload '*') -DestinationPath $PayloadZip -CompressionLevel Optimal
Compress-Archive -Path (Join-Path $Wheelhouse '*') -DestinationPath $WheelZip -CompressionLevel Optimal

Write-Host '[6/7] Compilo il Setup offline singolo...'
Push-Location $Setup
$env:GOOS='windows'; $env:GOARCH='amd64'; $env:CGO_ENABLED='0'
go build -trimpath -ldflags '-s -w -H=windowsgui' -o $Output .
if ($LASTEXITCODE -ne 0) { throw 'Compilazione installer fallita.' }
Pop-Location

Write-Host '[7/7] Creo checksum SHA-256...'
$Hash = (Get-FileHash $Output -Algorithm SHA256).Hash.ToLowerInvariant()
$HashFile = "$Output.sha256.txt"
"$Hash  $(Split-Path $Output -Leaf)" | Set-Content -Path $HashFile -Encoding ascii

Write-Host ''
Write-Host 'Build completata:' -ForegroundColor Green
Write-Host $Output
Write-Host $HashFile
