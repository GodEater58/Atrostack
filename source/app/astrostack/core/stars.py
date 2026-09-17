"""Rilevamento stelle, centroidi sub-pixel, FWHM e metriche di qualità del frame."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares

from .calibration import mad_sigma
from .loader import luminance


@dataclass
class StarField:
    xy: np.ndarray                      # (N, 2) coordinate (x, y) a piena risoluzione, ordinate per flusso
    flux: np.ndarray                    # (N,)
    fwhm: float = 0.0                   # FWHM mediana in pixel (piena risoluzione)
    eccentricity: float = 0.0           # 0 = stelle rotonde
    n_detected: int = 0                 # stelle trovate (prima del taglio a max_stars)
    background: float = 0.0             # livello mediano del fondo cielo
    noise: float = 0.0                  # sigma del rumore di fondo
    saturated: int = 0
    scale: int = 1
    extra: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.xy.shape[0])


def downsample_factor(shape, max_dim: int = 1400) -> int:
    f = 1
    while max(shape[0], shape[1]) / f > max_dim:
        f *= 2
    return f


def estimate_background(img: np.ndarray, tile: int = 64) -> np.ndarray:
    """Fondo cielo (2D) tramite mediane robuste per riquadri, interpolato."""
    h, w = img.shape
    ny, nx = max(2, int(np.ceil(h / tile))), max(2, int(np.ceil(w / tile)))
    grid = np.empty((ny, nx), np.float32)
    for j in range(ny):
        for i in range(nx):
            t = img[j * tile:(j + 1) * tile, i * tile:(i + 1) * tile]
            if t.size == 0:
                grid[j, i] = grid[j, max(i - 1, 0)]
                continue
            v = t.ravel()
            m = np.median(v)
            s = 1.4826 * np.median(np.abs(v - m)) + 1e-9
            sel = v < m + 2.0 * s     # esclude le stelle
            grid[j, i] = np.median(v[sel]) if sel.sum() > 10 else m
    # attenua i riquadri anomali (nebulose brillanti, stelle enormi)
    grid = cv2.medianBlur(grid, 3) if min(ny, nx) >= 3 else grid
    bg = cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
    return bg


def _refine_star(lum: np.ndarray, x: float, y: float, r: int, rgb: np.ndarray | None = None,
                 passes: int = 2):
    """Centroide pesato + momenti secondi su un ritaglio a piena risoluzione.

    Due passate: la prima ricentra il ritaglio (la posizione iniziale viene
    dall'immagine ridotta), la seconda misura su un ritaglio piccolo attorno al
    centroide, così il rumore di fondo non gonfia la FWHM.
    """
    res = None
    for p in range(passes):
        rr = r if p == 0 else min(r, 7)
        res = _moments(lum, x, y, rr, rgb)
        if res is None:
            return None
        x, y = res[0], res[1]
    return res


def _moments(lum: np.ndarray, x: float, y: float, r: int, rgb: np.ndarray | None = None):
    h, w = lum.shape
    x0, x1 = int(round(x)) - r, int(round(x)) + r + 1
    y0, y1 = int(round(y)) - r, int(round(y)) + r + 1
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    st = lum[y0:y1, x0:x1].astype(np.float32)
    border = np.concatenate([st[0], st[-1], st[:, 0], st[:, -1]])
    bg = float(np.median(border))
    st = st - bg
    st[st < 0] = 0
    tot = float(st.sum())
    if tot <= 0:
        return None
    ys, xs = np.mgrid[y0:y1, x0:x1]
    cx = float((st * xs).sum() / tot)
    cy = float((st * ys).sum() / tot)
    dx, dy = xs - cx, ys - cy
    vxx = float((st * dx * dx).sum() / tot)
    vyy = float((st * dy * dy).sum() / tot)
    vxy = float((st * dx * dy).sum() / tot)
    tr = vxx + vyy
    det = vxx * vyy - vxy * vxy
    disc = max(tr * tr / 4 - det, 0.0)
    l1 = tr / 2 + np.sqrt(disc)
    l2 = max(tr / 2 - np.sqrt(disc), 1e-6)
    fwhm = 2.3548 * np.sqrt(max(tr / 2, 1e-6))
    ecc = float(np.sqrt(max(1 - l2 / l1, 0.0))) if l1 > 0 else 0.0
    peak = float(st.max())
    if rgb is not None and rgb.ndim == 3:
        peak = float(rgb[y0:y1, x0:x1].max())   # saturazione valutata sul canale più alto
    else:
        peak = peak + bg
    return cx, cy, tot, fwhm, ecc, peak


def _fit_gaussian(lum: np.ndarray, x: float, y: float, r: int = 7):
    """Fit di una gaussiana 2D (assi allineati) su un ritaglio: (fwhm, ecc) o None."""
    h, w = lum.shape
    x0, x1 = int(round(x)) - r, int(round(x)) + r + 1
    y0, y1 = int(round(y)) - r, int(round(y)) + r + 1
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return None
    st = lum[y0:y1, x0:x1].astype(np.float64)
    ys, xs = np.mgrid[y0:y1, x0:x1]
    bg0 = float(np.median(np.concatenate([st[0], st[-1], st[:, 0], st[:, -1]])))
    amp0 = float(st.max() - bg0)
    if amp0 <= 0:
        return None

    def model(p):
        a, cx, cy, sx, sy, b = p
        return a * np.exp(-((xs - cx) ** 2 / (2 * sx * sx) + (ys - cy) ** 2 / (2 * sy * sy))) + b

    p0 = [amp0, x, y, 1.5, 1.5, bg0]
    lb = [0, x - r, y - r, 0.4, 0.4, -np.inf]
    ub = [np.inf, x + r, y + r, r, r, np.inf]
    try:
        sol = least_squares(lambda p: (model(p) - st).ravel(), p0, bounds=(lb, ub), max_nfev=80)
    except Exception:
        return None
    a, cx, cy, sx, sy, b = sol.x
    if not sol.success and sol.nfev < 5:
        return None
    fwhm = 2.3548 * float(np.sqrt(sx * sy))
    lo, hi = min(sx, sy), max(sx, sy)
    ecc = float(np.sqrt(max(1 - (lo / hi) ** 2, 0.0)))
    return fwhm, ecc


def detect_stars(img: np.ndarray, max_stars: int = 250, sigma: float = 5.0,
                 sat_level: float = 0.9) -> StarField:
    """Trova le stelle in un'immagine RGB/mono lineare (float32, 1.0 = saturazione)."""
    lum = luminance(img)
    h, w = lum.shape
    f = downsample_factor(lum.shape)
    if f > 1:
        small = cv2.resize(lum, (w // f, h // f), interpolation=cv2.INTER_AREA)
    else:
        small = lum
    bg = estimate_background(small)
    sub = small - bg
    smooth = cv2.GaussianBlur(sub, (0, 0), 1.0)
    noise_s = mad_sigma(smooth, 0.0)
    thr = sigma * noise_s
    mask = (smooth > thr).astype(np.uint8)
    n_lab, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n_lab <= 1:
        return StarField(xy=np.zeros((0, 2), np.float32), flux=np.zeros(0, np.float32),
                         background=float(np.median(bg)), noise=float(mad_sigma(sub, 0.0)), scale=f)
    areas = stats[1:, cv2.CC_STAT_AREA]
    max_area = max(60, int(0.002 * small.size))
    ids = np.arange(1, n_lab)
    ok = (areas >= 2) & (areas <= max_area)
    # esclude componenti che toccano il bordo
    x_ = stats[1:, cv2.CC_STAT_LEFT]
    y_ = stats[1:, cv2.CC_STAT_TOP]
    ww = stats[1:, cv2.CC_STAT_WIDTH]
    hh = stats[1:, cv2.CC_STAT_HEIGHT]
    ok &= (x_ > 1) & (y_ > 1) & (x_ + ww < small.shape[1] - 1) & (y_ + hh < small.shape[0] - 1)
    ids = ids[ok]
    n_detected = int(ids.size)
    if n_detected == 0:
        return StarField(xy=np.zeros((0, 2), np.float32), flux=np.zeros(0, np.float32),
                         background=float(np.median(bg)), noise=float(mad_sigma(sub, 0.0)), scale=f)
    flux = np.asarray(ndimage.sum(sub, labels, ids), dtype=np.float64)
    com = np.asarray(ndimage.center_of_mass(np.maximum(sub, 0), labels, ids), dtype=np.float64)
    order = np.argsort(-flux)[: max_stars * 2]
    cand = com[order]
    cand_flux = flux[order]
    # raffinamento a piena risoluzione
    r = 5 if f == 1 else min(12, 3 * f + 2)
    xy, fl, fw, ec, pk = [], [], [], [], []
    for (cy, cx), fx in zip(cand, cand_flux):
        X = cx * f + (f - 1) / 2.0
        Y = cy * f + (f - 1) / 2.0
        ref = _refine_star(lum, X, Y, r, img)
        if ref is None:
            continue
        rx, ry, tot, fwhm, ecc, peak = ref
        if abs(rx - X) > r or abs(ry - Y) > r:
            continue
        xy.append((rx, ry))
        fl.append(tot)
        fw.append(fwhm)
        ec.append(ecc)
        pk.append(peak)
        if len(xy) >= max_stars:
            break
    xy_a = np.asarray(xy, np.float32).reshape(-1, 2)
    fl_a = np.asarray(fl, np.float32)
    pk_a = np.asarray(pk, np.float32)
    fw_a = np.asarray(fw, np.float32)
    ec_a = np.asarray(ec, np.float32)
    sat = pk_a >= sat_level
    good = ~sat
    # FWHM ed eccentricità: fit gaussiano sulle stelle più brillanti non sature
    # (i momenti risentono del rumore di fondo e sovrastimano la FWHM)
    fits = []
    for i in np.where(good)[0][:40]:
        g = _fit_gaussian(lum, float(xy_a[i, 0]), float(xy_a[i, 1]))
        if g is not None and 0.8 < g[0] < 30:
            fits.append(g)
    if len(fits) >= 3:
        fwhm_med = float(np.median([g[0] for g in fits]))
        ecc_med = float(np.median([g[1] for g in fits]))
    else:
        fwhm_med = float(np.median(fw_a[good])) if good.sum() >= 3 else (float(np.median(fw_a)) if fw_a.size else 0.0)
        ecc_med = float(np.median(ec_a[good])) if good.sum() >= 3 else (float(np.median(ec_a)) if ec_a.size else 0.0)
    return StarField(xy=xy_a, flux=fl_a, fwhm=fwhm_med, eccentricity=ecc_med,
                     n_detected=n_detected, background=float(np.median(bg)),
                     noise=float(mad_sigma(sub, 0.0)), saturated=int(sat.sum()), scale=f)


def quality_score(sf: StarField, ref_fwhm: float, ref_nstars: float, ref_noise: float) -> float:
    """Punteggio 0..1+ del frame: più stelle, stelle più fini e meno rumore = meglio."""
    if sf.n == 0:
        return 0.0
    s_fwhm = (ref_fwhm / max(sf.fwhm, 0.3)) if sf.fwhm > 0 else 1.0
    s_n = min(sf.n_detected / max(ref_nstars, 1.0), 1.5)
    s_noise = (ref_noise / max(sf.noise, 1e-9)) if sf.noise > 0 else 1.0
    s_ecc = 1.0 - 0.5 * min(sf.eccentricity, 1.0)
    score = (s_fwhm ** 1.0) * (s_n ** 0.5) * (s_noise ** 0.5) * s_ecc
    return float(score)
