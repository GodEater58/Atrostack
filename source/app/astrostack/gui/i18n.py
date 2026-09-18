"""Lingua dell'interfaccia: italiano / inglese, con cambio in tempo reale.

Le stringhe sorgente sono in italiano. `tr()` le traduce in inglese quando la
lingua è "en"; `retranslate()` percorre l'albero dei widget e riscrive testi,
segnaposto, voci dei menu a tendina e popup di aiuto, senza ricostruire nulla.
"""
from __future__ import annotations

import re
from typing import Callable

from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox, QDockWidget, QGroupBox, QLabel,
                               QLineEdit, QListWidget, QTableWidget, QTabWidget, QWidget)

_lang = "it"
_listeners: list[Callable[[str], None]] = []


def language() -> str:
    return _lang


def set_language(lang: str):
    global _lang
    _lang = "en" if str(lang).lower().startswith("en") else "it"
    for fn in list(_listeners):
        try:
            fn(_lang)
        except Exception:
            pass


def on_language_changed(fn: Callable[[str], None]):
    _listeners.append(fn)


# ----------------------------------------------------------------------------
# dizionario italiano -> inglese
# ----------------------------------------------------------------------------
DICT: dict[str, str] = {
    # --- intestazione e pulsanti principali
    "Trascina i file nelle zone a sinistra, poi premi Stack.": "Drop your files in the zones on the left, then press Stack.",
    "Apri progetto…": "Open project…", "Salva progetto…": "Save project…", "Smista file…": "Sort files…",
    "Live": "Live", "Apri immagine…": "Open image…", "Importa sessione…": "Import session…",
    "Frame": "Frames", "Registro": "Log", "Sviluppo": "Develop", "Livelli": "Layers",
    "▶  Stack": "▶  Stack", "In elaborazione…": "Working…", "Annulla": "Cancel", "Esporta…": "Export…",
    "Prima / Dopo": "Before / After", "Adatta": "Fit", "100 %": "100 %",
    "Stretch automatico": "Auto stretch", "Lineare": "Linear", "Già stirata (StarNet)": "Already stretched (StarNet)",
    # --- zone
    "Light": "Light", "Dark": "Dark", "Flat": "Flat", "Bias / Offset": "Bias / Offset",
    "Le foto del cielo (obbligatorie)": "Your sky shots (required)",
    "Stessa posa e ISO dei light, tappo sull'obiettivo": "Same exposure and ISO as the lights, lens cap on",
    "Campo uniforme: correggono vignettatura e polvere": "Evenly lit field: fixes vignetting and dust",
    "Posa più breve possibile, tappo sull'obiettivo": "Shortest possible exposure, lens cap on",
    "Aggiungi file": "Add files", "Cartella": "Folder", "Svuota": "Clear",
    "nessun file": "no files",
    # --- opzioni
    "Opzioni": "Options", "Combinazione": "Combination", "Kappa-sigma (consigliato)": "Kappa-sigma (recommended)",
    "Sigma winsorizzato": "Winsorized sigma", "Mediana": "Median", "Media semplice": "Simple average",
    "Scie stellari (senza allineamento)": "Star trails (no alignment)",
    "Scarta i frame peggiori": "Discard the worst frames", "Severità": "Strictness",
    "mai": "never", "leggera": "light", "normale": "normal", "severa": "strict",
    "Pesa i frame in base alla qualità": "Weight frames by quality",
    "Rimuovi l'inquinamento luminoso": "Remove light pollution",
    "Grado del modello": "Model degree", "Neutralizza il fondo cielo": "Neutralise the sky background",
    "Calibra i colori sulle stelle": "Colour-calibrate on the stars",
    "Paesaggio: primo piano nitido": "Landscape: sharp foreground",
    "Avanzate ▸": "Advanced ▸", "Avanzate ▾": "Advanced ▾", "Avanzate": "Advanced",
    "Bianco": "White balance", "Luce diurna (consigliato)": "Daylight (recommended)", "Come scattato": "As shot",
    "Nessuno": "None", "Kappa basso (σ)": "Low kappa (σ)", "Kappa alto (σ)": "High kappa (σ)",
    "Iterazioni rigetto": "Rejection passes", "Debayer": "Debayer", "Piena risoluzione": "Full resolution",
    "Super-pixel (½ risoluzione)": "Super-pixel (½ resolution)", "Interpolazione": "Interpolation",
    "Cubica (consigliata)": "Cubic (recommended)", "Lanczos (più nitida)": "Lanczos (sharper)",
    "Lineare (veloce)": "Linear (fast)", "Soglia hot pixel": "Hot pixel threshold",
    "Hot pixel automatici senza dark": "Automatic hot pixels without darks",
    "Riscala i dark (posa diversa)": "Scale darks (different exposure)",
    "Ritaglia i bordi non coperti": "Crop uncovered edges", "Drizzle": "Drizzle",
    "1× normale": "1× normal", "2× super-risoluzione (serve dithering)": "2× super-resolution (needs dithering)",
    "Libreria master dark/bias automatica": "Automatic dark/bias master library",
    "Libreria": "Library", "cartella predefinita (AppData\\AstroStack\\master)": "default folder (AppData\\AstroStack\\master)",
    "Thread": "Threads", "Memoria/banda": "Memory/band", "Cache": "Cache",
    "cartella temporanea": "temporary folder", "Cartella per la cache temporanea": "Folder for the temporary cache",
    "Cartella della libreria dei master": "Master library folder",
    # --- strumenti IA
    "Strumenti IA ▸": "AI tools ▸", "Strumenti IA ▾": "AI tools ▾", "Strumenti IA": "AI tools",
    "Forza denoise": "Denoise strength", "Usa la scheda video (GPU)": "Use the graphics card (GPU)",
    "Denoise IA": "AI denoise", "Gradiente IA": "AI gradient", "Rimuovi le stelle": "Remove the stars",
    "Riconosci oggetti": "Identify objects", "Mostra etichette": "Show labels",
    "Annulla ultima modifica": "Undo last change", "chiave API (gratuita)": "API key (free)",
    "GraXpert non trovato: scaricalo da graxpert.com (gratuito) e indica il file .exe":
        "GraXpert not found: download it from graxpert.com (free) and point to the .exe file",
    "StarNet++ non trovato: scaricalo da starnetastro.com e indica starnet++.exe":
        "StarNet++ not found: download it from starnetastro.com and point to starnet++.exe",
    "Dov'è GraXpert?": "Where is GraXpert?", "Dov'è StarNet++?": "Where is StarNet++?",
    # --- sviluppo
    "Sviluppo attivo": "Develop on", "Auto": "Auto", "Reimposta": "Reset", "Reimposta HSL": "Reset HSL",
    "Reimposta curva": "Reset curve", "Salva preset…": "Save preset…", "Carica preset…": "Load preset…",
    "Base": "Basic", "Colore": "Colour", "Dettaglio": "Detail", "Effetti": "Effects", "Geometria": "Geometry",
    "Tipo di stretch": "Stretch type", "Classico (MTF)": "Classic (MTF)",
    "Arcsinh: stelle colorate": "Arcsinh: colourful stars", "Ibrido (metà e metà)": "Hybrid (half and half)",
    "Fondo cielo": "Sky background", "Taglio ombre": "Shadow clipping", "Esposizione": "Exposure",
    "Contrasto": "Contrast", "Alte luci": "Highlights", "Ombre": "Shadows", "Bianchi": "Whites", "Neri": "Blacks",
    "Temperatura": "Temperature", "Tinta": "Tint", "Vividezza": "Vibrance", "Saturazione": "Saturation",
    "HSL — colore per colore": "HSL — colour by colour", "Tonalità": "Hue", "Luminanza": "Luminance",
    "Rosso": "Red", "Arancione": "Orange", "Giallo": "Yellow", "Verde": "Green", "Acqua": "Aqua",
    "Blu": "Blue", "Viola": "Purple", "Magenta": "Magenta",
    "Chiarezza": "Clarity", "Riduci velatura": "Dehaze", "Nitidezza": "Sharpening", "Raggio": "Radius",
    "Mascheratura": "Masking", "Rumore luminanza": "Luminance noise", "Rumore colore": "Colour noise",
    "Riduzione stelle": "Star reduction", "Vignettatura": "Vignette", "Grana": "Grain",
    "Rotazione": "Rotation", "Elimina i bordi neri della rotazione": "Remove the black corners after rotation",
    "Ritaglio %": "Crop %", "Rifletti ↔": "Flip ↔", "Rifletti ↕": "Flip ↕",
    "Curva dei toni": "Tone curve", "Salva preset di sviluppo": "Save develop preset",
    "Carica preset di sviluppo": "Load develop preset",
    # --- livelli
    "Livello selezionato": "Selected layer", "Opacità": "Opacity", "Fusione": "Blend",
    "Posizione": "Position", "Scala": "Scale", "Maschera": "Mask", "Tipo": "Type", "Inverti": "Invert",
    "Mostra in rosso": "Show in red", "Sfumatura bordo": "Edge feather", "Sfumatura": "Gradient",
    "Luminosità": "Luminosity", "Dimensione": "Size", "Durezza": "Hardness",
    "Cancella invece di aggiungere": "Erase instead of adding", "Dipingi sull'anteprima": "Paint on the preview",
    "Cancella tutto": "Clear all", "Carica maschera da file…": "Load mask from file…",
    "Aggiungi immagine…": "Add image…", "Duplica": "Duplicate", "Elimina": "Delete",
    "Normale": "Normal", "Schiarisci": "Lighten", "Scurisci": "Darken", "Moltiplica": "Multiply",
    "Scherma": "Screen", "Sovrapponi": "Overlay", "Luce soffusa": "Soft light", "Somma": "Add",
    "Differenza": "Difference", "Nessuna": "None", "Sfumatura lineare": "Linear gradient",
    "Luminosità del livello": "Layer luminosity", "Pennello": "Brush",
    "Primo piano automatico": "Automatic foreground", "Da file (scala di grigi)": "From file (greyscale)",
    "da": "from", "a": "to", "scuro": "dark", "chiaro": "light", "orizzontale": "horizontal",
    "Orizzontale (da sinistra a destra)": "Horizontal (left to right)",
    "Il livello 1 è la base (lo stack o l'immagine aperta). Aggiungi una foto per il primo piano, scegli fusione e maschera; il pannello Sviluppo regola il livello selezionato.":
        "Layer 1 is the base (the stack or the image you opened). Add a photo for the foreground, choose a blend mode and a mask; the Develop panel adjusts the selected layer.",
    # --- tabella frame
    "File": "File", "Stato": "Status", "Stelle": "Stars", "FWHM px": "FWHM px", "Ecc.": "Ecc.",
    "Qualità": "Quality", "Peso": "Weight", "Spostamento": "Shift", "RMS px": "RMS px",
    "Allineamento": "Alignment", "Posa": "Exposure", "ISO": "ISO", "Hot px": "Hot px", "Note": "Notes",
    "in coda": "queued", "ok": "ok", "scartato": "discarded", "errore": "error", "riferimento": "reference",
    "stelle": "stars", "fase": "phase", "identità": "identity",
    # --- esportazione
    "Esporta immagine": "Export image", "Formato": "Format", "TIFF 16 bit (massima qualità)": "TIFF 16-bit (best quality)",
    "TIFF 8 bit": "TIFF 8-bit", "PNG 16 bit": "PNG 16-bit", "PNG 8 bit": "PNG 8-bit",
    "JPG (per web e social)": "JPG (for web and social)",
    "FITS lineare (senza sviluppo, per ulteriori elaborazioni)": "Linear FITS (no develop, for further processing)",
    "Qualità JPG": "JPG quality", "Compressione PNG": "PNG compression", "Compressione TIFF": "TIFF compression",
    "Senza perdita (zlib): file più piccolo": "Lossless (zlib): smaller file",
    "Nessuna: file più grande, apertura più veloce": "None: bigger file, faster to open",
    "Risoluzione": "Resolution", "Originale": "Original", "Percentuale": "Percentage",
    "Larghezza in pixel": "Width in pixels", "Ingrandimento": "Upscaling", "Lanczos (nitido)": "Lanczos (sharp)",
    "Cubico (morbido)": "Cubic (soft)", "Nitidezza in uscita": "Output sharpening",
    "Bassa": "Low", "Standard": "Standard", "Alta": "High",
    "Applica le regolazioni di Sviluppo": "Apply the Develop adjustments",
    "Dimensione finale": "Final size", "Esporta": "Export",
    # --- messaggi e titoli di finestre
    "Nessuna anteprima: carica i light e premi Stack.": "No preview yet: load your lights and press Stack.",
    "Pronto: aggiungi almeno un light.": "Ready: add at least one light.",
    "Annullamento in corso…": "Cancelling…", "Annullato.": "Cancelled.",
    "Elaborazione annullata": "Processing cancelled", "Modifica annullata.": "Change undone.",
    "Stacking non riuscito": "Stacking failed", "Sviluppo a piena risoluzione…": "Developing at full resolution…",
    "Anteprima al 100 % con sviluppo applicato.": "100 % preview with the develop settings applied.",
    "Aggiorno gradiente e fondo cielo…": "Updating gradient and sky background…",
    "Auto: neri e bianchi regolati": "Auto: blacks and whites adjusted",
    "Scrittura del file…": "Writing the file…", "Progetto salvato": "Project saved",
    "Progetto aperto": "Project opened", "Live disattivato.": "Live off.",
    "Nessun file riconosciuto": "No files recognised", "Oggetti riconosciuti:": "Objects identified:",
    "Stelle rimosse: salva per avere anche il file delle sole stelle":
        "Stars removed: export to also get the stars-only file",
    "Stelle rimosse (immagine stirata). Salvando, le sole stelle vanno in un file a parte.":
        "Stars removed (stretched image). On export the stars go to a separate file.",
    "Gradiente e colori si regolano prima degli strumenti IA: usa 'Annulla ultima modifica'.":
        "Gradient and colours must be set before the AI tools: use 'Undo last change'.",
    "Alcuni file del progetto non sono stati trovati (vedi Registro)":
        "Some project files were not found (see the Log)",
    "Apertura non riuscita": "Could not open", "Apertura del progetto non riuscita": "Could not open the project",
    "Salvataggio del progetto non riuscito": "Could not save the project",
    "Salvataggio non riuscito": "Could not save", "Esportazione non riuscita": "Export failed",
    "Non c'è ancora nulla da salvare: carica i file o fai lo stack.":
        "There is nothing to save yet: load your files or run the stack.",
    "Prima serve un'immagine base: fai lo stack o usa Apri immagine…":
        "You need a base image first: run the stack or use Open image…",
    "Stacking in corso": "Stacking in progress",
    "Vuoi interrompere lo stacking e uscire?": "Stop the stacking and quit?",
    "Progetto": "Project", "Salva progetto": "Save project", "Apri progetto": "Open project",
    "Salva il risultato": "Save the result", "Apri un'immagine da sviluppare": "Open an image to develop",
    "Aggiungi un'immagine come livello": "Add an image as a layer",
    "Carica una maschera (bianco = visibile)": "Load a mask (white = visible)",
    "Cartella della sessione (con light / dark / flat / bias)": "Session folder (with light / dark / flat / bias)",
    "Cartella da osservare (i light che arrivano)": "Folder to watch (incoming lights)",
    "Scegli i file da smistare (light, dark, flat, bias insieme)": "Choose the files to sort (lights, darks, flats, bias together)",
    "Rimozione stelle": "Star removal", "Riconoscimento oggetti": "Object identification",
    "Smistamento": "Sorting", "Progetto AstroStack (*.astrostack)": "AstroStack project (*.astrostack)",
    "Tutti (*)": "All (*)", "Tutti i file (*)": "All files (*)",
    "Immagini (*.tif *.tiff *.png *.jpg *.jpeg *.fits *.fit *.fts);;Tutti (*)":
        "Images (*.tif *.tiff *.png *.jpg *.jpeg *.fits *.fit *.fts);;All (*)",
    "Lingua dell'interfaccia: italiano o inglese": "Interface language: Italian or English",
    "Risultato finale": "Final result", "Pronto.": "Ready.",
    "corretto": "corrected", "non applicato": "not applied",
    "Nessun frame di calibrazione: correzione cosmetica automatica degli hot pixel":
        "No calibration frames: automatic cosmetic correction of the hot pixels",
    "ATTENZIONE: gradiente molto forte: se c'è un primo piano (alberi, orizzonte) prova grado 1 o disattiva la rimozione":
        "WARNING: very strong gradient: with a foreground (trees, horizon) try degree 1 or turn the removal off",
    "Scie stellari: nessun allineamento, combinazione con il pixel più luminoso":
        "Star trails: no alignment, the brightest pixel wins",
    "Drizzle 2x: uscita a doppia risoluzione (richiede frame ditherati)":
        "Drizzle 2x: output at double resolution (needs dithered frames)",
    "Lingua: italiano": "Lingua: italiano", "Language: English": "Language: English",
    "  (base)": "  (base)",
    "Scegli i file": "Choose the files", "Scegli la cartella dei": "Choose the folder of the",
    "Aggiunge tutti i file supportati della cartella (e delle sottocartelle).":
        "Adds every supported file in the folder (and its subfolders).",
    "Scegli uno o più file da aggiungere a questa zona.": "Pick one or more files to add to this zone.",
    "Toglie tutti i file da questa zona (i file su disco non vengono toccati).":
        "Removes every file from this zone (the files on disk are untouched).",
    "Esporta il risultato": "Export the result",
    "Lingua": "Language",
    "Cambia la lingua dell'interfaccia in tempo reale: italiano o inglese.":
        "Switches the interface language in real time: Italian or English.",
}

