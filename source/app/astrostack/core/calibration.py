"""Calibrazione: master bias / dark / flat, hot pixel, correzione cosmetica, debayer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import cv2
import numpy as np

from .loader import Frame, BAYER_U16_SCALE, load_frame

ProgressCb = Callable[[int, int, str], None]

# OpenCV nomina i pattern Bayer a partire dalla seconda riga/colonna: la mappa
# corretta (verificata) dal pattern in alto a sinistra al codice OpenCV è questa.
_CV_BAYER = {
    "RGGB": cv2.COLOR_BayerBG2RGB_EA,
    "BGGR": cv2.COLOR_BayerRG2RGB_EA,
    "GRBG": cv2.COLOR_BayerGB2RGB_EA,
    "GBRG": cv2.COLOR_BayerGR2RGB_EA,
}


@dataclass
class Masters:
    bias: Optional[np.ndarray] = None       # float32, stesse dimensioni dei light
    dark: Optional[np.ndarray] = None       # float32 (contiene già il bias)
    flat: Optional[np.ndarray] = None       # float32 normalizzato (media = 1)
    hot_mask: Optional[np.ndarray] = None   # bool: pixel caldi/difettosi
    dark_exposure: Optional[float] = None
    is_bayer: bool = False
    pattern: Optional[str] = None
    info: dict = field(default_factory=dict)


# ----------------------------------------------------------------------------
# statistiche robuste
# ----------------------------------------------------------------------------
def mad_sigma(x: np.ndarray, center: Optional[float] = None) -> float:
    """Deviazione standard robusta (1.4826 * MAD)."""
    x = x.ravel()
    if x.size > 2_000_000:
        x = x[:: max(1, x.size // 2_000_000)]
    if center is None:
        center = float(np.median(x))
    return float(1.4826 * np.median(np.abs(x - center))) + 1e-12


def cfa_views(img: np.ndarray):
    """Le quattro sotto-immagini di un mosaico Bayer (viste, non copie)."""
    return [img[0::2, 0::2], img[0::2, 1::2], img[1::2, 0::2], img[1::2, 1::2]]


# ----------------------------------------------------------------------------
# combinazione dei frame di calibrazione
# ----------------------------------------------------------------------------
def _median_stack(arrays: list[np.ndarray], band_rows: int = 256) -> np.ndarray:
    """Mediana per bande di righe (limita la memoria temporanea)."""
    h = arrays[0].shape[0]
    out = np.empty(arrays[0].shape, dtype=np.float32)
    for y0 in range(0, h, band_rows):
        y1 = min(h, y0 + band_rows)
        cube = np.stack([a[y0:y1] for a in arrays], axis=0)
        out[y0:y1] = np.median(cube, axis=0)
    return out


def build_master(paths: list[str], kind: str, progress: Optional[ProgressCb] = None,
                 max_memory_mb: int = 3000) -> tuple[Optional[np.ndarray], dict]:
    """Costruisce un master (mediana) da una lista di file.

    Restituisce (master float32, info). info contiene is_bayer, pattern, exposure media.
    Se i frame non stanno in memoria si usa una media sigma-clip a due passate.
    """
    if not paths:
        return None, {}
    frames_meta: dict = {"is_bayer": None, "pattern": None, "exposures": [], "shape": None}
    n = len(paths)

    def _check(fr: Frame):
        if frames_meta["shape"] is None:
            frames_meta["shape"] = fr.data.shape
            frames_meta["is_bayer"] = fr.is_bayer
            frames_meta["pattern"] = fr.pattern
        elif fr.data.shape != frames_meta["shape"]:
            raise ValueError(f"{fr.name}: dimensioni {fr.data.shape} diverse dagli altri {kind} {frames_meta['shape']}")
        if fr.exposure:
            frames_meta["exposures"].append(fr.exposure)

    first = load_frame(paths[0])
    _check(first)
    bytes_per_frame = first.data.nbytes
    in_memory = bytes_per_frame * n <= max_memory_mb * 1e6

    if in_memory:
        arrays = [first.data]
        if progress:
            progress(1, n, f"{kind}: {first.name}")
        for i, p in enumerate(paths[1:], start=2):
            fr = load_frame(p)
            _check(fr)
            arrays.append(fr.data)
            if progress:
                progress(i, n, f"{kind}: {fr.name}")
        master = _median_stack(arrays) if n >= 3 else np.mean(np.stack(arrays), axis=0).astype(np.float32)
    else:
        # passata 1: media e varianza (Welford); passata 2: media con rigetto a 3 sigma
        mean = first.data.astype(np.float64)
        m2 = np.zeros_like(mean)
        k = 1
        for p in paths[1:]:
            fr = load_frame(p)
            _check(fr)
            k += 1
            delta = fr.data - mean
            mean += delta / k
            m2 += delta * (fr.data - mean)
            if progress:
                progress(k, 2 * n, f"{kind} (1/2): {fr.name}")
        std = np.sqrt(m2 / max(k - 1, 1)) + 1e-9
        acc = np.zeros_like(mean)
        cnt = np.zeros_like(mean)
        for i, p in enumerate(paths, start=1):
            fr = load_frame(p)
            keep = np.abs(fr.data - mean) <= 3.0 * std
            acc += np.where(keep, fr.data, 0.0)
            cnt += keep
            if progress:
                progress(n + i, 2 * n, f"{kind} (2/2): {fr.name}")
        master = np.where(cnt > 0, acc / np.maximum(cnt, 1), mean).astype(np.float32)

    info = {
        "is_bayer": frames_meta["is_bayer"],
        "pattern": frames_meta["pattern"],
        "n": n,
        "exposure": float(np.mean(frames_meta["exposures"])) if frames_meta["exposures"] else None,
    }
    return master, info


def normalize_flat(flat: np.ndarray, bias: Optional[np.ndarray], dark: Optional[np.ndarray],
                   is_bayer: bool) -> np.ndarray:
    """Sottrae il pedestal (bias o dark) e normalizza il flat a media 1 (per canale)."""
    f = flat.astype(np.float32).copy()
    if dark is not None and dark.shape == f.shape:
        # con un master dark (stessa posa dei flat) il risultato è più corretto,
        # ma di norma i flat sono brevi: usiamo il bias se disponibile
        if bias is not None and bias.shape == f.shape:
            f -= bias
        else:
            f -= np.minimum(dark, f * 0.5)
    elif bias is not None and bias.shape == f.shape:
        f -= bias
    if is_bayer:
        for v in cfa_views(f):
            m = float(np.median(v))
            v /= max(m, 1e-6)
    elif f.ndim == 3:
        for c in range(f.shape[2]):
            m = float(np.median(f[:, :, c]))
            f[:, :, c] /= max(m, 1e-6)
    else:
        f /= max(float(np.median(f)), 1e-6)
    # protezione da valori estremi (bordi, polvere molto scura)
    np.clip(f, 0.05, 20.0, out=f)
    return f


def hot_pixels_from_dark(dark: np.ndarray, is_bayer: bool, sigma: float = 5.0) -> np.ndarray:
    """Maschera dei pixel caldi: valore anomalo rispetto al fondo del master dark."""
    mask = np.zeros(dark.shape, dtype=bool)
    if is_bayer:
        views = cfa_views(dark)
        mviews = cfa_views(mask)
    elif dark.ndim == 3:
        views = [dark[:, :, c] for c in range(dark.shape[2])]
        mviews = [mask[:, :, c] for c in range(dark.shape[2])]
    else:
        views, mviews = [dark], [mask]
    for v, mv in zip(views, mviews):
        med = float(np.median(v))
        s = mad_sigma(v, med)
        mv[...] = v > med + sigma * s
    if mask.ndim == 3:
        mask = np.any(mask, axis=2)
    return mask


def dead_pixels_from_flat(flat_norm: np.ndarray, threshold: float = 0.3) -> np.ndarray:
    m = flat_norm < threshold
    if m.ndim == 3:
        m = np.any(m, axis=2)
    return m


# ----------------------------------------------------------------------------
# correzione cosmetica
# ----------------------------------------------------------------------------
def _median_filter(a: np.ndarray, k: int = 5) -> np.ndarray:
    return cv2.medianBlur(np.ascontiguousarray(a, dtype=np.float32), k)


def cosmetic_correction(img: np.ndarray, is_bayer: bool, mask: Optional[np.ndarray] = None,
                        sigma: float = 6.0, fix_cold: bool = True) -> tuple[np.ndarray, int]:
    """Sostituisce pixel caldi/freddi con la mediana locale (per canale CFA).

    Con `mask` (da master dark/flat) vengono corretti quei pixel; senza mask
    vengono individuati automaticamente i valori isolati oltre `sigma` deviazioni.
    Restituisce (immagine corretta, numero di pixel corretti).
    """
    out = img.copy()
    if is_bayer:
        views = cfa_views(out)
        mviews = cfa_views(mask) if mask is not None else [None] * 4
    elif out.ndim == 3:
        views = [out[:, :, c] for c in range(out.shape[2])]
        mviews = [mask] * 3 if mask is not None else [None] * 3
    else:
        views, mviews = [out], [mask]
    n_fixed = 0
    ring = np.ones((3, 3), np.uint8)
    ring[1, 1] = 0   # massimo/minimo degli 8 vicini (centro escluso)
    for v, mv in zip(views, mviews):
        med = _median_filter(v, 5)
        if mv is not None:
            sel = mv
        else:
            # un hot pixel è isolato: supera nettamente sia la mediana locale sia
            # TUTTI i suoi vicini (una stella, anche piccola, "trascina" i vicini)
            diff = v - med
            s = mad_sigma(diff, 0.0)
            vc = np.ascontiguousarray(v, dtype=np.float32)
            nb_max = cv2.dilate(vc, ring)
            sel = (diff > sigma * s) & ((v - nb_max) > 0.9 * diff)
            if fix_cold:
                nb_min = cv2.erode(vc, ring)
                sel |= (diff < -sigma * s) & ((nb_min - v) > 0.9 * (-diff))
        n_fixed += int(np.count_nonzero(sel))
        v[sel] = med[sel]
    return out, n_fixed


# ----------------------------------------------------------------------------
# calibrazione di un light
# ----------------------------------------------------------------------------
def calibrate_light(frame: Frame, masters: Masters, dark_scaling: bool = True,
                    auto_cosmetic: bool = True, hot_sigma: float = 6.0) -> tuple[np.ndarray, dict]:
    """Applica bias/dark/flat e la correzione cosmetica. Restituisce (dati, info)."""
    x = frame.data.astype(np.float32, copy=True)
    info = {"dark": False, "flat": False, "bias": False, "hot_fixed": 0, "dark_scale": 1.0}
    if masters.dark is not None and masters.dark.shape == x.shape:
        d = masters.dark
        if (dark_scaling and masters.bias is not None and masters.bias.shape == x.shape
                and frame.exposure and masters.dark_exposure and masters.dark_exposure > 0):
            k = float(frame.exposure) / float(masters.dark_exposure)
            if abs(k - 1.0) > 0.05:
                d = masters.bias + (masters.dark - masters.bias) * k
                info["dark_scale"] = k
        x -= d
        info["dark"] = True
    elif masters.bias is not None and masters.bias.shape == x.shape:
        x -= masters.bias
        info["bias"] = True
    if masters.flat is not None and masters.flat.shape == x.shape:
        x /= masters.flat
        info["flat"] = True
    if masters.hot_mask is not None and masters.hot_mask.shape == x.shape[:2]:
        x, n = cosmetic_correction(x, frame.is_bayer, mask=masters.hot_mask)
        info["hot_fixed"] = n
    elif auto_cosmetic:
        x, n = cosmetic_correction(x, frame.is_bayer, mask=None, sigma=hot_sigma)
        info["hot_fixed"] = n
    return x, info


# ----------------------------------------------------------------------------
# bilanciamento del bianco
# ----------------------------------------------------------------------------
def apply_white_balance(data: np.ndarray, is_bayer: bool, pattern: Optional[str], wb) -> np.ndarray:
    """Moltiplica R e B per i coefficienti wb = (r, 1, b), prima del debayer se Bayer."""
    if wb is None:
        return data
    r, _g, b = float(wb[0]), 1.0, float(wb[2])
    if abs(r - 1) < 1e-3 and abs(b - 1) < 1e-3:
        return data
    out = data
    if is_bayer and pattern:
        subs = cfa_views(out)
        subs[pattern.index("R")] *= r
        subs[pattern.index("B")] *= b
    elif out.ndim == 3:
        out[:, :, 0] *= r
        out[:, :, 2] *= b
    return out


# ----------------------------------------------------------------------------
# debayer
# ----------------------------------------------------------------------------
def debayer(bayer: np.ndarray, pattern: str, mode: str = "bilinear") -> np.ndarray:
    """Mosaico Bayer float32 -> RGB float32 (stessa scala)."""
    if mode == "superpixel":
        # ogni blocco 2x2 diventa un pixel RGB (metà risoluzione, meno rumore)
        subs = cfa_views(bayer)  # ordine: (0,0) (0,1) (1,0) (1,1) = lettere del pattern
        rr = subs[pattern.index("R")]
        bb = subs[pattern.index("B")]
        greens = [subs[i] for i, c in enumerate(pattern) if c == "G"]
        h = min(s.shape[0] for s in subs)
        w = min(s.shape[1] for s in subs)
        rgb = np.empty((h, w, 3), np.float32)
        rgb[:, :, 0] = rr[:h, :w]
        rgb[:, :, 1] = 0.5 * (greens[0][:h, :w] + greens[1][:h, :w])
        rgb[:, :, 2] = bb[:h, :w]
        return rgb
    code = _CV_BAYER.get(pattern)
    if code is None:
        raise ValueError(f"Pattern Bayer non supportato: {pattern}")
    u16 = np.clip(bayer * BAYER_U16_SCALE, 0, 65535).astype(np.uint16)
    rgb = cv2.cvtColor(u16, code)
    return rgb.astype(np.float32) / BAYER_U16_SCALE


def to_rgb(data: np.ndarray, is_bayer: bool, pattern: Optional[str], mode: str = "bilinear") -> np.ndarray:
    if is_bayer:
        return debayer(data, pattern or "RGGB", mode)
    if data.ndim == 2:
        return np.repeat(data[:, :, None], 3, axis=2)
    return data
