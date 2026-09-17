# AstroStack 1.4.0 Preview — Offline Windows Builder

Questo pacchetto costruisce un singolo installer Windows x64 completamente offline per l'utente finale.

## Cosa contiene il setup finale

- AstroStack 1.4.0 Preview
- runtime Python 3.12.10 x64 privato
- dipendenze necessarie all'applicazione
- launcher `AstroStack.exe`
- collegamenti Desktop e Start
- disinstallazione da App installate
- associazione `.astrostack`

Le dipendenze vengono scaricate e incorporate durante la build. Il PC su cui viene installato AstroStack non deve scaricare nulla.

## Metodo consigliato: GitHub Actions

1. apri **Actions → Build Windows offline installer**;
2. premi **Run workflow**;
3. lascia la versione predefinita `1.4.0_preview` oppure specificane una;
4. scarica l'artifact generato.

## Build locale su Windows

Prerequisiti sulla sola macchina che crea il setup:

- Python 3.12+
- Go 1.23+
- connessione Internet durante la build

Da PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\source\build_offline.ps1 -Version "1.4.0_preview"
```

Output previsto:

- `source\AstroStack_Setup_Offline_1.4.0_preview.exe`
- relativo checksum `.sha256.txt`

## Installazione finale

Il setup installa per utente in:

`%LOCALAPPDATA%\Programs\AstroStack`

Non richiede privilegi amministrativi. Dopo la build, il PC di destinazione può essere completamente offline.

## Firma digitale

Finché l'eseguibile non è firmato con un certificato Authenticode, Windows può mostrare un avviso per l'eseguibile non firmato.
