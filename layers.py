"""Livelli (stile Photoshop, versione essenziale): fusione di più immagini con
opacità, metodi di fusione, maschere (sfumatura, luminosità, pennello, da file,
primo piano automatico), posizione e scala. Ogni livello ha il proprio Sviluppo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from .develop import DevelopParams, develop

BLEND_MODES = [("normal", "Normale"), ("lighten", "Schiarisci"), ("darken", "Scurisci"), ("multiply", "Moltiplica"),
               ("screen", "Scherma"), ("overlay", "Sovrapponi"), ("softlight", "Luce soffusa"),
               ("add", "Somma"), ("difference", "Differenza")]
MASK_TYPES = [("none", "Nessuna"), ("gradient", "Sfumatura lineare"), ("luminosity", "Luminosità del livello"),
              ("brush", "Pennello"), ("foreground", "Primo piano automatico"), ("stars", "Stelle del livello"),
              ("file", "Da file (scala di grigi)")]


@dataclass
class Layer:
    name: str
    image: np.ndarray                          # float32 RGB (H, W, 3)
    is_linear: bool = False                    # True = dati lineari da stirare (stack, FITS)
    params: DevelopParams = field(default_factory=DevelopParams)
    visible: bool = True
    opacity: float = 100.0
    blend: str = "normal"
    offset_x: float = 0.0                      # px (a piena risoluzione del livello base)
    offset_y: float = 0.0
    scale: float = 100.0                       # %
    mask_type: str = "none"
    mask_invert: bool = False
    mask_feather: float = 0.0                  # px (a piena risoluzione)
    grad_start: float = 40.0                   # % dall'alto: inizio della sfumatura
    grad_end: float = 60.0                     # % dall'alto: fine
    grad_horizontal: bool = False
    lum_low: float = 20.0                      # % soglia inferiore
    lum_high: float = 60.0                     # % soglia superiore
    brush_mask: Optional[np.ndarray] = None    # float32 (h, w) alla risoluzione dell'anteprima (spazio tela)
    brush_shape: Optional[tuple] = None        # (h, w) della tela in cui è stata dipinta
    file_mask: Optional[np.ndarray] = None     # float32 (h, w) qualsiasi dimensione (spazio tela)
    _cache_key: str = ""
    _cache: Optional[np.ndarray] = None


# ----------------------------------------------------------------------------
# fusione
# ----------------------------------------------------------------------------
def blend(a: np.ndarray, b: np.ndarray, mode: str) -> np.ndarray:
    """a = sfondo, b = livello (entrambi 0..1)."""
    if mode == "normal":
        return b
    if mode == "lighten":
        return np.maximum(a, b)
    if mode == "darken":
        return np.minimum(a, b)
    if mode == "multiply":
        return a * b
    if mode == "screen":
        return 1.0 - (1.0 - a) * (1.0 - b)
    if mode == "overlay":
        return np.where(a < 0.5, 2.0 * a * b, 1.0 - 2.0 * (1.0 - a) * (1.0 - b))
    if mode == "softlight":
        d = np.where(a <= 0.25, ((16.0 * a - 12.0) * a + 4.0) * a, np.sqrt(np.maximum(a, 0)))
        return np.where(b <= 0.5, a - (1.0 - 2.0 * b) * a * (1.0 - a), a + (2.0 * b - 1.0) * (d - a))
    if mode == "add":
        return np.minimum(a + b, 1.0)
    if mode == "difference":
        return np.abs(a - b)
    return b


# ----------------------------------------------------------------------------
# geometria del livello nella tela
# ----------------------------------------------------------------------------
def place(img: np.ndarray, canvas_hw: tuple[int, int], offset_xy: tuple[float, float], scale_pct: float,
          unit: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Scala e sposta il livello nella tela. `unit` = px tela / px pieni (anteprima ridotta).

    Restituisce (immagine nella tela, copertura 0..1).
    """
    H, W = canvas_hw
    s = max(float(scale_pct), 1.0) / 100.0
    dx, dy = float(offset_xy[0]) * unit, float(offset_xy[1]) * unit
    if abs(s - 1.0) < 1e-6 and abs(dx) < 1e-6 and abs(dy) < 1e-6 and img.shape[:2] == (H, W):
        return img, np.ones((H, W), np.float32)
    M = np.array([[s, 0.0, dx], [0.0, s, dy]], np.float64)
    out = cv2.warpAffine(np.ascontiguousarray(img), M, (W, H), flags=cv2.INTER_LINEAR if s < 1 else cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    cov = cv2.warpAffine(np.ones(img.shape[:2], np.float32), M, (W, H), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out, np.clip(cov, 0.0, 1.0)


# ----------------------------------------------------------------------------
# maschere (nello spazio della tela)
# ----------------------------------------------------------------------------
def layer_mask(layer: Layer, developed_in_canvas: np.ndarray, canvas_hw: tuple[int, int], unit: float) -> Optional[np.ndarray]:
    H, W = canvas_hw
    t = layer.mask_type
    m: Optional[np.ndarray] = None
    if t == "gradient":
        a, b = layer.grad_start / 100.0, layer.grad_end / 100.0
        if abs(b - a) < 1e-3:
            b = a + 1e-3
        coord = (np.linspace(0, 1, W, dtype=np.float32)[None, :] if layer.grad_horizontal
                 else np.linspace(0, 1, H, dtype=np.float32)[:, None])
        g = np.clip((coord - a) / (b - a), 0.0, 1.0)
        m = np.broadcast_to(g, (H, W)).astype(np.float32)
    elif t == "luminosity":
        L = 0.2126 * developed_in_canvas[:, :, 0] + 0.7152 * developed_in_canvas[:, :, 1] + 0.0722 * developed_in_canvas[:, :, 2]
        lo, hi = layer.lum_low / 100.0, layer.lum_high / 100.0
        if hi - lo < 1e-3:
            hi = lo + 1e-3
        x = np.clip((L - lo) / (hi - lo), 0.0, 1.0)
        m = (x * x * (3.0 - 2.0 * x)).astype(np.float32)
    elif t == "brush":
        if layer.brush_mask is not None:
            m = layer.brush_mask
            if m.shape != (H, W):
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
        else:
            m = np.zeros((H, W), np.float32)
    elif t == "file":
        if layer.file_mask is not None:
            m = layer.file_mask
            if m.shape != (H, W):
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
    elif t == "stars":
        from .develop import star_mask
        m = star_mask(developed_in_canvas, unit)
    elif t == "foreground":
        from .foreground import foreground_mask
        try:
            fg, _ = foreground_mask(developed_in_canvas)
        except Exception:
            fg = None
        m = fg if fg is not None else np.zeros((H, W), np.float32)
    if m is None:
        return None
    m = np.ascontiguousarray(m, dtype=np.float32)
    if layer.mask_feather > 0:
        sig = max(0.5, float(layer.mask_feather) * unit)
        m = cv2.GaussianBlur(m, (0, 0), sig)
    if layer.mask_invert:
        m = 1.0 - m
    return np.clip(m, 0.0, 1.0)


def paint_brush(mask: np.ndarray, x: float, y: float, radius: float, hardness: float, value: float):
    """Dipinge un cerchio morbido nella maschera (in-place). value 1 = aggiungi, 0 = cancella."""
    h, w = mask.shape
    r = max(float(radius), 1.0)
    x0, x1 = int(max(0, x - r - 1)), int(min(w, x + r + 2))
    y0, y1 = int(max(0, y - r - 1)), int(min(h, y + r + 2))
    if x1 <= x0 or y1 <= y0:
        return
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.sqrt((xs - x) ** 2 + (ys - y) ** 2) / r
    hard = float(np.clip(hardness, 0.0, 1.0))
    edge0 = hard * 0.98
    w_ = np.clip((1.0 - d) / max(1.0 - edge0, 1e-3), 0.0, 1.0)
    w_ = w_ * w_ * (3.0 - 2.0 * w_)
    region = mask[y0:y1, x0:x1]
    if value > 0.5:
        region[:] = np.maximum(region, w_)
    else:
        region[:] = np.minimum(region, 1.0 - w_)


# ----------------------------------------------------------------------------
# composizione
# ----------------------------------------------------------------------------
def _developed(layer: Layer, image: np.ndarray, scale: float, key: str) -> np.ndarray:
    if layer._cache is not None and layer._cache_key == key:
        return layer._cache
    out = develop(image, layer.params, layer.is_linear, scale=scale)
    layer._cache, layer._cache_key = out, key
    return out


def composite(layers: list[Layer], proxies: Optional[list[np.ndarray]] = None, full: bool = False,
              show_mask_of: Optional[int] = None) -> np.ndarray:
    """Fonde i livelli. Con `proxies` (immagini ridotte, una per livello) calcola l'anteprima.

    Il livello 0 è la base e definisce la tela. show_mask_of = indice del livello di cui
    mostrare la maschera in rosso (solo anteprima).
    """
    if not layers:
        raise ValueError("Nessun livello")
    imgs = proxies if (proxies is not None and not full) else [lay.image for lay in layers]
    base_layer = layers[0]
    base_full_w = base_layer.image.shape[1]
    unit = imgs[0].shape[1] / float(base_full_w)          # px tela / px pieni
    key0 = f"{'full' if full else 'proxy'}|{base_layer.params.to_json()}|{imgs[0].shape}"
    out = _developed(base_layer, imgs[0], unit, key0).copy()
    H, W = out.shape[:2]
    for i, lay in enumerate(layers[1:], start=1):
        if not lay.visible or lay.opacity <= 0:
            continue
        img = imgs[i]
        unit_i = img.shape[1] / float(lay.image.shape[1])
        key = f"{'full' if full else 'proxy'}|{lay.params.to_json()}|{img.shape}"
        dev = _developed(lay, img, unit_i, key)
        # la tela può avere dimensioni (e fattore di riduzione) diversi dal livello:
        # posiziona e scala, in unità di px del livello base a piena risoluzione
        eff_scale = float(lay.scale) * (unit / max(unit_i, 1e-6))
        placed, cov = place(dev, (H, W), (lay.offset_x, lay.offset_y), eff_scale, unit)
        alpha = cov * (float(lay.opacity) / 100.0)
        m = layer_mask(lay, placed, (H, W), unit)
        if m is not None:
            alpha = alpha * m
        mixed = blend(out, placed, lay.blend)
        out = out * (1.0 - alpha[:, :, None]) + mixed * alpha[:, :, None]
        if show_mask_of == i and not full:
            mm = m if m is not None else cov
            out = out * (1.0 - 0.5 * mm[:, :, None]) + np.array([1.0, 0.15, 0.15], np.float32)[None, None, :] * 0.5 * mm[:, :, None]
    np.clip(out, 0.0, 1.0, out=out)
    return np.ascontiguousarray(out, dtype=np.float32)


def invalidate(layer: Layer):
    layer._cache = None
    layer._cache_key = ""
