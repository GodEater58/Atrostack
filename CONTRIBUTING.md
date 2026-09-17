# Contribuire ad AstroStack

Grazie per l'interesse nel progetto.

## Versione di sviluppo

Il ramo di sviluppo attuale è **AstroStack 1.4.0-preview**.

## Struttura principale

Il sorgente attuale dell'applicazione si trova in `source/app/`.

- `source/app/astrostack/` — codice dell'applicazione
- `source/app/tests/` — test e regressioni
- `source/build_offline.ps1` — build dell'installer Windows offline
- `.github/workflows/ci.yml` — test automatici
- `.github/workflows/build-windows.yml` — build installer e release

## Ambiente di sviluppo

Richiede Python 3.12 per riprodurre l'ambiente usato in CI.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r source/app/requirements.txt
$env:PYTHONPATH = "$PWD\source\app"
python source/app/main.py
```

## Test

Prima di proporre una modifica, eseguire almeno:

```powershell
python source/app/tests/test_diagnostics.py
python source/app/tests/regression_editor_stack_v12.py
python source/app/tests/regression_live_drizzle.py
python source/app/tests/synthetic_test.py
```

Per il test GUI headless:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python source/app/tests/smoke_gui.py
```

## Pull request

Mantieni ogni PR focalizzata su un singolo obiettivo. Descrivi cosa cambia, come è stato testato e allega screenshot quando la modifica riguarda l'interfaccia.

Non includere nella PR build locali, runtime Python, file `.exe`, ZIP, log o crash report: sono esclusi dal `.gitignore` e gli installer vengono generati da GitHub Actions.

Quando descrivi funzioni o obiettivi del progetto, preferisci descrizioni tecniche dirette ed evita confronti promozionali con applicazioni di terze parti.
