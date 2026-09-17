# AstroStack

[![AstroStack CI](https://github.com/GodEater58/Atrostack/actions/workflows/ci.yml/badge.svg)](https://github.com/GodEater58/Atrostack/actions/workflows/ci.yml)

**AstroStack** è un'app desktop per Windows dedicata allo stacking e allo sviluppo di immagini astronomiche.

Include due ambienti principali:

- **Stack** — calibrazione, valutazione, allineamento e combinazione automatica dei frame.
- **Editor** — sviluppo standalone di TIFF, FITS, PNG, JPG e RAW, senza dover eseguire prima uno stack.

La versione attuale del ramo di sviluppo è **1.4.0-preview**.

> Il sorgente mantenuto dell'applicazione si trova in `source/app/`. I file presenti nella root sono mantenuti per compatibilità con le versioni precedenti e verranno gradualmente consolidati.

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

## Installazione su Windows

### Installer offline

L'installer Windows include un **runtime Python privato** e le dipendenze necessarie all'applicazione.

L'utente finale non deve installare Python né modificare il proprio ambiente di sistema.

Le build vengono generate automaticamente dal workflow **Build Windows offline installer**. Le versioni taggate vengono pubblicate nella sezione **Releases**, insieme al checksum SHA-256.

Se Windows segnala l'eseguibile come non firmato, è perché le build preview non dispongono ancora di firma digitale commerciale.

### Avvio da sorgente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r source/app/requirements.txt
$env:PYTHONPATH = "$PWD\source\app"
python source/app/main.py
```

L'ambiente CI usa **Python 3.12**.

## Uso rapido

1. Avvia AstroStack.
2. Scegli **Stack** oppure **Editor** dalla schermata iniziale.
3. In modalità Stack aggiungi i frame **Light**, ed eventualmente **Dark**, **Flat** e **Bias**.
4. Premi **Stack**.
5. Controlla qualità, FWHM, spostamento, rotazione e motivi di eventuale esclusione dei frame.
6. Rifinisci il risultato nell'Editor.
7. Esporta in TIFF, PNG, JPG o FITS.

### Formati di esportazione

- **TIFF 16 bit sviluppato** — pronto per ulteriori elaborazioni fotografiche.
- **TIFF/FITS lineare** — conserva il risultato lineare per lavorazioni successive senza perdere il segnale debole.

Un file lineare può apparire quasi nero in un normale visualizzatore: è previsto.

## Stack

Il flusso di stacking può includere master bias, dark e flat, correzione hot pixel, valutazione automatica dei frame, esclusione o pesatura dei frame peggiori, allineamento sub-pixel, diversi algoritmi di combinazione, rimozione gradiente, neutralizzazione del cielo, calibrazione colore sulle stelle, ritaglio automatico, live stacking, drizzle 2× e scie stellari.

Con meno di cinque light, i metodi di rejection statistica sono poco affidabili: AstroStack può passare automaticamente a una combinazione più adatta.

## Editor

L'Editor può essere usato sia dopo lo stack sia come ambiente standalone.

Comprende stretch MTF, Arcsinh, ibrido e Masked Stretch; esposizione e contrasto; alte luci, ombre, bianchi e neri; temperatura, tinta, vividezza e saturazione; HSL; curve; chiarezza e riduzione velatura; nitidezza; riduzione rumore luminanza/colore; riduzione stelle; wavelet e deconvoluzione; vignettatura e grana; rotazione, crop e riflessioni; preset, cronologia, snapshot e confronto prima/dopo.

Le regolazioni sono non distruttive e vengono applicate a piena risoluzione durante l'esportazione.

## Progetti e sessioni

I file `.astrostack` possono conservare elenco dei frame, opzioni di stacking, sviluppo, livelli e maschere, snapshot, workspace attivo e modalità semplice/avanzata.

AstroStack include inoltre lo smistamento automatico di Light, Dark, Flat e Bias e una libreria dei master riutilizzabili.

## Strumenti esterni opzionali

AstroStack può richiamare strumenti esterni configurati dall'utente per funzioni avanzate come riduzione del rumore, rimozione del gradiente, separazione stelle/sfondo e plate solving.

Questi strumenti non sono inclusi automaticamente nell'installer AstroStack e mantengono le proprie licenze e condizioni d'uso.

## Test automatici

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

Il workflow `ci.yml` esegue automaticamente i test sulle pull request e sulle modifiche al sorgente.

## Build dell'installer

Su Windows, con Python 3.12 e Go installati:

```powershell
./source/build_offline.ps1 -Version "1.4.0_preview"
```

La build compila il launcher, prepara un runtime isolato, include le dipendenze, verifica il runtime, crea l'installer offline e genera il checksum SHA-256.

GitHub Actions automatizza lo stesso processo tramite `.github/workflows/build-windows.yml`.

## Struttura del repository

```text
source/
├─ app/                    sorgente AstroStack mantenuto
│  ├─ astrostack/
│  │  ├─ core/             pipeline, stacking, calibrazione, editor
│  │  └─ gui/              interfaccia desktop
│  ├─ tests/               test automatici e regressioni
│  ├─ main.py              entry point applicazione
│  └─ requirements.txt
├─ launcher/               launcher Windows
├─ setup/                  installer offline
└─ build_offline.ps1       build completa Windows

.github/workflows/
├─ ci.yml                  test automatici
└─ build-windows.yml       installer + artifact/release
```

## Sviluppo 1.4

La serie 1.4 è il ramo di sviluppo attuale. Gli interventi previsti includono miglioramenti al ridimensionamento dell'interfaccia ad alta risoluzione, scorciatoie, pannelli più flessibili e un Editor standalone più completo. Le singole funzioni vengono considerate completate solo dopo test e integrazione nel ramo principale.

## Diagnostica

AstroStack registra localmente informazioni di avvio e crash report per facilitare il debug. I log locali e i report di crash sono esclusi dal repository tramite `.gitignore`.

Quando segnali un bug, allega se possibile il crash report e indica versione di AstroStack, Windows, RAM, GPU e tipo/numero di frame utilizzati.

## Contribuire

Consulta [`CONTRIBUTING.md`](CONTRIBUTING.md) per ambiente di sviluppo, test e linee guida per le pull request.

Le segnalazioni bug e le richieste di funzione possono essere aperte tramite i template GitHub presenti nel repository.

## Font

L'interfaccia utilizza IBM Plex Sans / Mono. La relativa licenza è inclusa nel file `LICENSE-IBM-Plex.txt`.