# stringhe dinamiche (numeri, nomi di file): regole con espressioni regolari
PATTERNS: list[tuple[re.Pattern, str]] = [(re.compile(p), r) for p, r in [
    (r"^(\d+) file$", r"\1 files"),
    (r"^(\d+) light pronti\.$", r"\1 lights ready."),
    (r"^Avvio: (\d+) light, (\d+) dark, (\d+) flat, (\d+) bias$", r"Start: \1 lights, \2 darks, \3 flats, \4 bias"),
    (r"^Calibrazione e analisi", "Calibration and analysis"),
    (r"^Allineamento$", "Alignment"), (r"^Anteprima$", "Preview"), (r"^Stacking$", "Stacking"),
    (r"^Gradiente$", "Gradient"), (r"^Primo piano$", "Foreground"),
    (r"^Master (bias|dark|flat)$", r"Master \1"),
    (r"^Anteprima: (\d+)/(\d+) frame$", r"Preview: \1/\2 frames"),
    (r"^(\d+) frame su (\d+)$", r"\1 of \2 frames"),
    (r"^(\d+) light, (\d+) dark, (\d+) flat, (\d+) bias$", r"\1 lights, \2 darks, \3 flats, \4 bias"),
    (r"^Primo frame calibrato$", "First calibrated frame"),
    (r"^Completato in (\d+) s: (\d+) frame su (\d+)", r"Completed in \1 s: \2 of \3 frames"),
    (r"^Stack completato  ·  (\d+) frame su (\d+)$", r"Stack complete  ·  \1 of \2 frames"),
    (r"^Risultato finale  ·  (\d+) frame su (\d+)$", r"Final result  ·  \1 of \2 frames"),
    (r"^Gradiente rilevato: ([\d.,]+) % del fondo \(S/N (\d+)\)$", r"Gradient detected: \1 % of the background (S/N \2)"),
    (r"^Gradiente trascurabile \(([\d.,]+) % del fondo\)$", r"Negligible gradient (\1 % of the background)"),
    (r"^Colori calibrati su (\d+) stelle \(R ×([\d.,]+), B ×([\d.,]+)\)$",
     r"Colours calibrated on \1 stars (R ×\2, B ×\3)"),
    (r"  ·  corretto$", "  ·  corrected"), (r"  ·  non applicato$", "  ·  not applied"),
    (r"^Salvato: (.+?)  \(come anteprima\)(.*)$", r"Saved: \1  (as previewed)\2"),
    (r"^Salvato: (.+?)  \(lineare\)(.*)$", r"Saved: \1  (linear)\2"),
    (r"^Salvato  ·  (.+)$", r"Saved  ·  \1"),
    (r"^Esportato: (.+)$", r"Exported: \1"),
    (r"^Aperta: (.+)$", r"Opened: \1"),
    (r"^Progetto salvato: (.+)$", r"Project saved: \1"),
    (r"^Progetto aperto: (.+)$", r"Project opened: \1"),
    (r"^Progetto: (.+)$", r"Project: \1"),
    (r"^Livello aggiunto: (.+)$", r"Layer added: \1"),
    (r"^Smistati: (.*)$", r"Sorted: \1"),
    (r"^Smistamento di (\d+) file…$", r"Sorting \1 files…"),
    (r"^(\d+)\. (.+?)  \(base\)$", r"\1. \2  (base)"),
    (r"^Riferimento: (.+?) \(FWHM ([\d.,]+) px, (\d+) stelle\)$", r"Reference: \1 (FWHM \2 px, \3 stars)"),
    (r"^Frame allineati: (\d+) su (\d+)$", r"Frames aligned: \1 of \2"),
    (r"^Qualità: FWHM mediana ([\d.,]+) px, scartati (\d+) frame$",
     r"Quality: median FWHM \1 px, \2 frames discarded"),
    (r"^Ritaglio automatico: (\d+)x(\d+) px$", r"Automatic crop: \1x\2 px"),
    (r"^Completato in (\d+) s con (\d+) frame$", r"Completed in \1 s with \2 frames"),
    (r"^Master (bias|dark|flat): (\d+) frame(.*)$", r"Master \1: \2 frames\3"),
    (r"^Pixel difettosi mappati dal master dark: (\d+)$", r"Defective pixels mapped from the master dark: \1"),
    (r"^Denoise IA applicato\.(.*)$", r"AI denoise applied.\1"),
    (r"^Gradiente IA applicato\.(.*)$", r"AI gradient applied.\1"),
    (r"^(Denoise IA|Gradiente IA|Rimozione stelle|Riconoscimento oggetti|Smistamento) in corso… \(può richiedere qualche minuto\)$",
     r"\1 in progress… (this can take a few minutes)"),
    (r"^(Denoise IA|Gradiente IA|Rimozione stelle|Riconoscimento oggetti|Smistamento) non riuscito(.*)$",
     r"\1 failed\2"),
    (r"^Live: (\d+) frame, ricalcolo lo stack$", r"Live: \1 frames, restacking"),
    (r"^Live: osservo (.+) \(controllo ogni 5 s\)$", r"Live: watching \1 (checking every 5 s)"),
    (r"^Riconosciuti (\d+) oggetti$", r"\1 objects identified"),
    (r"^(\d+) %$", r"\1 %"),
    (r"^([\d.,]+) px$", r"\1 px"),
    (r"^([\d.,]+) EV$", r"\1 EV"),
]]

