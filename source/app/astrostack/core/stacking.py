"""Motore di stacking: cache su disco dei frame calibrati e combinazione per bande.

I frame calibrati e demosaicizzati vengono salvati come .npy uint16 (memmap):
così anche 100 frame da 20 MP si combinano con memoria limitata. La
combinazione avviene per bande di righe con rigetto kappa-sigma completo.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .registration import scale_transform, source_rows_for_band, warp_band

CACHE_SCALE = 16000.0      # valore float -> uint16 (headroom fino a ~4.0)
CACHE_PEDESTAL = 0.02      # consente piccoli valori negativi dopo la calibrazione


class FrameCache:
    """Cartella temporanea con un file .npy uint16 per frame."""

    def __init__(self, base_dir: Optional[str] = None):
        base = base_dir if base_dir else tempfile.gettempdir()
        os.makedirs(base, exist_ok=True)
        self.dir = tempfile.mkdtemp(prefix="astrostack_", dir=base)
        self.paths: list[str] = []
        self._lock = threading.Lock()

    def put(self, rgb: np.ndarray, index: Optional[int] = None) -> str:
        """Salva un frame; `index` rende il nome univoco anche con più thread in parallelo."""
        with self._lock:
            idx = len(self.paths) if index is None else int(index)
            path = os.path.join(self.dir, f"frame_{idx:04d}.npy")
            self.paths.append(path)
        u16 = np.clip((rgb + CACHE_PEDESTAL) * CACHE_SCALE, 0, 65535).astype(np.uint16)
        tmp = path + ".part"
        with open(tmp, "wb") as f:      # scrittura atomica: il file appare solo quando è completo
            np.save(f, u16)
        os.replace(tmp, path)
        return path

    @staticmethod
    def open(path: str) -> np.ndarray:
        return np.load(path, mmap_mode="r")

    @staticmethod
    def decode(u16: np.ndarray) -> np.ndarray:
        return u16.astype(np.float32) / CACHE_SCALE - CACHE_PEDESTAL

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


@dataclass
class StackOptions:
    method: str = "sigma"          # media | mediana | sigma | winsor | linearfit
    kappa_low: float = 3.0
    kappa_high: float = 2.5
    iterations: int = 2
    max_band_mb: int = 900
    interp: str = "cubica"


def combine(cube: np.ndarray, cov: np.ndarray, weights: np.ndarray, opt: StackOptions) -> np.ndarray:
    """Combina cube (N, h, W, C) con copertura cov (N, h, W) e pesi (N,) -> (h, W, C)."""
    n = cube.shape[0]
    w = (weights.astype(np.float32)[:, None, None, None] * cov[..., None].astype(np.float32))
    wsum = w.sum(axis=0)
    wsum_safe = np.maximum(wsum, 1e-9)
    mean = (w * cube).sum(axis=0) / wsum_safe
    method = opt.method
    if n < 3 and method not in ("media", "max"):
        method = "media"
    if n < 5 and method in ("sigma", "winsor", "linearfit"):
        method = "mediana"
    if method == "media":
        return mean.astype(np.float32)
    if method == "max":                                    # scie stellari: tiene il pixel più luminoso
        filled = np.where(cov[..., None], cube, 0.0)
        return filled.max(axis=0).astype(np.float32)
    # per usare np.median (veloce, senza NaN) i pixel non coperti prendono la media pesata
    filled = np.where(cov[..., None], cube, mean[None])
    center = np.median(filled, axis=0)
    if method == "mediana":
        return center.astype(np.float32)

    if method == "linearfit":
        # Normalizza ogni frame al riferimento robusto (mediana dei frame) con
        # un fit lineare y=a*x+b sui pixel validi, poi esegue sigma clipping.
        # È particolarmente utile quando il fondo cielo cambia tra sessioni.
        norm = cube.astype(np.float32, copy=True)
        h, ww, cc = center.shape
        max_samples = 40_000
        for i in range(n):
            valid2d = cov[i]
            if int(valid2d.sum()) < 100:
                continue
            yy, xx = np.nonzero(valid2d)
            step = max(1, len(yy) // max_samples)
            yy, xx = yy[::step], xx[::step]
            for c in range(cc):
                xv = cube[i, yy, xx, c].astype(np.float64)
                yv = center[yy, xx, c].astype(np.float64)
                good = np.isfinite(xv) & np.isfinite(yv)
                if good.sum() < 80:
                    continue
                xv, yv = xv[good], yv[good]
                qlo, qhi = np.percentile(xv, [5, 95])
                sel = (xv >= qlo) & (xv <= qhi)
                if sel.sum() < 50:
                    continue
                try:
                    a, b = np.polyfit(xv[sel], yv[sel], 1)
                except Exception:
                    continue
                if not np.isfinite(a) or not np.isfinite(b):
                    continue
                a = float(np.clip(a, 0.5, 2.0))
                b = float(np.clip(b, -0.5, 0.5))
                norm[i, :, :, c] = norm[i, :, :, c] * a + b
        cube = norm
        mean = (w * cube).sum(axis=0) / wsum_safe
        filled = np.where(cov[..., None], cube, center[None])
        center = np.median(filled, axis=0)
        # Da qui in poi usa lo stesso rigetto iterativo di kappa-sigma.
        method = "sigma"
    dev = filled - center[None]
    sigma = 1.4826 * np.median(np.abs(dev), axis=0) + 1e-6
    if method == "winsor":
        lo = center - opt.kappa_low * sigma
        hi = center + opt.kappa_high * sigma
        clipped = np.clip(cube, lo[None], hi[None])
        return ((w * clipped).sum(axis=0) / wsum_safe).astype(np.float32)
    keep = (dev >= -opt.kappa_low * sigma[None]) & (dev <= opt.kappa_high * sigma[None])
    wk = w * keep
    for _ in range(max(0, opt.iterations - 1)):
        ws = np.maximum(wk.sum(axis=0), 1e-9)
        c2 = (wk * cube).sum(axis=0) / ws
        v2 = (wk * (cube - c2[None]) ** 2).sum(axis=0) / ws
        s2 = np.sqrt(v2) + 1e-6
        d2 = cube - c2[None]
        keep = (d2 >= -opt.kappa_low * s2[None]) & (d2 <= opt.kappa_high * s2[None])
        wk = w * keep
    ws = wk.sum(axis=0)
    result = (wk * cube).sum(axis=0) / np.maximum(ws, 1e-9)
    # dove tutto è stato rigettato torna alla media pesata
    result = np.where(ws > 0, result, mean)
    return result.astype(np.float32)


def stack_frames(cache_paths: list[str], transforms: list[np.ndarray], weights: list[float],
                 shape: tuple[int, int, int], opt: StackOptions,
                 progress: Optional[Callable[[int, int, str], None]] = None,
                 cancelled: Optional[Callable[[], bool]] = None,
                 rows: Optional[tuple[int, int]] = None) -> np.ndarray:
    """Registra e combina i frame dalla cache, per bande. Restituisce (H, W, C) float32.

    Con `rows=(r0, r1)` elabora e restituisce solo quelle righe (r1-r0, W, C).
    """
    n = len(cache_paths)
    H, W, C = shape
    r0, r1 = (0, H) if rows is None else (max(0, rows[0]), min(H, rows[1]))
    result = np.zeros((r1 - r0, W, C), np.float32)
    band = int(opt.max_band_mb * 1e6 / max(n * W * C * 4 * 2.2, 1))
    band = max(16, min(band, r1 - r0))
    mm = [FrameCache.open(p) for p in cache_paths]
    wts = np.asarray(weights, np.float32)
    total = int(np.ceil((r1 - r0) / band))
    for bi, y0 in enumerate(range(r0, r1, band)):
        if cancelled and cancelled():
            break
        y1 = min(r1, y0 + band)
        cube = np.empty((n, y1 - y0, W, C), np.float32)
        cov = np.empty((n, y1 - y0, W), bool)
        for i in range(n):
            ys0, ys1 = source_rows_for_band(transforms[i], y0, y1, W, H)
            if ys1 <= ys0:
                cube[i] = 0
                cov[i] = False
                continue
            src = FrameCache.decode(np.asarray(mm[i][ys0:ys1]))
            out, cv = warp_band(src, ys0, transforms[i], y0, y1, W, opt.interp)
            if out.ndim == 2:
                out = out[:, :, None]
            cube[i] = out
            cov[i] = cv
        result[y0 - r0:y1 - r0] = combine(cube, cov, wts, opt)
        if progress:
            progress(bi + 1, total, f"Stacking righe {y0}-{y1}")
    return result


def coverage_map(transforms: list[np.ndarray], shape: tuple[int, int], step: int = 8,
                 source_shape: Optional[tuple[int, int]] = None) -> np.ndarray:
    """Quanti frame coprono ogni pixel (a bassa risoluzione).

    ``shape`` è la geometria *di uscita*. Normalmente sorgente e uscita hanno
    la stessa dimensione; con Drizzle 2x, invece, i frame in cache restano 1x
    mentre lo stack è 2x. In quel caso ``source_shape`` evita di costruire una
    maschera di copertura grande il doppio e quindi di calcolare un crop errato.
    """
    H, W = shape
    src_H, src_W = source_shape or shape
    h, w = max(1, H // step), max(1, W // step)
    sh, sw = max(1, src_H // step), max(1, src_W // step)
    acc = np.zeros((h, w), np.int32)
    import cv2
    for M in transforms:
        S = scale_transform(np.asarray(M, np.float64), step)
        if S.shape[0] == 3:
            m = cv2.warpPerspective(np.full((sh, sw), 1, np.uint8), S, (w, h), flags=cv2.INTER_NEAREST)
        else:
            m = cv2.warpAffine(np.full((sh, sw), 1, np.uint8), S, (w, h), flags=cv2.INTER_NEAREST)
        acc += m
    return acc


def auto_crop_box(transforms: list[np.ndarray], shape: tuple[int, int], min_fraction: float = 0.999,
                  source_shape: Optional[tuple[int, int]] = None):
    """Riquadro (x0, y0, x1, y1) coperto da (quasi) tutti i frame."""
    cov = coverage_map(transforms, shape, source_shape=source_shape)
    n = len(transforms)
    need = max(1, int(np.ceil(n * min_fraction)))
    full = cov >= need
    rows = np.where(full.all(axis=1))[0]
    cols = np.where(full.all(axis=0))[0]
    step = 8
    if rows.size == 0 or cols.size == 0:
        # riquadro massimale greedy: righe/colonne con copertura in almeno il 90% dei pixel
        rows = np.where(full.mean(axis=1) > 0.9)[0]
        cols = np.where(full.mean(axis=0) > 0.9)[0]
        if rows.size == 0 or cols.size == 0:
            return 0, 0, shape[1], shape[0]
    return int(cols[0] * step), int(rows[0] * step), int((cols[-1] + 1) * step), int((rows[-1] + 1) * step)
