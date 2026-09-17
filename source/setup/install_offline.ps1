param(
    [Parameter(Mandatory=$true)][string]$PayloadZip,
    [switch]$Silent
)

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.IO.Compression.FileSystem

$ErrorActionPreference = 'Stop'
$Version = '1.4.0-preview-offline'
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\AstroStack'
$RuntimeDir = Join-Path $InstallDir 'runtime'
$StartMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AstroStack'
$DesktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AstroStack.lnk'
$StartLink = Join-Path $StartMenuDir 'AstroStack.lnk'
$UninstallLink = Join-Path $StartMenuDir 'Disinstalla AstroStack.lnk'
$StagingDir = Join-Path (Split-Path $InstallDir) ('AstroStack-staging-' + [guid]::NewGuid().ToString('N'))
$LogPath = Join-Path $env:TEMP 'AstroStack-install.log'
$script:InstallExitCode = 0
Start-Transcript -Path $LogPath -Force | Out-Null

if (-not $Silent) {
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="AstroStack Setup Offline" Height="265" Width="580" WindowStartupLocation="CenterScreen"
        ResizeMode="NoResize" Background="#0B1420" Foreground="#E7EEF8">
  <Grid Margin="28">
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
    </Grid.RowDefinitions>
    <TextBlock Text="AstroStack 1.4.0 Preview" FontSize="25" FontWeight="SemiBold"/>
    <TextBlock Grid.Row="1" Margin="0,8,0,0" Text="Installazione offline completa · nessuna connessione richiesta" Foreground="#8FA7C2" FontSize="13"/>
    <ProgressBar Name="Bar" Grid.Row="2" Margin="0,26,0,0" Height="16" Minimum="0" Maximum="100" Value="2"/>
    <TextBlock Name="Status" Grid.Row="3" Margin="0,18,0,0" Text="Preparazione…" TextWrapping="Wrap" FontSize="13"/>
  </Grid>
</Window>
"@
$reader = New-Object System.Xml.XmlNodeReader $xaml
$win = [Windows.Markup.XamlReader]::Load($reader)
$bar = $win.FindName('Bar')
$status = $win.FindName('Status')
}

function Set-Stage([string]$Text, [int]$Value) {
    Write-Host $Text
    if ($Silent) { return }
    $status.Text = $Text
    $bar.Value = $Value
    $win.Dispatcher.Invoke([action]{}, 'Background')
}

function Run-Process([string]$File, [string[]]$ProcessArgs) {
    $p = Start-Process -FilePath $File -ArgumentList $ProcessArgs -Wait -PassThru -WindowStyle Hidden
    if ($p.ExitCode -ne 0) { throw "$File ha restituito il codice $($p.ExitCode)." }
}

function New-Shortcut([string]$Path, [string]$Target, [string]$Arguments='') {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($Path)
    $s.TargetPath = $Target
    if ($Arguments) { $s.Arguments = $Arguments }
    $s.WorkingDirectory = $InstallDir
    $icon = Join-Path $InstallDir 'app\astrostack.ico'
    if (Test-Path $icon) { $s.IconLocation = "$icon,0" }
    $s.Save()
}