# nomi degli strumenti usati nei messaggi dinamici
TOOL_NAMES = {"Denoise IA": "AI denoise", "Gradiente IA": "AI gradient", "Rimozione stelle": "Star removal",
              "Riconoscimento oggetti": "Object identification", "Smistamento": "Sorting"}


def tr(text) -> str:
    """Traduce una stringa italiana nella lingua corrente."""
    if text is None:
        return text
    s = str(text)
    if _lang == "it" or not s.strip():
        return s
    hit = DICT.get(s)
    if hit is not None:
        return hit
    if "  ·  " in s:
        return "  ·  ".join(tr(part) for part in s.split("  ·  "))
    hit = _tooltip_map().get(s)
    if hit is not None:
        return hit
    for rx, rep in PATTERNS:
        if rx.search(s):
            out = rx.sub(rep, s)
            for it_name, en_name in TOOL_NAMES.items():
                out = out.replace(it_name, en_name)
            return out
    return s


# ----------------------------------------------------------------------------
# popup di aiuto in inglese
# ----------------------------------------------------------------------------
_TIP_EN = {
    "OPTIONS": {
        "method": ("Combination", "How the pixels of the aligned frames are merged.<br>"
                   "• <b>Kappa-sigma</b>: average that rejects outliers (satellites, planes, cosmic rays, hot pixels). Best with 5 frames or more.<br>"
                   "• <b>Winsorized sigma</b>: outliers are clamped instead of rejected: slightly less noise.<br>"
                   "• <b>Median</b>: very robust but noisier (about 25 % more than the average).<br>"
                   "• <b>Simple average</b>: lowest noise but no rejection: satellite trails stay.<br>"
                   "• <b>Star trails</b>: no alignment, the brightest pixel wins."),
        "auto_reject": ("Automatic rejection", "Drops the worst frames (shaken, soft, cloudy, few stars) by comparing them with the session median.<br>"
                        "<b>On</b>: sharper result, fewer frames so slightly more noise.<br><b>Off</b>: every alignable frame is used."),
        "severity": ("Rejection strictness", "How much worse a frame must be before it is dropped.<br>"
                     "<b>Left</b>: only clearly ruined frames.<br><b>Right</b>: only the best ones are kept (never fewer than 40 %)."),
        "weights": ("Quality weights", "Frames with tighter stars and less noise count more in the average (weight 0.2 to 1)."),
        "gradient": ("Gradient removal", "Samples the sky background on a grid, excludes stars, nebulae and foreground, fits a model and subtracts it.<br>"
                     "Can be switched after the stack without recomputing."),
        "degree": ("Model degree", "How complex the gradient model is.<br><b>1</b>: tilted plane.<br><b>2</b>: recommended.<br>"
                   "<b>3–4</b>: complex gradients; with trees or a horizon in the frame they can create halos."),
        "neutralize": ("Neutralise the background", "Brings the sky background to the same level in all three channels: removes the colour cast."),
        "star_color": ("Colour-calibrate on the stars", "White reference = average colour of the unsaturated stars, using the average stellar colour. The background stays neutral."),
        "white_balance": ("White balance", "Coefficients read from the RAW file, applied before debayering.<br>"
                          "• <b>Daylight</b>: the camera's standard coefficients, identical for every shot (recommended).<br>"
                          "• <b>As shot</b>: the in-camera setting.<br>• <b>None</b>: raw data, green image."),
        "kappa_low": ("Low kappa", "Rejection threshold below the median, in standard deviations.<br><b>Lower</b> (2): aggressive.<br><b>Higher</b> (4–5): almost nothing rejected."),
        "kappa_high": ("High kappa", "Rejection threshold above the median: satellites, planes, cosmic rays, leftover hot pixels.<br><b>Lower</b> (2): aggressive, with few frames it can eat star cores."),
        "iterations": ("Rejection passes", "How many times rejection is repeated recomputing mean and sigma.<br><b>1</b>: fast. <b>2</b>: recommended. <b>3–5</b>: better on strong trails, slower."),
        "debayer": ("Debayer", "How colour is reconstructed from the sensor's Bayer mosaic.<br>• <b>Full resolution</b>: 16-bit edge-aware interpolation.<br>• <b>Super-pixel</b>: each 2×2 block becomes one pixel: half resolution, less noise."),
        "interp": ("Interpolation", "Resampling used during alignment.<br>• <b>Cubic</b>: balanced (recommended).<br>• <b>Lanczos</b>: sharper, can ring around bright stars.<br>• <b>Linear</b>: fastest, slightly softer."),
        "hot_sigma": ("Hot pixel threshold", "How far a pixel must exceed its neighbours (in sigma) to count as defective when no darks are loaded.<br><b>Lower</b> (3–4): fixes more, may touch tiny stars."),
        "auto_cosmetic": ("Automatic hot pixels", "With no master dark, isolated outlier pixels are found and replaced in every light.<br><b>Recommended</b> when you have no darks."),
        "dark_scaling": ("Scale darks", "If the darks were shot at a different exposure, the thermal signal is scaled accordingly (bias frames are needed too)."),
        "auto_crop": ("Crop the edges", "Removes the borders that, because of the shift between frames, are not covered by every shot."),
        "workers": ("Threads", "How many frames are calibrated in parallel.<br><b>Higher</b>: faster, about 700 MB more RAM per thread on 20 MP files."),
        "band_mb": ("Memory per band", "RAM used for each band of rows during stacking.<br><b>Higher</b>: fewer passes, faster."),
        "landscape": ("Landscape: sharp foreground", "In shots with trees, a horizon or buildings, stacking on the stars blurs the foreground. With this option the foreground is detected (dark area with no stars), aligned to itself and rebuilt sharp from the median of the frames."),
        "drizzle": ("Drizzle 2×", "Produces the stack at double resolution using the small shifts between frames (dithering). Without dithering you only get a bigger image. Files and times ×4."),
        "master_library": ("Master library", "Every master dark and bias is stored (camera, ISO, exposure). When a session has no darks or bias, a compatible one is reused (same camera and ISO, exposure within 25 %)."),
        "library_dir": ("Library folder", "Where the reusable masters are stored. Empty = default folder."),
        "cache_dir": ("Disk cache", "Folder where the calibrated frames are stored (about 120 MB per 20 MP frame), deleted when the job ends. Pick a fast drive (SSD) with free space."),
    },
    "ZONES": {
        "light": ("Light", "The shots of your subject: required. More lights = less noise (4× the frames = half the noise). They must all have the same size."),
        "dark": ("Dark", "Shots with the lens cap on, same exposure, same ISO and a similar temperature as the lights. They map and remove hot pixels and thermal noise. 10–20 recommended."),
        "flat": ("Flat", "Shots of an evenly lit field (twilight sky, light panel, white t-shirt over the lens) with the same focus, aperture and zoom as the lights, exposed to mid-histogram. They fix vignetting and dust. 15–30 recommended."),
        "bias": ("Bias / Offset", "Shots with the cap on at the shortest possible exposure (e.g. 1/4000 s), same ISO. They contain only read noise: used to calibrate the flats and scale the darks. 20–50 recommended.<br><b>Do not put your lights here!</b>"),
    },
    "BUTTONS": {
        "project_open": ("Open project", "Reopens an .astrostack project: files, settings, develop, layers and masks."),
        "project_save": ("Save project", "Saves everything (files used, settings, develop, layers, masks and the computed stack) in an .astrostack file, so you can pick the work up later."),
        "sort": ("Sort files", "Pick mixed files or folders: from the EXIF data and the thumbnail every file goes into the right zone (light, dark, flat, bias)."),
        "live": ("Live", "Watches a folder: whenever new shots arrive the stack restarts by itself with every file, so you see the result grow during the session."),
        "compare": ("Before / After", "Split comparison: left of the line the image without develop, right of it the developed one. Drag the slider to move the line."),
        "stack": ("Stack", "Runs everything: calibration masters → calibration → stars → alignment → stacking → gradient and colours. Shortcut: Ctrl+Enter."),
        "cancel": ("Cancel", "Stops the job in progress and clears the disk cache."),
        "save": ("Export", "Opens the export window: format, quality, resolution, output sharpening. Shortcut: Ctrl+S."),
        "stretch": ("Auto stretch / Linear", "Shows the preview with the auto stretch (faint signal visible) or linear (as the linear file: almost black)."),
        "fit": ("Fit", "Fits the whole image in the window. Mouse wheel to zoom, drag to pan."),
        "zoom100": ("100 %", "Shows real pixels: one pixel of the stack = one pixel on screen. Useful to check star shapes."),
        "session": ("Import session", "Pick a folder with Lights / Darks / Flats / Bias (or Offset) subfolders: the four zones fill themselves."),
        "frames": ("Frames", "Shows or hides the table with quality, alignment and status of every frame."),
        "log": ("Log", "Shows or hides the detailed processing log."),
    },
    "TOOLS": {
        "gx_path": ("GraXpert", "Free, open-source program (graxpert.com) with neural networks for denoising and gradient removal. Download it, open it once so it fetches the AI models, then point here to the .exe file."),
        "gx_strength": ("Denoise strength", "How much noise to remove.<br><b>Low</b> (20–40 %): natural, keeps the faintest stars.<br><b>High</b> (70–100 %): very smooth sky, risk of a plastic look."),
        "gx_gpu": ("Graphics card", "Uses the GPU for the AI: much faster. If GraXpert fails, turn it off and use the CPU."),
        "denoise": ("AI denoise", "Reduces the noise of the stack with GraXpert's neural network (1–5 minutes). Can be undone with 'Undo last change'."),
        "gradient_ai": ("AI gradient", "Removes light pollution with GraXpert's AI model: an alternative to AstroStack's polynomial, better with complex gradients."),
        "sn_path": ("StarNet++", "Free program (starnetastro.com) that removes stars with a neural network. Download the command-line version, unzip it and point to starnet++.exe (the weight files must stay in the same folder)."),
        "starnet": ("Remove the stars", "Produces the starless image (the picture is stretched first, as StarNet requires). The stars-only file is written next to your export: useful to process nebulae and stars separately."),
        "api_key": ("astrometry.net API key", "Free: sign up at nova.astrometry.net, then Profile → API key. Used only for object identification (a small preview is uploaded)."),
        "annotate": ("Identify objects", "Uploads a small preview to nova.astrometry.net, which identifies the field (coordinates, scale) and writes the names of constellations, nebulae, galaxies and clusters on the preview. Needs internet; takes 1–3 minutes."),
        "labels": ("Show labels", "Shows or hides the names of the identified objects on the preview (they are not saved in the file)."),
        "undo": ("Undo last change", "Goes back to the image before the last AI tool was applied (up to 5 steps)."),
    },
    "LAYERS": {
        "add": ("Add image", "Loads a photo (TIFF, PNG, JPG, FITS) as a new layer on top: for example the long exposure of the foreground, to blend with the stacked sky."),
        "dup": ("Duplicate", "Copies the selected layer (handy to apply two different develop settings to the same image)."),
        "del": ("Delete", "Removes the selected layer. The base layer cannot be deleted."),
        "move": ("Move", "Changes the order: layers higher in the list cover the ones below."),
        "opacity": ("Opacity", "How much the layer covers the ones below: 100 % = fully, 0 % = invisible."),
        "blend": ("Blend", "How the layer's pixels combine with the background.<br>• <b>Normal</b>: covers.<br>• <b>Lighten</b>: keeps the brighter one (great to merge sky and stars).<br>• <b>Darken</b>: keeps the darker one.<br>• <b>Multiply</b>: darkens.<br>• <b>Screen</b>: brightens.<br>• <b>Overlay / Soft light</b>: add contrast.<br>• <b>Add</b>: adds light.<br>• <b>Difference</b>: shows what differs (handy to align)."),
        "position": ("Position", "Shift of the layer in pixels relative to the base (at full resolution)."),
        "scale": ("Scale", "Enlarges or shrinks the layer (100 % = original size)."),
        "mask_type": ("Mask", "Where the layer is visible.<br>• <b>Linear gradient</b>: smooth transition (sky above, land below).<br>• <b>Luminosity</b>: visible only in the bright (or dark) areas of the layer itself.<br>• <b>Brush</b>: you paint the area on the preview.<br>• <b>Automatic foreground</b>: detects trees and horizon.<br>• <b>From file</b>: a greyscale image (white = visible)."),
        "invert": ("Invert", "Swaps the visible and hidden areas of the mask."),
        "show_mask": ("Show in red", "Paints in red, on the preview, the area where the layer is visible."),
        "feather": ("Edge feather", "Softens the edges of the mask (in pixels at full resolution)."),
        "gradient": ("Gradient", "Percentage from the top (or from the left) where the mask goes from hidden to visible."),
        "luminosity": ("Luminosity", "Below the dark threshold the layer is hidden, above the bright one it is visible, in between it fades."),
        "brush_size": ("Brush size", "Brush diameter in preview pixels."),
        "brush_hard": ("Hardness", "0 = very soft edge, 100 = crisp edge."),
        "paint": ("Paint", "Turns the brush on: drag with the left button on the preview to reveal the layer (or to erase, with the checkbox). Turn it off to pan the image again."),
        "load_mask": ("Load mask", "Greyscale image (white = visible, black = hidden), resized to the canvas."),
    },
    "DEVELOP": {
        "stretch_type": ("Stretch type", "How the linear data is made visible.<br>• <b>Classic (MTF)</b>: most detail in the background.<br>• <b>Arcsinh</b>: bright stars keep their colour instead of turning white.<br>• <b>Hybrid</b>: average of the two."),
        "star_reduce": ("Star reduction", "Shrinks the stars without deleting them: the Milky Way and nebulae stand out.<br><b>30–50</b>: natural.<br><b>80–100</b>: very strong, the faintest stars disappear."),
        "hsl": ("HSL", "Adjusts every colour range separately: <b>Hue</b> shifts it, <b>Saturation</b> makes it more or less vivid, <b>Luminance</b> brightens or darkens it. Example: lower the saturation of orange to tame light pollution, raise the blue of the sky."),
        "enabled": ("Develop on", "Turns every adjustment on or off: a quick before/after."),
        "auto": ("Auto", "Sets Blacks and Whites so the histogram uses the whole range without clipping."),
        "reset": ("Reset", "Puts every slider back to its default."),
        "preset_save": ("Save preset", "Saves the current settings in a file, to reuse them on other photos of the same session."),
        "preset_load": ("Load preset", "Applies settings saved earlier."),
        "stretch_bg": ("Sky background", "Where the sky background lands after the stretch.<br><b>Low</b> (10–20 %): dark, contrasty sky.<br><b>High</b> (30–40 %): brighter, more faint signal and more noise."),
        "stretch_shadows": ("Shadow clipping", "How much of the darkest part is cut.<br><b>Negative</b>: open shadows, nothing lost.<br><b>Positive</b>: deeper blacks, cleaner sky but the faintest signal goes."),
        "exposure": ("Exposure", "Overall brightness in stops (EV): +1 doubles the light."),
        "contrast": ("Contrast", "Increases or reduces the difference between light and dark areas, without touching the extremes."),
        "highlights": ("Highlights", "Recovers (negative) or brightens (positive) only the brightest areas: nebula cores, bright stars."),
        "shadows": ("Shadows", "Lifts (positive) or deepens (negative) the darkest areas: dust lanes, foreground."),
        "whites": ("Whites", "Moves the white point: sets how bright the brightest pixels are."),
        "blacks": ("Blacks", "Moves the black point. Slightly negative makes the sky cleaner; too much loses the faintest signal."),
        "temperature": ("Temperature", "Warmer (positive, more orange) or cooler (negative, more blue)."),
        "tint": ("Tint", "Green–magenta balance: useful to remove the residual green cast of the sensor."),
        "vibrance": ("Vibrance", "Boosts the least saturated colours and leaves the already vivid ones alone: the natural way to bring out star colours."),
        "saturation": ("Saturation", "Boosts every colour by the same amount: easy to overdo on astro images."),
        "clarity": ("Clarity", "Local contrast on the midtones: brings out the structure of nebulae without touching the stars."),
        "dehaze": ("Dehaze", "Removes the veil of haze or residual light pollution, deepening the large-scale background."),
        "sharpen": ("Sharpening", "Unsharp mask on the luminance.<br><b>30–60</b>: natural.<br>Above 100 it brings out the noise: use masking."),
        "sharpen_radius": ("Radius", "Size of the details being sharpened, in pixels. 0.8–1.2 px for stars; higher for large structures."),
        "sharpen_masking": ("Masking", "Applies the sharpening only on edges and stars, leaving the flat sky untouched.<br><b>High</b>: less noise brought out."),
        "nr_luminance": ("Luminance noise", "Removes the grain keeping the edges: too much makes the image look like plastic."),
        "nr_color": ("Colour noise", "Removes the coloured speckles (red and green dots) typical of high ISO."),
        "vignette": ("Vignette", "Darkens (negative) or brightens (positive) the corners: darkening helps the eye stay on the centre."),
        "grain": ("Grain", "Adds film-like grain: makes a heavily denoised image look more natural."),
        "rotation": ("Rotation", "Straightens the horizon or tilts the composition (degrees). The black corners are removed if the option below is on."),
        "auto_crop_rotation": ("Remove the black corners", "After rotating, crops the largest rectangle with no empty corners."),
        "curve": ("Tone curve", "Drag the points, click on the curve to add one, right-click to remove it. The classic S shape adds contrast."),
    },
}

