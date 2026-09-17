"""Caricamento immagini: RAW (tutti i formati LibRaw), FITS, TIFF, PNG, JPG.

Tutte le immagini vengono restituite come float32 lineari, normalizzate in modo
che il livello di bianco (saturazione) corrisponda a 1.0.

Le immagini RAW vengono lette come mosaico Bayer (senza demosaicizzazione): la
calibrazione (dark / flat / bias) viene fatta nel dominio Bayer, come fanno
DeepSkyStacker e Siril, e solo dopo si passa a RGB.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

RAW_EXT = {
    ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng",
    ".raf", ".orf", ".pef", ".rw2", ".raw", ".rwl", ".3fr", ".fff", ".iiq",
    ".mos", ".mrw", ".kdc", ".dcr", ".erf", ".mef", ".srw", ".x3f", ".ari",
}
FITS_EXT = {".fits", ".fit", ".fts"}
IMG_EXT = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
ALL_EXT = RAW_EXT | FITS_EXT | IMG_EXT

# Fattore di scala usato per i mosaici Bayer convertiti in uint16 (debayer OpenCV)
BAYER_U16_SCALE = 32767.0


@dataclass
class Frame:
    """Un'immagine caricata in memoria."""
    path: str
    data: np.ndarray                 # float32: Bayer (H, W) oppure RGB (H, W, 3) o mono (H, W)
    is_bayer: bool
    pattern: Optional[str] = None    # "RGGB", "BGGR", "GRBG", "GBRG" (solo se is_bayer)
    exposure: Optional[float] = None # secondi
    iso: Optional[int] = None
    camera: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def shape2d(self) -> tuple[int, int]:
        return self.data.shape[0], self.data.shape[1]


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ALL_EXT


def collect_files(paths) -> list[str]:
    """Espande file e cartelle (ricorsivamente) in una lista ordinata di file supportati."""
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    fp = os.path.join(root, f)
                    if is_supported(fp):
                        out.append(fp)
        elif os.path.isfile(p) and is_supported(p):
            out.append(p)
    # ordine stabile e senza duplicati
    seen = set()
    result = []
    for p in sorted(out, key=lambda s: s.lower()):
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


# ----------------------------------------------------------------------------
# EXIF (opzionale)
# ----------------------------------------------------------------------------
def quick_meta(path: str) -> dict:
    """Posa, ISO e fotocamera da EXIF (RAW/JPG/TIFF) o dall'intestazione FITS, senza decodificare l'immagine."""
    ext = os.path.splitext(path)[1].lower()
    if ext in FITS_EXT:
        info: dict = {}
        try:
            from astropy.io import fits  # type: ignore
            with fits.open(path, memmap=False, lazy_load_hdus=True) as h:
                hdr = h[0].header
            exp = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
            if exp is not None:
                info["exposure"] = float(exp)
            cam = hdr.get("INSTRUME") or hdr.get("CAMERA")
            if cam:
                info["camera"] = str(cam).strip()
            iso = hdr.get("ISOSPEED", hdr.get("ISO", hdr.get("GAIN")))
            if iso is not None:
                try:
                    info["iso"] = int(float(iso))
                except Exception:
                    pass
        except Exception:
            pass
        return info
    return read_exif(path)


def read_exif(path: str) -> dict:
    """Legge tempo di posa, ISO e modello camera. Restituisce {} se non disponibile."""
    info: dict = {}
    if os.path.splitext(path)[1].lower() in FITS_EXT:
        return info
    try:
        import exifread  # type: ignore
        import logging
        logging.getLogger("exifread").setLevel(logging.ERROR)
    except ImportError:
        return info
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
    except Exception:
        return info
    try:
        t = tags.get("EXIF ExposureTime")
        if t is not None:
            v = t.values[0]
            info["exposure"] = float(v.num) / float(v.den) if hasattr(v, "num") else float(v)
    except Exception:
        pass
    try:
        t = tags.get("EXIF ISOSpeedRatings")
        if t is not None:
            info["iso"] = int(t.values[0])
    except Exception:
        pass
    try:
        t = tags.get("Image Model")
        if t is not None:
            info["camera"] = str(t.values).strip()
    except Exception:
        pass
    return info


