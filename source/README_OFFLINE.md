# AstroStack 1.2.0 Preview — Offline Windows Builder

Questo pacchetto costruisce un singolo installer Windows x64 completamente offline.

## Cosa contiene il Setup finale

- AstroStack 1.2.0 Preview
- Python 3.12.10 x64 privato
- tutte le wheel necessarie (NumPy, SciPy, OpenCV, RawPy, TIFFFile, Astropy, ExifRead, PySide6, Requests e dipendenze)
- launcher AstroStack.exe
- collegamenti Desktop e Start
- disinstallazione da App installate
- associazione `.astrostack`

Durante l'installazione finale `pip` viene eseguito con `--no-index` e `PIP_NO_INDEX=1`: il Setup non consulta PyPI e non richiede Internet.

## Metodo consigliato: GitHub Actions

1. carica questa cartella in un repository GitHub;
2. apri **Actions → Build AstroStack Offline Windows**;
3. premi **Run workflow**;
4. scarica l'artifact `AstroStack-1.2.0-preview-offline-windows`.

Il runner Windows scarica Python e le dipendenze *durante la build*, poi le incorpora nel singolo installer. L'utente finale non deve scaricare nulla.

## Build locale su Windows

Prerequisiti solo sulla macchina che CREA il Setup:
- Python 3.12+
- Go 1.23+
- connessione Internet durante la build

Da PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_offline.ps1
```

Output:

- `AstroStack_Setup_Offline_1.2.0_preview.exe`
- relativo checksum `.sha256.txt`

## Installazione finale

Il Setup installa per utente in:

`%LOCALAPPDATA%\Programs\AstroStack`

Non richiede privilegi amministrativi. Dopo la build, il PC su cui viene installato AstroStack può essere completamente offline.

## Nota SmartScreen

Finché l'eseguibile non è firmato con un certificato Authenticode, Windows può mostrare l'avviso SmartScreen. La firma digitale va aggiunta prima di una distribuzione pubblica.