_TIP_MAP: dict | None = None


def _tooltip_map() -> dict:
    """Mappa popup italiano -> inglese, costruita una sola volta."""
    global _TIP_MAP
    if _TIP_MAP is not None:
        return _TIP_MAP
    from . import tooltips as T
    m: dict[str, str] = {}
    for group in ("OPTIONS", "ZONES", "BUTTONS", "TOOLS", "LAYERS", "DEVELOP"):
        it_group = getattr(T, group, {})
        en_group = _TIP_EN.get(group, {})
        for key, it_text in it_group.items():
            if key in en_group:
                title, body = en_group[key]
                m[it_text] = T.tip(title, body)
    # colonne della tabella: testo semplice
    cols_en = {
        "nome": "File name", "stato": "ok = used · reference = the frame the others are aligned to · discarded / error = excluded (see Notes)",
        "stelle": "Stars detected in the frame: few stars = clouds, out of focus or bright sky",
        "fwhm": "Width of the stars at half maximum, in pixels: lower = sharper and steadier",
        "ecc": "Eccentricity: 0 = round stars, above 0.6 = elongated (shake, tracking, coma)",
        "punteggio": "Combined quality score (FWHM, stars, noise, eccentricity): 1 = the best",
        "peso": "Weight of the frame in the final average (0.2 to 1)",
        "spost": "Shift in pixels relative to the reference frame (x, y)",
        "rot": "Rotation relative to the reference", "rms": "Residual alignment error in pixels: below 0.5 great, above 1.5 suspicious",
        "metodo": "stars = star triangles (precise) · phase = phase correlation (shift only) · identity = reference",
        "posa": "Exposure time from the EXIF data", "iso": "ISO from the EXIF data",
        "hot": "Defective pixels fixed in this frame", "motivo": "Why the frame was discarded or failed",
    }
    col_labels = {"nome": "File", "stato": "Status", "stelle": "Stars", "fwhm": "FWHM px", "ecc": "Ecc.",
                  "punteggio": "Quality", "peso": "Weight", "spost": "Shift", "rot": "Rotation", "rms": "RMS px",
                  "metodo": "Alignment", "posa": "Exposure", "iso": "ISO", "hot": "Hot px", "motivo": "Notes"}
    from .frames_table import COLUMNS
    for key, label in COLUMNS:
        if key in getattr(T, "COLUMNS", {}) and key in cols_en:
            m[T.tip(label, T.COLUMNS[key])] = T.tip(col_labels.get(key, label), cols_en[key])
    m[T.tip("Lingua", "Cambia la lingua dell'interfaccia in tempo reale: italiano o inglese.")] = \
        T.tip("Language", "Switches the interface language in real time: Italian or English.")
    _TIP_MAP = m
    return m


