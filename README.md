# AstroStack

**AstroStack** è un'app desktop per Windows dedicata allo stacking e allo sviluppo di immagini astronomiche.

La versione attuale del ramo di sviluppo è **1.4.0-preview**.

Include due ambienti principali:

- **Stack** — calibrazione, valutazione, allineamento e combinazione automatica dei frame.
- **Editor** — sviluppo standalone di TIFF, FITS, PNG, JPG e RAW, senza dover eseguire prima uno stack.

> Il sorgente mantenuto dell'applicazione si trova in `source/app/`.

## Download e avvio su Windows

AstroStack 1.4 viene distribuito come **ZIP portable completo**, senza installer.

Il pacchetto contiene:

- `AstroStack.exe` — launcher Windows nativo, senza finestra console;
- `app/` — applicazione AstroStack;
- `runtime/` — runtime Python privato e dipendenze;
- `AstroStack-Debug.cmd` — avvio diagnostico con console;
- `logs/` — log locali dell'applicazione.

Per usarlo:

1. scarica `AstroStack_1.4.0_preview_Windows_x64.zip`;
2. estrai completamente lo ZIP in una cartella;
3. avvia `AstroStack.exe`.

Non serve installare Python e non serve eseguire un setup. Il launcher usa esclusivamente il runtime incluso nel pacchetto e nasconde la console Python durante l'uso normale.

In caso di problema, controlla `logs/AstroStack.log` oppure avvia `AstroStack-Debug.cmd` per vedere i messaggi in tempo reale.

## Funzioni principali

| Area | Funzioni |
|---|---|
| RAW e FITS | CR2, CR3, NEF, ARW, DNG, RAF, ORF, PEF, RW2, FITS, TIFF, PNG e JPG |
| Calibrazione | Bias, dark e flat; master frame; riscalatura dark; hot pixel e correzione cosmetica |
| Qualità frame | Stelle, FWHM, eccentricità, rumore, saturazione, trasparenza, punteggio e peso |
| Registrazione | Matching stelle + RANSAC, rotazione, scala, traslazione e fallback a correlazione di fase |
| Stacking | Automatico, Kappa-sigma, Winsorized Sigma, Linear-fit clipping, mediana e media |
| Drizzle / Live | Drizzle 2× e live stacking incrementale |
| Gradiente | Rimozione dell'inquinamento luminoso e neutralizzazione del fondo |
| Editor | Stretch, esposizione, contrasto, HSL, colore, curve, nitidezza, denoise, wavelet e deconvoluzione |
| Livelli | Fusione immagini, opacità, metodi di fusione e maschere |
| Export | TIFF, PNG, JPG e FITS; preset web/stampa e controllo risoluzione |
| Progetti | Salvataggio sessione `.astrostack`, impostazioni, livelli, maschere e snapshot |
| Strumenti esterni | Integrazioni opzionali configurabili dall'utente per elaborazioni specialistiche |

## Avvio da sorgente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r source/app/requirements.txt
$env:PYTHONPATH = "$PWD\source\app"
python source/app/main.py
```

L'ambiente di riferimento usa Python 3.12.

## Build del pacchetto portable

Su Windows, con Python 3.12 e Go installati:

```powershell
./source/build_portable.ps1 -Version "1.4.0_preview"
```

La build:

1. compila `AstroStack.exe` come launcher Windows senza console;
2. copia il sorgente mantenuto;
3. scarica Python embeddable;
4. prepara le dipendenze nel runtime privato;
5. verifica il runtime incluso;
6. crea lo ZIP portable e il checksum SHA-256.

GitHub Actions può eseguire la stessa build manualmente tramite `.github/workflows/build-portable.yml`. Le build non vengono avviate automaticamente a ogni commit.

## Test

Il CI è volutamente **manuale** durante lo sviluppo della 1.4, per evitare l'avvio di un workflow a ogni singolo commit.

```powershell
python source/app/tests/test_diagnostics.py
python source/app/tests/regression_editor_stack_v12.py
python source/app/tests/regression_live_drizzle.py
python source/app/tests/synthetic_test.py
```

Test GUI headless:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python source/app/tests/smoke_gui.py
```

## Versione 1.4

La serie 1.4 è il ramo di sviluppo attuale. Gli interventi previsti includono miglioramenti al ridimensionamento dell'interfaccia ad alta risoluzione, scorciatoie, pannelli più flessibili e un Editor standalone più completo. Le singole funzioni vengono considerate completate solo dopo test e integrazione.

## Note sui riferimenti esterni

La documentazione descrive AstroStack direttamente per le sue funzioni. Le eventuali integrazioni con strumenti esterni sono opzionali, separate dal core e soggette alle rispettive licenze.

## Font

L'interfaccia utilizza IBM Plex Sans / Mono. La relativa licenza è inclusa nel file `LICENSE-IBM-Plex.txt`.
