"""Strumenti IA esterni gratuiti richiamati da AstroStack.

- GraXpert  (https://www.graxpert.com)      : denoise e rimozione gradiente con rete neurale
- StarNet++ (https://www.starnetastro.com)  : rimozione delle stelle con rete neurale
- astrometry.net (https://nova.astrometry.net): riconoscimento degli oggetti nel campo (servizio web)

I programmi vanno scaricati dai rispettivi siti (gratuiti per uso personale);
AstroStack li richiama in automatico sull'immagine corrente.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Optional

import numpy as np

from .io_out import save_fits, save_jpg_preview, save_tiff16
from .loader import load_frame
from .stretch import auto_stretch

LogCb = Optional[Callable[[str], None]]


class ToolError(Exception):
    pass


# ----------------------------------------------------------------------------
# ricerca degli eseguibili
# ----------------------------------------------------------------------------
def _candidate_dirs() -> list[str]:
    home = os.path.expanduser("~")
    dirs = [home, os.path.join(home, "Desktop"), os.path.join(home, "Downloads"), os.path.join(home, "Scaricati"),
            os.path.join(home, "Documents"), os.path.join(home, "Documenti")]
    if sys.platform.startswith("win"):
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                dirs += [base, os.path.join(base, "GraXpert"), os.path.join(base, "Programs", "GraXpert"),
                         os.path.join(base, "StarNet"), os.path.join(base, "StarNetv2CLI_Win")]
    elif sys.platform == "darwin":
        dirs += ["/Applications"]
    return dirs


def find_graxpert(user_path: str = "") -> Optional[str]:
    if user_path and os.path.isfile(user_path):
        return user_path
    for name in ("GraXpert-win64.exe", "GraXpert.exe", "graxpert", "GraXpert-linux", "GraXpert"):
        p = shutil.which(name)
        if p:
            return p
    for d in _candidate_dirs():
        for pat in ("GraXpert*.exe", "GraXpert-linux", "GraXpert.app/Contents/MacOS/GraXpert", "GraXpert*/GraXpert*.exe"):
            hits = sorted(glob.glob(os.path.join(d, pat)))
            if hits:
                return hits[-1]
    return None


def find_starnet(user_path: str = "") -> Optional[str]:
    if user_path and os.path.isfile(user_path):
        return user_path
    for name in ("starnet++.exe", "starnet++", "rgb_starnet++.exe", "StarNetv2CLI"):
        p = shutil.which(name)
        if p:
            return p
    for d in _candidate_dirs():
        for pat in ("starnet++.exe", "*/starnet++.exe", "rgb_starnet++.exe", "*/rgb_starnet++.exe", "*StarNet*/starnet++*"):
            hits = sorted(glob.glob(os.path.join(d, pat)))
            if hits:
                return hits[-1]
    return None


def _run(cmd: list[str], cwd: Optional[str], log: LogCb, timeout: int = 7200) -> str:
    if log:
        log("Eseguo: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    creation = 0
    if sys.platform.startswith("win"):
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              creationflags=creation, errors="replace")
    except FileNotFoundError:
        raise ToolError(f"Programma non trovato: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise ToolError("Il programma esterno non ha risposto entro il tempo massimo")
    out = (proc.stdout or "") + (proc.stderr or "")
    if log and out.strip():
        for line in out.strip().splitlines()[-12:]:
            log("  " + line)
    if proc.returncode != 0:
        raise ToolError(f"Il programma esterno è uscito con errore (codice {proc.returncode}). "
                        "Controlla il registro.")
    return out


def _find_output(base: str) -> Optional[str]:
    for ext in (".fits", ".fit", ".tif", ".tiff", ".png", ".xisf"):
        if os.path.isfile(base + ext):
            return base + ext
    hits = sorted(glob.glob(base + "*"))
    hits = [h for h in hits if os.path.isfile(h) and not h.endswith(".part")]
    return hits[0] if hits else None


# ----------------------------------------------------------------------------
# GraXpert
# ----------------------------------------------------------------------------
def run_graxpert(exe: str, image: np.ndarray, mode: str = "denoise", strength: float = 0.5,
                 smoothing: float = 0.5, gpu: bool = True, log: LogCb = None) -> np.ndarray:
    """mode: "denoise" oppure "background". L'immagine è lineare float32 (H, W, 3)."""
    if not exe or not os.path.isfile(exe):
        raise ToolError("GraXpert non trovato: scaricalo da graxpert.com e indica il percorso in Strumenti IA")
    work = tempfile.mkdtemp(prefix="astrostack_gx_")
    try:
        src = os.path.join(work, "input.fits")
        save_fits(src, image, {"SOFTWARE": "AstroStack"})
        out_base = os.path.join(work, "output")
        cmd = [exe, src, "-cli", "-cmd", "denoising" if mode == "denoise" else "background-extraction",
               "-output", out_base, "-gpu", "true" if gpu else "false"]
        if mode == "denoise":
            cmd += ["-strength", f"{float(strength):.2f}"]
        else:
            cmd += ["-correction", "Subtraction", "-smoothing", f"{float(smoothing):.2f}"]
        _run(cmd, work, log)
        out = _find_output(out_base)
        if out is None:
            raise ToolError("GraXpert non ha prodotto alcun file. Apri GraXpert una volta dalla sua "
                            "interfaccia per scaricare i modelli IA, poi riprova.")
        fr = load_frame(out)
        data = fr.data
        if data.ndim == 2:
            data = np.repeat(data[:, :, None], 3, axis=2)
        if data.shape[:2] != image.shape[:2]:
            raise ToolError(f"Dimensioni inattese nel risultato di GraXpert: {data.shape}")
        return np.ascontiguousarray(data[:, :, :3], dtype=np.float32)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------