# ----------------------------------------------------------------------------
# traduzione dell'albero dei widget
# ----------------------------------------------------------------------------
_SRC = "_i18n_src"


def _src(w: QWidget, key: str, current: str) -> str:
    """Testo originale italiano: memorizzato la prima volta che si incontra il widget."""
    prop = f"{_SRC}_{key}"
    saved = w.property(prop)
    if saved is None:
        w.setProperty(prop, current)
        return current
    return str(saved)


def skip(*widgets):
    """Marca i widget con testo dinamico: non verranno riscritti dal traduttore."""
    for w in widgets:
        w.setProperty("_i18n_skip", True)


def retranslate(root: QWidget):
    """Riscrive tutti i testi visibili di `root` e dei suoi figli nella lingua corrente."""
    if root.windowTitle():
        root.setWindowTitle(tr(_src(root, "win", root.windowTitle())))
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        try:
            _retranslate_widget(w)
        except Exception:
            continue


def _retranslate_widget(w: QWidget):
    if w.toolTip():
        w.setToolTip(tr(_src(w, "tip", w.toolTip())))
    if w.property("_i18n_skip"):
        return             # testo dinamico: lo aggiorna il pannello che lo possiede
    fn = getattr(w, "retranslate_i18n", None)
    if callable(fn):
        fn()               # il widget conosce il proprio testo originale
        return
    if isinstance(w, QLabel):
        w.setText(tr(_src(w, "text", w.text())))
    elif isinstance(w, QAbstractButton):
        w.setText(tr(_src(w, "text", w.text())))
    if isinstance(w, QGroupBox):
        w.setTitle(tr(_src(w, "title", w.title())))
    elif isinstance(w, QComboBox):
        for i in range(w.count()):
            key = f"item{i}"
            w.setItemText(i, tr(_src(w, key, w.itemText(i))))
    elif isinstance(w, QLineEdit):
        if w.placeholderText():
            w.setPlaceholderText(tr(_src(w, "ph", w.placeholderText())))
    elif isinstance(w, QAbstractSpinBox):
        suffix = getattr(w, "suffix", None)
        if callable(suffix) and suffix():
            w.setSuffix(tr(_src(w, "suffix", suffix())))
    elif isinstance(w, QTabWidget):
        for i in range(w.count()):
            w.setTabText(i, tr(_src(w, f"tab{i}", w.tabText(i))))
    elif isinstance(w, QDockWidget):
        w.setWindowTitle(tr(_src(w, "win", w.windowTitle())))
    elif isinstance(w, QListWidget):
        for i in range(w.count()):
            it = w.item(i)
            if it is not None:
                it.setText(tr(it.text()))
    elif isinstance(w, QTableWidget):
        for c in range(w.columnCount()):
            it = w.horizontalHeaderItem(c)
            if it is None:
                continue
            it.setText(tr(_src(w, f"h{c}", it.text())))
            if it.toolTip():
                it.setToolTip(tr(_src(w, f"ht{c}", it.toolTip())))
        # la colonna "Stato" contiene parole tradotte
        for r in range(w.rowCount()):
            for c in range(w.columnCount()):
                it = w.item(r, c)
                if it is not None and it.text() in ("ok", "scartato", "errore", "riferimento", "in coda",
                                                    "discarded", "error", "reference", "queued",
                                                    "stelle", "fase", "identità", "stars", "phase", "identity"):
                    it.setText(tr(_back(it.text())))