# ----------------------------------------------------------------------------
# RAW
# ----------------------------------------------------------------------------
def _pattern_from_rawpy(raw) -> Optional[str]:
    pat = raw.raw_pattern
    if pat is None or pat.shape != (2, 2):
        return None
    desc = raw.color_desc.decode("ascii") if isinstance(raw.color_desc, bytes) else str(raw.color_desc)
    letters = []
    for idx in pat.flatten():
        c = desc[int(idx)] if int(idx) < len(desc) else "G"
        letters.append("G" if c == "G" else c)
    s = "".join(letters)
    return s if s in ("RGGB", "BGGR", "GRBG", "GBRG") else None


def load_raw(path: str, want_bayer: bool = True) -> Frame:
    import rawpy  # type: ignore

    exif = read_exif(path)
    # lettura tramite buffer: evita problemi con percorsi non ASCII su Windows
    with open(path, "rb") as f:
        buf = f.read()
    import io as _io
    with rawpy.imread(_io.BytesIO(buf)) as raw:
        pattern = _pattern_from_rawpy(raw)
        white = float(raw.white_level)
        blacks = [float(b) for b in raw.black_level_per_channel]
        wb_meta = {}
        for key, attr in (("wb_daylight", "daylight_whitebalance"), ("wb_camera", "camera_whitebalance")):
            try:
                w = [float(v) for v in getattr(raw, attr)]
                if len(w) >= 3 and w[1] > 0 and w[0] > 0 and w[2] > 0:
                    wb_meta[key] = (w[0] / w[1], 1.0, w[2] / w[1])
            except Exception:
                pass
        raw_img = raw.raw_image_visible
        if want_bayer and pattern is not None and raw_img.ndim == 2:
            data = raw_img.astype(np.float32)
            # sottrazione del livello di nero per ogni posizione del mosaico
            pat = raw.raw_pattern
            for dy in range(2):
                for dx in range(2):
                    b = blacks[int(pat[dy, dx])]
                    data[dy::2, dx::2] -= b
            span = max(white - float(np.mean(blacks)), 1.0)
            data /= span
            np.clip(data, -0.1, 4.0, out=data)
            return Frame(path=path, data=data, is_bayer=True, pattern=pattern,
                         exposure=exif.get("exposure"), iso=exif.get("iso"),
                         camera=exif.get("camera", ""),
                         meta={"white_level": white, "black_levels": blacks, **wb_meta})
        # sensori non-Bayer (X-Trans, Foveon, mono...): usa la demosaicizzazione LibRaw
        rgb = raw.postprocess(gamma=(1, 1), no_auto_bright=True, output_bps=16,
                              use_camera_wb=True, user_flip=0)
    data = rgb.astype(np.float32) / 65535.0
    return Frame(path=path, data=data, is_bayer=False, pattern=None,
                 exposure=exif.get("exposure"), iso=exif.get("iso"),
                 camera=exif.get("camera", ""), meta={"white_level": 65535.0})


