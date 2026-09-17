"""Auto-stretch per anteprima ed esportazione 8 bit (funzione di trasferimento midtones)."""
from __future__ import annotations

import numpy as np


def _mtf(m: float, x: np.ndarray) -> np.ndarray:
    return ((m - 1.0) * x) / (((2.0 * m - 1.0) * x) - m + 1e-12)


def auto_stretch(img: np.ndarray, target_bg: float = 0.25, shadows_clip: float = -2.8,
                 linked: bool = True) -> np.ndarray:
    """Restituisce un'immagine float32 0..1 già "stirata" (non lineare)."""
    x = img.astype(np.float32, copy=False)
    if x.ndim == 2:
        x = x[:, :, None]
    sub = x[::4, ::4].reshape(-1, x.shape[2])
    out = np.empty_like(x)
    C = x.shape[2]
    if linked:
        lum = sub.mean(axis=1)
        med = float(np.median(lum))
        mad = float(np.median(np.abs(lum - med))) + 1e-9
        params = [(med, mad)] * C
    else:
        params = []
        for c in range(C):
            med = float(np.median(sub[:, c]))
            mad = float(np.median(np.abs(sub[:, c] - med))) + 1e-9
            params.append((med, mad))
    for c in range(C):
        med, mad = params[c]
        mad *= 1.4826
        c0 = min(max(med + shadows_clip * mad, 0.0), 0.99)
        m = _mtf(target_bg, max(min((med - c0) / max(1.0 - c0, 1e-6), 0.999), 1e-6))
        xc = (x[:, :, c] - c0) / max(1.0 - c0, 1e-6)
        np.clip(xc, 0.0, 1.0, out=xc)
        out[:, :, c] = _mtf(m, xc)
    np.clip(out, 0.0, 1.0, out=out)
    if img.ndim == 2:
        return out[:, :, 0]
    return out


def to_uint8(img: np.ndarray, stretch: bool = True) -> np.ndarray:
    y = auto_stretch(img) if stretch else np.clip(img, 0.0, 1.0)
    return (y * 255.0 + 0.5).astype(np.uint8)