# Desktop 1.4 workspace.
DICT.update({
    "Dalle tue immagini, nuovi universi": "New universes from your images",
    "Progetti": "Projects", "Altre azioni ▾": "More actions ▾", "Pannelli": "Panels",
    "Modalità": "Mode", "Semplice": "Simple", "Avanzata": "Advanced",
    "Regolazioni di base": "Basic adjustments", "Strumenti astro": "Astro tools",
    "Colore / HSL": "Colour / HSL", "Curva dei toni": "Tone curve",
    "Geometria / effetti": "Geometry / effects", "Livelli e maschere": "Layers and masks",
    "Cronologia": "History", "+ Snapshot": "+ Snapshot", "Prima": "Before", "Dopo": "After",
    "01   Importa": "01   Import", "02   Controlla": "02   Inspect", "04   Risultato": "04   Result",
    "Il tuo prossimo cielo inizia qui": "Your next sky starts here",
    "Apri un'immagine per iniziare lo sviluppo.\nRAW · FITS · TIFF · PNG · JPEG": "Open an image to start editing.\nRAW · FITS · TIFF · PNG · JPEG",
    "Scegli il flusso di lavoro da cui partire.": "Choose where to start.",
    "Sviluppo standalone per RAW, FITS e immagini finite.": "Standalone editing for RAW, FITS and finished images.",
    "Calibra, analizza, allinea e combina i tuoi frame.": "Calibrate, analyse, align and combine your frames.",
    "Apri, salva e riprendi le tue sessioni AstroStack.": "Open, save and resume your AstroStack sessions.",
    "Stack, sviluppa e rifinisci il cielo\nin un unico spazio di lavoro.": "Stack, develop and refine the sky\nin one workspace.",
    "Dai frame al master": "From frames to master", "Sviluppo standalone": "Standalone editing",
    "Riprendi il lavoro": "Resume your work", "Apri Editor": "Open Editor", "Apri progetto": "Open project",
    "ULTIMO PROGETTO": "LAST PROJECT", "PROGETTI": "PROJECTS", "RECENTE": "RECENT",
    "Il tuo lavoro, sempre riprendibile.": "Your work, ready to resume.",
    "Offline-first • elaborazione locale": "Offline-first • local processing",
})

_BACK = {v: k for k, v in DICT.items()}


def _back(text: str) -> str:
    """Riporta all'italiano un testo già tradotto (per ritradurre le celle)."""
    return _BACK.get(text, text)
