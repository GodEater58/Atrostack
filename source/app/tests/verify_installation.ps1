# Run only on an isolated CI runner: installs AstroStack in the runner profile.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'This integration test requires an isolated GitHub Actions runner.' }
$installer = (Resolve-Path 'source/AstroStack_Setup_Offline_1.3.2_preview.exe').Path
$existing = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
if (-not (Test-Path -LiteralPath $existing)) { throw 'Expected registered Python 3.12.10 fixture.' }
function Get-PythonSnapshot {
    $result = [ordered]@{}
    foreach ($file in @('python.exe','python312.dll','DLLs\_tkinter.pyd','include\Python.h','libs\python312.lib')) {
        $result[$file] = (Get-FileHash -LiteralPath (Join-Path (Split-Path $existing) $file)).Hash
    }
    $result['registry'] = (reg query 'HKCU\Software\Python' /s | Out-String)
    if ($LASTEXITCODE) { throw 'Python registry fixture missing.' }
    $result['path'] = [Environment]::GetEnvironmentVariable('PATH','User')
    return ($result | ConvertTo-Json -Compress)
}
$before = Get-PythonSnapshot
$install = Join-Path $env:LOCALAPPDATA 'Programs\AstroStack'
$runtime = Join-Path $install 'runtime\python.exe'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:HTTP_PROXY='http://127.0.0.1:9'
$env:HTTPS_PROXY='http://127.0.0.1:9'
$env:PIP_NO_INDEX='1'
# Poison ambient Python settings: the bundled runtime must ignore them.
$env:PYTHONHOME='Z:\nonexistent-python'
$env:PYTHONPATH='Z:\nonexistent-packages'
foreach ($attempt in 1..2) {
    $p = Start-Process -FilePath $installer -ArgumentList '-Silent' -PassThru -WindowStyle Hidden
    if (-not $p.WaitForExit(300000)) { $p.Kill(); throw 'Installer timed out.' }
    if ($p.ExitCode -ne 0) { Get-Content (Join-Path $env:TEMP 'AstroStack-install.log'); throw "Installer failed: $($p.ExitCode)" }
    & $runtime (Join-Path $install 'app\verify_runtime.py')
    if ($LASTEXITCODE) { throw 'Installed runtime verification failed.' }
    Push-Location (Join-Path $install 'app')
    try {
        & $runtime 'tests\smoke_gui.py'
        if ($LASTEXITCODE) { throw 'Installed GUI smoke test failed.' }
    } finally { Pop-Location }
    if ((Get-PythonSnapshot) -ne $before) { throw 'Existing Python files, registration or PATH changed.' }
    if ((Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AstroStack').DisplayVersion -ne '1.3.2-preview-offline') { throw 'Incorrect installed version.' }
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'AstroStack.lnk'))
    if ($shortcut.TargetPath -ne (Join-Path $install 'AstroStack.exe')) { throw 'Invalid desktop shortcut.' }
    Write-Host "ASTROSTACK_INSTALL_AND_REINSTALL_OK attempt=$attempt"
}
Remove-Item Env:PYTHONHOME,Env:PYTHONPATH
& $existing -c 'import tkinter, sys; assert sys.version_info[:3] == (3, 12, 10)'
if ($LASTEXITCODE) { throw 'Existing Python no longer works.' }
# A malformed payload must return an error without replacing the good installation.
$badZip = Join-Path $env:RUNNER_TEMP 'invalid-payload.zip'
$emptyFile = Join-Path $env:RUNNER_TEMP 'not-a-runtime.txt'
Set-Content -LiteralPath $emptyFile -Value 'invalid payload'
Compress-Archive -LiteralPath $emptyFile -DestinationPath $badZip -Force
$hash = (Get-FileHash -LiteralPath $runtime).Hash
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'source/setup/install_offline.ps1' -PayloadZip $badZip -Silent
if ($LASTEXITCODE -eq 0) { throw 'Invalid payload incorrectly succeeded.' }
if ((Get-FileHash -LiteralPath $runtime).Hash -ne $hash) { throw 'Failed install damaged the existing application.' }
Write-Host 'ASTROSTACK_INSTALL_FAILURE_PROPAGATION_OK'
exit 0
