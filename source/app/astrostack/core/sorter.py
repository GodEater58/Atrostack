"""Smistamento automatico dei file in light / dark / flat / bias (EXIF + anteprima incorporata)."""
from __future__ import annotations

import os
from typing import Callable, Optional

import numpy as np

from .loader import FITS_EXT, RAW_EXT, quick_meta


def _thumb_stats(path: str) -> Optional[tuple[float, float]]:
    """(media, deviazione standard) della luminosità dell'anteprima JPEG incorporata nel RAW (0..1)."""
    ext = os.path.splitext(path)[1].lower()
    try:
        import cv2
        if ext in RAW_EXT:
            import io
            import rawpy
            with open(path, "rb") as f:
                buf = f.read()
            with rawpy.imread(io.BytesIO(buf)) as raw:
                th = raw.extract_thumb()
            if th.format == rawpy.ThumbFormat.JPEG:
                img = cv2.imdecode(np.frombuffer(th.data, np.uint8), cv2.IMREAD_GRAYSCALE)
            else:
                img = np.asarray(th.data).mean(axis=2) if np.ndim(th.data) == 3 else np.asarray(th.data)
            if img is None:
                return None
            g = img.astype(np.float32) / 255.0
        elif ext in FITS_EXT:
            from astropy.io import fits
            with fits.open(path, memmap=False) as h:      # memmap non ammesso con BZERO/BSCALE
                d = np.asarray(h[0].data)
                d = d[::8, ::8] if d.ndim == 2 else d[0][::8, ::8]
            g = d.astype(np.float32)
            if np.issubdtype(d.dtype, np.integer):
                g /= float(np.iinfo(d.dtype).max)
            elif float(g.max()) > 1.5:                      # BZERO/BSCALE: astropy restituisce float 0..65535
                g /= 65535.0 if float(g.max()) <= 65535.0 else float(g.max())
        else:
            img = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return None
            g = img[::4, ::4].astype(np.float32) / (65535.0 if img.dtype == np.uint16 else 255.0)
        return float(np.median(g)), float(g.std())
    except Exception:
        return None


def classify_file(path: str) -> tuple[str, str]:
    """Restituisce (categoria, motivo). Categorie: light, dark, flat, bias."""
    exif = quick_meta(path)
    exp = exif.get("exposure")
    st = _thumb_stats(path)
    mean, std = st if st else (None, None)
    if exp is not None and exp <= 1 / 400:
        return "bias", f"posa {exp:g} s"
    if mean is not None:
        if mean > 0.30 and std is not None and std < 0.12:
            return "flat", f"campo chiaro e uniforme (livello {mean:.2f})"
        if mean < 0.06 and (exp is None or exp >= 0.5):
            return "dark", f"tutto nero (livello {mean:.3f})"
    return "light", "immagine del cielo"


def classify_files(paths: list[str], progress: Optional[Callable[[int, int, str], None]] = None) -> dict:
    out = {"light": [], "dark": [], "flat": [], "bias": [], "reasons": {}}
    for i, p in enumerate(paths):
        kind, why = classify_file(p)
        out[kind].append(p)
        out["reasons"][p] = (kind, why)
        if progress:
            progress(i + 1, len(paths), os.path.basename(p))
    return out
