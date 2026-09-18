param([Parameter(Mandatory=$true)][string]$Archive)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'Run only on an isolated CI runner.' }
$Archive = (Resolve-Path -LiteralPath $Archive).Path
$Stage = Join-Path $env:RUNNER_TEMP 'AstroStack portable test con spazi'
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
Expand-Archive -LiteralPath $Archive -DestinationPath $Stage
$Root = (Get-ChildItem -LiteralPath $Stage -Directory | Select-Object -First 1).FullName
$Python = Join-Path $Root 'runtime\python.exe'
$ReportDir = Join-Path $env:GITHUB_WORKSPACE 'windows-verification'
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
# Simulate an offline user with an unrelated/broken ambient Python installation.
$env:HTTP_PROXY = 'http://127.0.0.1:9'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$env:PIP_NO_INDEX = '1'
$env:PYTHONHOME = 'Z:\missing-python'
$env:PYTHONPATH = 'Z:\missing-python-packages'
$env:PYTHONDONTWRITEBYTECODE = '1'
$BeforePath = [Environment]::GetEnvironmentVariable('PATH', 'User')
& $Python (Join-Path $Root 'app\verify_runtime.py')
if ($LASTEXITCODE) { throw 'Private runtime verification failed.' }
# Check the exact archive contents, not the source/build directory.
$env:ASTROSTACK_VERIFY_ROOT = $Root
& $Python -c "import hashlib,json,os,pathlib; p=pathlib.Path(os.environ['ASTROSTACK_VERIFY_ROOT']); m=json.loads((p/'BUILD-MANIFEST.json').read_text(encoding='utf8')); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in m['sha256'].items()); print('ASTROSTACK_ARCHIVE_HASHES_OK')"
if ($LASTEXITCODE) { throw 'Archive manifest mismatch.' }
$env:QT_QPA_PLATFORM = 'offscreen'
foreach ($Test in @('test_ux_v14.py','test_render_workspace.py','test_assisted_140.py','regression_editor_stack_v12.py','regression_live_drizzle.py')) {
    # Native QSettings on Windows uses the runner registry. Reset only this disposable app profile.
    & $Python -c "from PySide6.QtCore import QSettings; s=QSettings('AstroStack','AstroStack'); s.clear(); s.setValue('guide_seen','1'); s.sync()"
    if ($LASTEXITCODE) { throw 'Test settings preparation failed.' }
    & $Python (Join-Path $Root "app\tests\$Test")
    if ($LASTEXITCODE) { throw "Packaged test failed: $Test" }
}
# Actual native Windows GUI, launched through the distributed EXE (no console).
$env:QT_QPA_PLATFORM = 'windows'
& $Python -c "from PySide6.QtCore import QSettings; s=QSettings('AstroStack','AstroStack'); s.clear(); s.setValue('guide_seen','1'); s.sync()"
$Report = Join-Path $ReportDir 'launcher-report.json'
$Launcher = Join-Path $Root 'AstroStack.exe'
# PE subsystem must be Windows GUI (2), not console (3).
$env:ASTROSTACK_LAUNCHER = $Launcher
& $Python -c "import os,struct; d=open(os.environ['ASTROSTACK_LAUNCHER'],'rb').read(); pe=struct.unpack_from('<I',d,0x3c)[0]; assert struct.unpack_from('<H',d,pe+24+68)[0]==2; print('ASTROSTACK_WINDOWS_GUI_SUBSYSTEM_OK')"
if ($LASTEXITCODE) { throw 'Launcher is not a Windows GUI binary.' }
$Process = Start-Process -FilePath $Launcher -ArgumentList "--self-test-report `"$Report`"" -PassThru
if (-not $Process.WaitForExit(20000)) { $Process.Kill(); throw 'Launcher timed out.' }
if ($Process.ExitCode -ne 0) { throw 'Launcher returned an error.' }
$Deadline = (Get-Date).AddSeconds(90)
while (-not (Test-Path -LiteralPath $Report) -and (Get-Date) -lt $Deadline) { Start-Sleep -Milliseconds 250 }
if (-not (Test-Path -LiteralPath $Report)) { throw 'GUI report missing; inspect launcher.log.' }
$Result = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
if (-not $Result.ok) { throw "Native GUI test failed: $($Result.error)" }
if ($Result.version -ne '1.4.0-preview' -or $Result.platform -ne 'windows' -or $Result.console_window -ne 0 -or -not $Result.isolated_runtime) { throw 'Incorrect native GUI runtime.' }
if ([IO.Path]::GetFullPath($Result.python) -ne [IO.Path]::GetFullPath((Join-Path $Root 'runtime\pythonw.exe'))) { throw 'Launcher did not use the bundled pythonw.' }
$GuiProcess = Get-Process -Id $Result.pid -ErrorAction SilentlyContinue
if ($GuiProcess -and -not $GuiProcess.WaitForExit(20000)) { $GuiProcess.Kill(); throw 'GUI did not close cleanly.' }
if ([Environment]::GetEnvironmentVariable('PATH', 'User') -ne $BeforePath) { throw 'Portable app changed user PATH.' }
Copy-Item -LiteralPath (Join-Path $Root 'BUILD-MANIFEST.json') -Destination $ReportDir
Write-Host 'ASTROSTACK_WINDOWS_PORTABLE_VERIFIED'