# ----------------------------------------------------------------------------
# FITS
# ----------------------------------------------------------------------------
def load_fits(path: str) -> Frame:
    from astropy.io import fits  # type: ignore

    with fits.open(path, memmap=False) as hdul:
        hdu = None
        for h in hdul:
            if h.data is not None and np.ndim(h.data) >= 2:
                hdu = h
                break
        if hdu is None:
            raise ValueError("Il file FITS non contiene immagini")
        data = np.asarray(hdu.data)
        hdr = hdu.header
    orig_dtype = data.dtype
    data = data.astype(np.float32)
    if data.ndim == 3:
        if data.shape[0] in (1, 3):
            data = np.transpose(data, (1, 2, 0))
        if data.shape[2] == 1:
            data = data[:, :, 0]
    # normalizzazione
    if np.issubdtype(orig_dtype, np.integer):
        bits = orig_dtype.itemsize * 8
        maxv = float(2 ** bits - 1)
        if orig_dtype == np.int16:  # BZERO gestito da astropy → 0..65535
            maxv = 65535.0
        data /= maxv
    else:
        m = float(np.nanmax(data)) if data.size else 1.0
        if m > 1.5:
            data /= m
    pattern = None
    is_bayer = False
    bp = str(hdr.get("BAYERPAT", "")).strip().upper()
    if data.ndim == 2 and bp in ("RGGB", "BGGR", "GRBG", "GBRG"):
        is_bayer = True
        pattern = bp
    n_frames = hdr.get("NFRAMES")
    exposure = hdr.get("EXPTIME", hdr.get("EXPOSURE"))
    try:
        exposure = float(exposure) if exposure is not None else None
    except Exception:
        exposure = None
    return Frame(path=path, data=np.ascontiguousarray(data), is_bayer=is_bayer, pattern=pattern,
                 exposure=exposure, iso=None, camera=str(hdr.get("INSTRUME", "")),
                 meta={"white_level": 1.0, **({"n_frames": float(n_frames)} if n_frames else {})})


# ----------------------------------------------------------------------------
# TIFF / PNG / JPG
# ----------------------------------------------------------------------------
def _normalize_int(data: np.ndarray) -> np.ndarray:
    if data.dtype == np.uint8:
        return data.astype(np.float32) / 255.0
    if data.dtype == np.uint16:
        return data.astype(np.float32) / 65535.0
    if np.issubdtype(data.dtype, np.integer):
        return data.astype(np.float32) / float(np.iinfo(data.dtype).max)
    d = data.astype(np.float32)
    m = float(np.nanmax(d)) if d.size else 1.0
    return d / m if m > 1.5 else d


def load_image(path: str) -> Frame:
    ext = os.path.splitext(path)[1].lower()
    exif = read_exif(path)
    if ext in (".tif", ".tiff"):
        import tifffile  # type: ignore
        data = tifffile.imread(path)
        if data.ndim == 3 and data.shape[2] == 4:
            data = data[:, :, :3]
        if data.ndim == 3 and data.shape[0] in (3, 4) and data.shape[2] not in (3, 4):
            data = np.transpose(data[:3], (1, 2, 0))
    else:
        import cv2  # type: ignore
        buf = np.fromfile(path, dtype=np.uint8)  # percorsi unicode su Windows
        data = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if data is None:
            raise ValueError("Impossibile decodificare l'immagine")
        if data.ndim == 3:
            if data.shape[2] == 4:
                data = data[:, :, :3]
            data = data[:, :, ::-1]  # BGR -> RGB
    data = _normalize_int(np.ascontiguousarray(data))
    return Frame(path=path, data=np.ascontiguousarray(data), is_bayer=False, pattern=None,
                 exposure=exif.get("exposure"), iso=exif.get("iso"),
                 camera=exif.get("camera", ""), meta={"white_level": 1.0})


def load_frame(path: str, want_bayer: bool = True) -> Frame:
    """Carica un file in base all'estensione."""
    ext = os.path.splitext(path)[1].lower()
    if ext in RAW_EXT:
        return load_raw(path, want_bayer=want_bayer)
    if ext in FITS_EXT:
        return load_fits(path)
    if ext in IMG_EXT:
        return load_image(path)
    raise ValueError(f"Formato non supportato: {ext}")


def luminance(img: np.ndarray) -> np.ndarray:
    """Luminanza float32 di un'immagine RGB o mono (i mosaici Bayer vengono trattati come mono)."""
    if img.ndim == 2:
        return img.astype(np.float32, copy=False)
    return (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]).astype(np.float32)
