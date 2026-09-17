# AstroStack 1.4.0 Preview

AstroStack è un'app desktop per stacking ed editing di immagini astronomiche.

Il sorgente mantenuto dell'applicazione è in questa cartella. Le due aree principali sono:

- **Stack** — calibrazione, valutazione qualità, allineamento, combinazione e sviluppo del risultato.
- **Editor** — apertura e sviluppo diretto di TIFF, FITS, PNG, JPG e RAW senza dover eseguire prima uno stack.

## Funzioni

| Area | Funzioni principali |
|---|---|
| Import | RAW, FITS, TIFF, PNG e JPG |
| Calibrazione | Bias, dark, flat, hot pixel e correzione cosmetica |
| Qualità | Stelle, FWHM, eccentricità, rumore, saturazione, trasparenza e peso |
| Registrazione | Matching stellare, RANSAC, trasformazioni geometriche e correlazione di fase |
| Stacking | Media, mediana, rejection statistica, live stacking e drizzle |
| Fondo cielo | Rimozione gradiente e neutralizzazione |
| Colore | Bilanciamento, calibrazione colore e controlli HSL |
| Editor | Stretch, curve, dettagli, denoise, deconvoluzione, livelli, maschere e preset |
| Export | TIFF, PNG, JPG e FITS |
| Progetti | Sessioni `.astrostack`, snapshot, livelli, maschere e preferenze |

## Avvio da sorgente

Richiede Python 3.12 per riprodurre l'ambiente usato dal CI.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Test

```powershell
python tests/test_diagnostics.py
python tests/regression_editor_stack_v12.py
python tests/regression_live_drizzle.py
python tests/synthetic_test.py
```

Test GUI headless:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python tests/smoke_gui.py
```

## Editor

L'Editor è utilizzabile sia come fase successiva allo stack sia come ambiente standalone. Include controlli non distruttivi per esposizione, contrasto, alte luci, ombre, bianchi, neri, temperatura, tinta, vividezza, saturazione, HSL, curve, chiarezza, riduzione velatura, nitidezza, riduzione rumore, riduzione stelle, wavelet, deconvoluzione, vignettatura, grana, geometria, preset, cronologia, snapshot e confronto prima/dopo.

## Stack

Il flusso di stacking supporta master frame, calibrazione, valutazione automatica della qualità, esclusione o pesatura dei frame peggiori, allineamento sub-pixel, diversi metodi di combinazione, rimozione gradiente, neutralizzazione del cielo, calibrazione colore, crop automatico, live stacking, drizzle e scie stellari.

## Strumenti esterni opzionali

AstroStack può richiamare strumenti esterni configurati dall'utente per elaborazioni specialistiche. Questi strumenti non sono inclusi nel pacchetto e mantengono licenze e condizioni d'uso proprie.

## Versione 1.4

La serie **1.4.0-preview** è il ramo di sviluppo attuale. Gli interventi previsti comprendono miglioramenti al ridimensionamento dell'interfaccia ad alta risoluzione, scorciatoie, pannelli ridimensionabili e un Editor standalone più completo. Una funzione viene considerata completata solo dopo test e integrazione.