function Install-AstroStack {
    try {
        Set-Stage 'Estraggo applicazione e runtime privato...' 15
        New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null
        [System.IO.Compression.ZipFile]::ExtractToDirectory($PayloadZip, $StagingDir)
        $python = Join-Path $StagingDir 'runtime\python.exe'
        if (-not (Test-Path -LiteralPath $python)) { throw 'Runtime privato assente nel pacchetto.' }
        Set-Stage 'Verifico il runtime e le librerie incluse...' 70
        Run-Process $python @(('"' + (Join-Path $StagingDir 'app\verify_runtime.py') + '"'))
        $expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\AstroStack'))
        if ([IO.Path]::GetFullPath($InstallDir) -ne $expected) { throw 'Percorso installazione non valido.' }
        if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force }
        Move-Item -LiteralPath $StagingDir -Destination $InstallDir

        Set-Stage 'Creo collegamenti e integrazione con Windows…' 88
        New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
        $launcher = Join-Path $InstallDir 'AstroStack.exe'
        New-Shortcut $DesktopLink $launcher
        New-Shortcut $StartLink $launcher

        $uninstallPs = Join-Path $InstallDir 'uninstall.ps1'
        $uninstallCode = @'
Add-Type -AssemblyName PresentationFramework
$install = Split-Path -Parent $MyInvocation.MyCommand.Path
$r = [System.Windows.MessageBox]::Show('Vuoi disinstallare AstroStack?','AstroStack',[System.Windows.MessageBoxButton]::YesNo,[System.Windows.MessageBoxImage]::Question)
if ($r -ne [System.Windows.MessageBoxResult]::Yes) { exit }
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AstroStack.lnk'
$start = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AstroStack'
Remove-Item $desktop -Force -ErrorAction SilentlyContinue
Remove-Item $start -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Classes\.astrostack' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Classes\AstroStack.Project' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AstroStack' -Recurse -Force -ErrorAction SilentlyContinue
Start-Process cmd.exe -ArgumentList '/c', "timeout /t 2 /nobreak >nul & rmdir /s /q `"$install`"" -WindowStyle Hidden
'@
        Set-Content -Path $uninstallPs -Value $uninstallCode -Encoding UTF8
        $ps = (Get-Command powershell.exe).Source
        New-Shortcut $UninstallLink $ps "-NoProfile -ExecutionPolicy Bypass -File `"$uninstallPs`""

        New-Item 'HKCU:\Software\Classes\.astrostack' -Force | Out-Null
        Set-Item 'HKCU:\Software\Classes\.astrostack' -Value 'AstroStack.Project'
        New-Item 'HKCU:\Software\Classes\AstroStack.Project\DefaultIcon' -Force | Out-Null
        Set-Item 'HKCU:\Software\Classes\AstroStack.Project\DefaultIcon' -Value (Join-Path $InstallDir 'app\astrostack.ico')
        New-Item 'HKCU:\Software\Classes\AstroStack.Project\shell\open\command' -Force | Out-Null
        Set-Item 'HKCU:\Software\Classes\AstroStack.Project\shell\open\command' -Value ('"' + $launcher + '" "%1"')

        $unKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AstroStack'
        New-Item $unKey -Force | Out-Null
        Set-ItemProperty $unKey -Name DisplayName -Value 'AstroStack'
        Set-ItemProperty $unKey -Name DisplayVersion -Value $Version
        Set-ItemProperty $unKey -Name Publisher -Value 'AstroStack'
        Set-ItemProperty $unKey -Name InstallLocation -Value $InstallDir
        Set-ItemProperty $unKey -Name DisplayIcon -Value (Join-Path $InstallDir 'app\astrostack.ico')
        Set-ItemProperty $unKey -Name UninstallString -Value ("powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallPs`"")
        New-ItemProperty $unKey -Name NoModify -PropertyType DWord -Value 1 -Force | Out-Null
        New-ItemProperty $unKey -Name NoRepair -PropertyType DWord -Value 1 -Force | Out-Null

        Set-Stage 'Installazione offline completata.' 100
        Start-Sleep -Milliseconds 500
        if (-not $Silent) {
        $win.Close()
        $go = [System.Windows.MessageBox]::Show('AstroStack è installato. Vuoi avviarlo ora?','AstroStack',[System.Windows.MessageBoxButton]::YesNo,[System.Windows.MessageBoxImage]::Information)
        if ($go -eq [System.Windows.MessageBoxResult]::Yes) { Start-Process $launcher -WindowStyle Hidden }
        }
    }
    catch {
        $script:InstallExitCode = 1
        Write-Host $_.Exception.ToString()
        if (-not $Silent) {
            $win.Close()
            [System.Windows.MessageBox]::Show("Installazione non riuscita:`n`n$($_.Exception.Message)`n`nLog: $LogPath", 'AstroStack Setup Offline') | Out-Null
        }
    }
    finally {
        $parent = [IO.Path]::GetFullPath((Split-Path $InstallDir)) + [IO.Path]::DirectorySeparatorChar
        if ([IO.Path]::GetFullPath($StagingDir).StartsWith($parent) -and (Split-Path $StagingDir -Leaf) -like 'AstroStack-staging-*') {
            if (Test-Path -LiteralPath $StagingDir) { Remove-Item -LiteralPath $StagingDir -Recurse -Force }
        }
    }
}
if ($Silent) { Install-AstroStack }
else {
    $win.Add_ContentRendered({ Install-AstroStack })
    $win.ShowDialog() | Out-Null
}
Stop-Transcript | Out-Null
exit $script:InstallExitCode
