"""Paesaggio: primo piano nitido.

Nelle foto di paesaggio notturno lo stack allineato sulle stelle rende sfocati
alberi, orizzonte, edifici. Qui il primo piano viene riconosciuto in automatico
(zona scura e priva di stelle), allineato su sé stesso e ricostruito con la
mediana dei frame, poi fuso nello stack del cielo con un bordo sfumato.
"""
from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np

from .loader import luminance
from .stars import downsample_factor


def foreground_mask(stack: np.ndarray, dark_ratio: float = 0.55,
                    min_fraction: float = 0.002) -> tuple[Optional[np.ndarray], dict]:
    """Maschera float32 (H, W) con 1 = primo piano (bordi sfumati), oppure None.

    Il primo piano è una zona nettamente più scura del modello del cielo che,
    a differenza di una nebulosa oscura o della vignettatura, non contiene stelle.
    """
    from .gradient import fit_background
    from .stars import detect_stars

    H, W = stack.shape[:2]
    lum = luminance(stack)
    f = downsample_factor((H, W), 1200)
    hs, ws = H // f, W // f
    small = cv2.resize(lum, (ws, hs), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 1.5)

    # tante stelle: servono solo per sapere DOVE c'è cielo. I "rilevamenti" con
    # flusso trascurabile sono rumore e vengono ignorati
    sf = detect_stars(stack, max_stars=3000, sigma=5.0)
    star_xy = sf.xy
    if sf.n > 0:
        star_xy = sf.xy[sf.flux >= 0.1 * float(np.median(sf.flux))]
    stars = np.zeros((hs, ws), np.uint8)
    for x, y in np.asarray(star_xy, np.float64):
        xi, yi = int(x / f), int(y / f)
        if 0 <= xi < ws and 0 <= yi < hs:
            stars[yi, xi] = 1
    n_stars = int(stars.sum())
    if n_stars < 30:
        return None, {"reason": "poche stelle per distinguere il cielo"}

    # modello liscio del cielo (le zone scure e quelle luminose vengono escluse dal fit)
    model, _ = fit_background(np.repeat(small[:, :, None], 3, axis=2), degree=2)
    sky_level = model[:, :, 0] if model is not None else np.full_like(small, float(np.median(small)))
    sky_level = np.maximum(sky_level, 1e-4)

    dark = (small < dark_ratio * sky_level).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    sky_area = max(hs * ws - int(dark.sum()), 1)
    sky_density = n_stars / sky_area
    fg = np.zeros_like(dark)
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < 0.002 * hs * ws:
            continue
        comp = lab == i
        inside = int(stars[comp].sum())
        expected = sky_density * area
        if inside <= max(2.0, 0.15 * expected):       # quasi nessuna stella: è primo piano
            fg[comp] = 1
    # riempie i buchi interni (rami, finestre scure...)
    holes = cv2.bitwise_not(fg * 255)
    nh, labh, statsh, _ = cv2.connectedComponentsWithStats(holes, connectivity=4)
    for i in range(1, nh):
        x, y, w, h = (statsh[i, cv2.CC_STAT_LEFT], statsh[i, cv2.CC_STAT_TOP],
                      statsh[i, cv2.CC_STAT_WIDTH], statsh[i, cv2.CC_STAT_HEIGHT])
        touches = x == 0 or y == 0 or x + w >= ws or y + h >= hs
        if not touches and statsh[i, cv2.CC_STAT_AREA] < 0.01 * hs * ws:
            fg[labh == i] = 1
    frac = float(fg.mean())
    if frac < min_fraction:
        return None, {"reason": "nessun primo piano riconosciuto", "fraction": frac}
    soft = cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 1.5)
    mask = cv2.resize(soft, (W, H), interpolation=cv2.INTER_LINEAR)
    np.clip(mask, 0.0, 1.0, out=mask)
    ys = np.where(mask.max(axis=1) > 0.02)[0]
    rows = (int(ys.min()), int(ys.max()) + 1) if ys.size else (0, H)
    return mask.astype(np.float32), {"fraction": frac, "rows": rows, "scale": f}


def foreground_shift(ref_small: np.ndarray, frame_small: np.ndarray, mask_small: np.ndarray, factor: int):
    """Traslazione (in pixel pieni) del primo piano del frame rispetto al riferimento."""
    from .registration import phase_transform
    md = cv2.dilate(mask_small, np.ones((15, 15), np.uint8))
    a = ref_small * md
    b = frame_small * md
    tr = phase_transform(a, b, factor)
    if tr is None:
        return None
    dx, dy = tr.shift
    if abs(dx) > 0.3 * frame_small.shape[1] * factor or abs(dy) > 0.3 * frame_small.shape[0] * factor:
        return None
    return tr.M


def composite(sky: np.ndarray, foreground: np.ndarray, mask: np.ndarray, rows: tuple[int, int],
              coverage: Optional[np.ndarray] = None) -> np.ndarray:
    """Fonde il primo piano ricostruito nello stack del cielo (solo nelle righe interessate).

    `coverage` (stessa altezza/larghezza di `foreground`, bool o 0..1) azzera la maschera dove
    il primo piano non è stato ricostruito da nessun frame: lì resta visibile lo stack originale
    invece di un blocco nero.
    """
    out = sky.copy()
    y0, y1 = rows
    m = mask[y0:y1].astype(np.float32, copy=True)
    if coverage is not None:
        m *= coverage.astype(np.float32)
    m = m[:, :, None]
    out[y0:y1] = foreground * m + sky[y0:y1] * (1.0 - m)
    return out
