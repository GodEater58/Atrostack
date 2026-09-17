"""Salvataggio del risultato."""
from __future__ import annotations

import os

import numpy as np

from .stretch import auto_stretch, to_uint8


def _u16(img: np.ndarray) -> np.ndarray:
    return np.clip(img * 65535.0 + 0.5, 0, 65535).astype(np.uint16)


def save_tiff16(path: str, img: np.ndarray, metadata: dict | None = None, stretch: bool = False):
    """TIFF 16 bit. stretch=True salva l'immagine come appare nell'anteprima (non lineare)."""
    import tifffile
    data = auto_stretch(img) if stretch else img
    meta = dict(metadata or {})
    meta["STRETCH"] = "auto-stretch come anteprima" if stretch else "lineare"
    tifffile.imwrite(path, _u16(data), photometric="rgb" if img.ndim == 3 else "minisblack",
                     compression="zlib", metadata=meta)


def save_fits(path: str, img: np.ndarray, metadata: dict | None = None):
    from astropy.io import fits
    data = img.astype(np.float32)
    if data.ndim == 3:
        data = np.transpose(data, (2, 0, 1))  # (C, H, W) come Siril / PixInsight
    hdu = fits.PrimaryHDU(data)
    hdu.header["SOFTWARE"] = "AstroStack"
    for k, v in (metadata or {}).items():
        key = str(k)[:8].upper()
        try:
            hdu.header[key] = v if not isinstance(v, (list, tuple, dict)) else str(v)
        except Exception:
            pass
    hdu.writeto(path, overwrite=True)


def save_png16(path: str, img: np.ndarray, stretch: bool = True):
    import cv2
    u16 = _u16(auto_stretch(img) if stretch else img)
    if u16.ndim == 3:
        u16 = u16[:, :, ::-1]  # RGB -> BGR
    ok, buf = cv2.imencode(".png", u16)
    if not ok:
        raise IOError("Errore nella codifica PNG")
    buf.tofile(path)


def save_jpg_preview(path: str, img: np.ndarray, quality: int = 92):
    import cv2
    u8 = to_uint8(img, stretch=True)
    if u8.ndim == 3:
        u8 = u8[:, :, ::-1]
    ok, buf = cv2.imencode(".jpg", u8, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise IOError("Errore nella codifica JPG")
    buf.tofile(path)


def save_result(path: str, img: np.ndarray, metadata: dict | None = None, stretch: bool = False):
    """stretch=True: come l'anteprima (per Lightroom/Photoshop). False: lineare (per Siril/PixInsight).
    FITS è sempre lineare; JPG è sempre come l'anteprima."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff"):
        save_tiff16(path, img, metadata, stretch=stretch)
    elif ext in (".fits", ".fit", ".fts"):
        save_fits(path, img, metadata)
    elif ext == ".png":
        save_png16(path, img, stretch=stretch)
    elif ext in (".jpg", ".jpeg"):
        save_jpg_preview(path, img)
    else:
        raise ValueError(f"Formato di salvataggio non supportato: {ext}")