# StarNet++
# ----------------------------------------------------------------------------
def run_starnet(exe: str, image: np.ndarray, already_stretched: bool = False,
                log: LogCb = None) -> tuple[np.ndarray, np.ndarray]:
    """Restituisce (immagine senza stelle, sole stelle), entrambe NON lineari (stirate).

    StarNet++ lavora su TIFF 16 bit già stirati: l'immagine viene stirata con
    l'auto-stretch se è ancora lineare.
    """
    if not exe or not os.path.isfile(exe):
        raise ToolError("StarNet++ non trovato: scaricalo da starnetastro.com e indica il percorso in Strumenti IA")
    work = tempfile.mkdtemp(prefix="astrostack_sn_")
    try:
        stretched = image if already_stretched else auto_stretch(image)
        src = os.path.join(work, "input.tif")
        dst = os.path.join(work, "starless.tif")
        save_tiff16(src, stretched, {}, stretch=False)
        _run([exe, src, dst], os.path.dirname(exe) or None, log)
        if not os.path.isfile(dst):
            raise ToolError("StarNet++ non ha prodotto il file senza stelle (controlla che i file dei pesi siano nella sua cartella)")
        starless = load_frame(dst).data
        if starless.ndim == 2:
            starless = np.repeat(starless[:, :, None], 3, axis=2)
        starless = np.ascontiguousarray(starless[:, :, :3], dtype=np.float32)
        if starless.shape[:2] != stretched.shape[:2]:
            raise ToolError(f"Dimensioni inattese nel risultato di StarNet++: {starless.shape}")
        stars = np.clip(stretched - starless, 0.0, 1.0).astype(np.float32)
        return starless, stars
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------------
# astrometry.net (nova) — riconoscimento del campo e degli oggetti
# ----------------------------------------------------------------------------
API = "https://nova.astrometry.net/api/"


def astrometry_annotate(api_key: str, image: np.ndarray, log: LogCb = None, timeout: int = 420,
                        max_dim: int = 1600) -> dict:
    """Carica un'anteprima ridotta su nova.astrometry.net e restituisce oggetti e coordinate.

    Risultato: {"objects": [nomi], "annotations": [{"names": [...], "x": px, "y": px, "radius": px}],
                "calibration": {...}} con coordinate riferite all'immagine piena.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        raise ToolError("Manca la libreria 'requests' (pip install requests)")
    if not api_key or len(api_key.strip()) < 8:
        raise ToolError("Inserisci la chiave API di nova.astrometry.net (gratuita: Profilo → API key)")
    api_key = api_key.strip()
    import cv2
    H, W = image.shape[:2]
    f = 1
    while max(H, W) / f > max_dim:
        f *= 2
    small = image if f == 1 else cv2.resize(image, (W // f, H // f), interpolation=cv2.INTER_AREA)
    work = tempfile.mkdtemp(prefix="astrostack_an_")
    try:
        jpg = os.path.join(work, "field.jpg")
        save_jpg_preview(jpg, small, quality=90)
        if log:
            log("astrometry.net: accesso…")
        r = requests.post(API + "login", data={"request-json": json.dumps({"apikey": api_key})}, timeout=60)
        js = r.json()
        if js.get("status") != "success":
            raise ToolError("astrometry.net: chiave API rifiutata")
        session = js["session"]
        if log:
            log("astrometry.net: invio dell'anteprima…")
        args = {"session": session, "publicly_visible": "n", "allow_commercial_use": "n",
                "allow_modifications": "n", "scale_units": "degwidth", "scale_type": "ul",
                "scale_lower": 0.1, "scale_upper": 180}
        with open(jpg, "rb") as fh:
            files = [("request-json", (None, json.dumps(args), "text/plain")),
                     ("file", ("field.jpg", fh, "application/octet-stream"))]
            r = requests.post(API + "upload", files=files, timeout=120)
        js = r.json()
        if js.get("status") != "success":
            raise ToolError("astrometry.net: caricamento rifiutato: " + str(js))
        subid = js["subid"]
        t0 = time.time()
        job_id = None
        while time.time() - t0 < timeout:
            time.sleep(5)
            r = requests.get(API + f"submissions/{subid}", timeout=60)
            js = r.json()
            jobs = [j for j in js.get("jobs", []) if j]
            if jobs:
                job_id = jobs[0]
                r = requests.get(API + f"jobs/{job_id}", timeout=60)
                st = r.json().get("status")
                if log:
                    log(f"astrometry.net: {st}…")
                if st == "success":
                    break
                if st == "failure":
                    raise ToolError("astrometry.net non è riuscito a riconoscere il campo (troppo poche stelle "
                                    "o campo troppo stretto/largo)")
            elif log:
                log("astrometry.net: in coda…")
        else:
            raise ToolError("astrometry.net: tempo scaduto, riprova più tardi")
        info = requests.get(API + f"jobs/{job_id}/info", timeout=60).json()
        ann = requests.get(API + f"jobs/{job_id}/annotations", timeout=60).json()
        out = {"objects": list(info.get("objects_in_field", [])), "calibration": info.get("calibration", {}),
               "annotations": []}
        for a in ann.get("annotations", []):
            try:
                out["annotations"].append({"names": list(a.get("names", [])), "type": a.get("type", ""),
                                           "x": float(a["pixelx"]) * f, "y": float(a["pixely"]) * f,
                                           "radius": float(a.get("radius", 0)) * f})
            except Exception:
                continue
        return out
    except (requests.RequestException, ValueError) as e:  # type: ignore[name-defined]
        raise ToolError(f"astrometry.net non raggiungibile o risposta non valida: {e}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
