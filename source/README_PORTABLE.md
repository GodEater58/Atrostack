# AstroStack 1.4.0 Preview — Windows Portable

La distribuzione Windows ufficiale della serie 1.4 è un **pacchetto ZIP portable**.

## Contenuto del pacchetto

```text
AstroStack_1.4.0_preview_Windows_x64/
├─ AstroStack.exe
├─ AstroStack-Debug.cmd
├─ README.txt
├─ app/
├─ runtime/
└─ logs/
```

`AstroStack.exe` è un piccolo launcher Windows nativo. Avvia il runtime Python privato incluso tramite `pythonw.exe`, senza mostrare finestre console.

Il launcher usa percorsi relativi alla propria cartella, quindi il pacchetto può essere spostato dopo l'estrazione senza reinstallare nulla.

## Diagnostica

L'output dell'applicazione viene scritto in `logs/AstroStack.log`. Per una sessione diagnostica interattiva si può avviare `AstroStack-Debug.cmd`, che usa `runtime\python.exe` e mantiene visibile la console.

## Build

Prerequisiti sulla macchina che crea il pacchetto:

- Python 3.12+
- Go 1.23+
- connessione Internet durante la build

```powershell
./source/build_portable.ps1 -Version "1.4.0_preview"
```

Output:

- `source/AstroStack_1.4.0_preview_Windows_x64.zip`
- `source/AstroStack_1.4.0_preview_Windows_x64.zip.sha256.txt`

Il PC che usa AstroStack non deve installare Python e non deve scaricare dipendenze al primo avvio.
