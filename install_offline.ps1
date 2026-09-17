param(
    [Parameter(Mandatory=$true)][string]$PayloadZip,
    [Parameter(Mandatory=$true)][string]$PythonInstaller,
    [Parameter(Mandatory=$true)][string]$WheelhouseZip
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
$WheelsDir = Join-Path $env:TEMP ('AstroStack-wheels-' + [guid]::NewGuid().ToString('N'))

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

function Set-Stage([string]$Text, [int]$Value) {
    $status.Text = $Text
    $bar.Value = $Value
    $win.Dispatcher.Invoke([action]{}, 'Background')
}

function Run-Process([string]$File, [string[]]$Args) {
    $p = Start-Process -FilePath $File -ArgumentList $Args -Wait -PassThru -WindowStyle Hidden
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

$win.Add_ContentRendered({
    try {
        Set-Stage 'Copio i file di AstroStack…' 8
        if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        [System.IO.Compression.ZipFile]::ExtractToDirectory($PayloadZip, $InstallDir)

        Set-Stage 'Installo il runtime Python privato incluso nel Setup…' 24
        $pyArgs = @('/quiet','InstallAllUsers=0',("TargetDir=`"$RuntimeDir`""),'Include_pip=1','Include_launcher=0','Include_test=0','Include_doc=0','Include_tcltk=0','Include_dev=0','PrependPath=0','Shortcuts=0')
        Run-Process $PythonInstaller $pyArgs

        $python = Join-Path $RuntimeDir 'python.exe'
        if (-not (Test-Path $python)) { throw 'Runtime Python non trovato dopo l’installazione.' }

        Set-Stage 'Estraggo le librerie offline incluse nel Setup…' 42
        New-Item -ItemType Directory -Path $WheelsDir -Force | Out-Null
        [System.IO.Compression.ZipFile]::ExtractToDirectory($WheelhouseZip, $WheelsDir)

        Set-Stage 'Installo GUI e motori di elaborazione dal pacchetto locale…' 55
        $req = Join-Path $InstallDir 'app\requirements.txt'
        $env:PIP_NO_INDEX = '1'
        $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
        Run-Process $python @('-m','pip','install','--no-index','--disable-pip-version-check','--no-warn-script-location','--find-links',("`"$WheelsDir`""),'-r',("`"$req`""))

        Set-Stage 'Verifico l’installazione…' 78
        $verify = 'import numpy, scipy, cv2, rawpy, tifffile, astropy, exifread, PySide6, requests; print("ok")'
        Run-Process $python @('-c',("`"$verify`""))

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

        Remove-Item $WheelsDir -Recurse -Force -ErrorAction SilentlyContinue
        Set-Stage 'Installazione offline completata.' 100
        Start-Sleep -Milliseconds 500
        $win.Close()
        $go = [System.Windows.MessageBox]::Show('AstroStack è installato. Vuoi avviarlo ora?','AstroStack',[System.Windows.MessageBoxButton]::YesNo,[System.Windows.MessageBoxImage]::Information)
        if ($go -eq [System.Windows.MessageBoxResult]::Yes) { Start-Process $launcher }
    }
    catch {
        Remove-Item $WheelsDir -Recurse -Force -ErrorAction SilentlyContinue
        $win.Close()
        [System.Windows.MessageBox]::Show("Installazione non riuscita:`n`n$($_.Exception.Message)",'AstroStack Setup Offline',[System.Windows.MessageBoxButton]::OK,[System.Windows.MessageBoxImage]::Error) | Out-Null
    }
})

$win.ShowDialog() | Out-Null
