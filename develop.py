"""Sviluppo dell'immagine (stile Lightroom): tono, colore, dettaglio, curva, effetti, geometria.

Tutte le regolazioni lavorano su immagini float32 RGB 0..1. L'ingresso è lo stack
lineare (viene "stirato" come primo passo) oppure un'immagine già non lineare.
La stessa funzione `develop()` serve per l'anteprima (immagine ridotta, con
`scale` < 1 per mantenere identici i raggi dei filtri) e per l'esportazione.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

import cv2
import numpy as np

from .stretch import auto_stretch


@dataclass
class DevelopParams:
    enabled: bool = True
    # stretch (solo immagini lineari)
    stretch_type: str = "mtf"         # mtf | arcsinh | hybrid | masked
    stretch_bg: float = 25.0          # % livello del fondo cielo dopo lo stretch
    stretch_shadows: float = 0.0      # -100 (ombre aperte) .. 100 (neri più profondi)
    # base
    exposure: float = 0.0             # EV
    contrast: float = 0.0
    highlights: float = 0.0
    shadows: float = 0.0
    whites: float = 0.0
    blacks: float = 0.0
    # colore
    temperature: float = 0.0
    tint: float = 0.0
    vibrance: float = 0.0
    saturation: float = 0.0
    # astrofoto
    gradient_correction: float = 0.0   # 0..100, estrazione fondo robusta
    sky_neutralization: float = 0.0    # 0..100, neutralizzazione RGB del cielo
    star_protect: float = 0.0          # 0..100, protegge le stelle da dettaglio/NR
    # dettaglio
    clarity: float = 0.0
    dehaze: float = 0.0
    sharpen: float = 0.0              # 0..150
    sharpen_radius: float = 1.0       # px (a piena risoluzione)
    sharpen_masking: float = 30.0
    nr_luminance: float = 0.0
    nr_color: float = 0.0
    star_reduce: float = 0.0          # 0..100 riduzione delle stelle
    deconv: float = 0.0               # 0..100 deconvoluzione (Richardson-Lucy)
    deconv_radius: float = 1.6        # FWHM stimata in px
    wavelet_small: float = 0.0        # -100..100 dettaglio fine
    wavelet_medium: float = 0.0       # -100..100 dettaglio medio
    wavelet_large: float = 0.0        # -100..100 strutture grandi
    # HSL: 8 gamme (rosso, arancione, giallo, verde, acqua, blu, viola, magenta)
    hsl_h: list = field(default_factory=lambda: [0.0] * 8)
    hsl_s: list = field(default_factory=lambda: [0.0] * 8)
    hsl_l: list = field(default_factory=lambda: [0.0] * 8)
    # effetti
    vignette: float = 0.0
    grain: float = 0.0
    # geometria
    rotation: float = 0.0
    auto_crop_rotation: bool = True
    crop: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])   # % da sinistra, alto, destra, basso
    flip_h: bool = False
    flip_v: bool = False
    # curva dei toni: punti (x, y) in 0..1
    curve: list = field(default_factory=lambda: [[0.0, 0.0], [1.0, 1.0]])

    def is_default(self) -> bool:
        return asdict(self) == asdict(DevelopParams())

    def has_adjustments(self) -> bool:
        d = DevelopParams()
        for f in fields(self):
            if f.name in ("enabled", "stretch_bg", "stretch_shadows", "stretch_type"):
                continue
            if getattr(self, f.name) != getattr(d, f.name):
                return True
        return False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> "DevelopParams":
        data = json.loads(text)
        p = cls()
        for f in fields(cls):
            if f.name in data:
                setattr(p, f.name, data[f.name])
        if not isinstance(p.crop, list) or len(p.crop) != 4:
            p.crop = [0.0, 0.0, 0.0, 0.0]
        if not isinstance(p.curve, list) or len(p.curve) < 2:
            p.curve = [[0.0, 0.0], [1.0, 1.0]]
        for name in ("hsl_h", "hsl_s", "hsl_l"):
            v = getattr(p, name)
            if not isinstance(v, list) or len(v) != 8:
                setattr(p, name, [0.0] * 8)
        return p


# ----------------------------------------------------------------------------
# utilità
# ----------------------------------------------------------------------------
def _lum(img: np.ndarray) -> np.ndarray:
    return 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]


def _apply_lum_ratio(img: np.ndarray, L: np.ndarray, L2: np.ndarray) -> np.ndarray:
    ratio = np.clip(L2 / np.maximum(L, 1e-4), 0.0, 8.0)
    return img * ratio[:, :, None]


def _smoothstep(x):
    return x * x * (3.0 - 2.0 * x)


def curve_lut(points: list, n: int = 1024) -> np.ndarray:
    """Tabella della curva dei toni (monotona, liscia) da una lista di punti (x, y)."""
    pts = sorted((float(x), float(y)) for x, y in points)
    if len(pts) < 2:
        pts = [(0.0, 0.0), (1.0, 1.0)]
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    xs, idx = np.unique(xs, return_index=True)
    ys = ys[idx]
    grid = np.linspace(0.0, 1.0, n)
    if len(xs) >= 3:
        try:
            from scipy.interpolate import PchipInterpolator
            lut = PchipInterpolator(xs, ys, extrapolate=True)(grid)
        except Exception:
            lut = np.interp(grid, xs, ys)
    else:
        lut = np.interp(grid, xs, ys)
    return np.clip(lut, 0.0, 1.0).astype(np.float32)


def _curve_is_identity(points: list) -> bool:
    pts = sorted((float(x), float(y)) for x, y in points)
    return all(abs(x - y) < 1e-4 for x, y in pts)


# ----------------------------------------------------------------------------
# geometria
# ----------------------------------------------------------------------------
def _largest_rect_after_rotation(w: int, h: int, angle_deg: float) -> tuple[int, int]:
    a = np.radians(abs(angle_deg))
    sin, cos = np.sin(a), np.cos(a)
    if sin < 1e-6:
        return w, h
    k = min(w / (w * cos + h * sin), h / (w * sin + h * cos))
    return max(int(w * k), 8), max(int(h * k), 8)


def apply_geometry(img: np.ndarray, p: DevelopParams) -> np.ndarray:
    out = img
    if p.flip_h:
        out = out[:, ::-1]
    if p.flip_v:
        out = out[::-1]
    if abs(p.rotation) > 1e-3:
        h, w = out.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), float(p.rotation), 1.0)
        out = cv2.warpAffine(np.ascontiguousarray(out), M, (w, h), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        if p.auto_crop_rotation:
            wr, hr = _largest_rect_after_rotation(w, h, p.rotation)
            x0, y0 = (w - wr) // 2, (h - hr) // 2
            out = out[y0:y0 + hr, x0:x0 + wr]
    if p.crop and any(float(c) > 0 for c in p.crop):
        h, w = out.shape[:2]
        left, top, right, bottom = [max(0.0, min(45.0, float(c))) / 100.0 for c in p.crop]
        xa, ya = int(round(left * w)), int(round(top * h))
        xb, yb = w - int(round(right * w)), h - int(round(bottom * h))
        if xb - xa >= 8 and yb - ya >= 8:
            out = out[ya:yb, xa:xb]
    return np.ascontiguousarray(out, dtype=np.float32)


# ----------------------------------------------------------------------------
# sviluppo
# ----------------------------------------------------------------------------
def arcsinh_stretch(image: np.ndarray, target_bg: float = 0.25, shadows_clip: float = -2.8) -> np.ndarray:
    """Stretch arcsinh applicato alla luminanza: le stelle mantengono il colore invece di bruciarsi."""
    x = image.astype(np.float32, copy=False)
    if x.ndim == 2:
        x = x[:, :, None]
    L = _lum(x)
    sub = L[::4, ::4]
    med = float(np.median(sub))
    mad = 1.4826 * float(np.median(np.abs(sub - med))) + 1e-9
    c0 = min(max(med + shadows_clip * mad, 0.0), 0.99)
    Ln = np.clip((L - c0) / max(1.0 - c0, 1e-6), 0.0, None)
    m = max((med - c0) / max(1.0 - c0, 1e-6), 1e-6)
    # cerca il fattore a tale che asinh(a*m)/asinh(a) = target_bg
    lo, hi = 1.0, 1e6
    for _ in range(60):
        a = np.sqrt(lo * hi)
        v = np.arcsinh(a * m) / np.arcsinh(a)
        if v < target_bg:
            lo = a
        else:
            hi = a
    a = np.sqrt(lo * hi)
    L2 = np.arcsinh(a * Ln) / np.arcsinh(a)
    out = _apply_lum_ratio(np.clip((x - c0) / max(1.0 - c0, 1e-6), 0.0, None), Ln, L2)
    out = np.clip(out, 0.0, 1.0)
    return out[:, :, 0] if image.ndim == 2 else out


def masked_stretch(image: np.ndarray, target_bg: float = 0.25, shadows_clip: float = -2.8) -> np.ndarray:
    """Stretch adattivo: MTF sulle strutture deboli, arcsinh sulle alte luci/stelle.

    Il blend dipende dalla luminanza lineare, quindi protegge i nuclei stellari
    senza rinunciare al contrasto del fondo e delle nebulosità deboli.
    """
    mtf = auto_stretch(image, target_bg=target_bg, shadows_clip=shadows_clip)
    arc = arcsinh_stretch(image, target_bg=target_bg, shadows_clip=shadows_clip)
    src = image if image.ndim == 3 else image[:, :, None]
    L = _lum(src if src.shape[2] >= 3 else np.repeat(src, 3, axis=2))
    sub = L[::4, ::4]
    lo = float(np.percentile(sub, 50.0))
    hi = float(np.percentile(sub, 99.7))
    m = np.clip((L - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    m = _smoothstep(m) ** 0.65
    if mtf.ndim == 2:
        return (mtf * (1.0 - m) + arc * m).astype(np.float32)
    return (mtf * (1.0 - m[:, :, None]) + arc * m[:, :, None]).astype(np.float32)


def base_image(image: np.ndarray, p: DevelopParams, is_linear: bool) -> np.ndarray:
    """Immagine di partenza non lineare: stretch dei dati lineari, oppure l'immagine così com'è."""
    if is_linear:
        clip = -2.8 + 1.8 * (float(p.stretch_shadows) / 100.0)      # -4.6 .. -1.0 sigma
        bg = float(p.stretch_bg) / 100.0
        if p.stretch_type == "arcsinh":
            return arcsinh_stretch(image, target_bg=bg, shadows_clip=clip)
        if p.stretch_type == "hybrid":
            return np.clip(0.5 * auto_stretch(image, target_bg=bg, shadows_clip=clip)
                           + 0.5 * arcsinh_stretch(image, target_bg=bg, shadows_clip=clip), 0.0, 1.0)
        if p.stretch_type == "masked":
            return np.clip(masked_stretch(image, target_bg=bg, shadows_clip=clip), 0.0, 1.0)
        return auto_stretch(image, target_bg=bg, shadows_clip=clip)
    return np.clip(image.astype(np.float32, copy=False), 0.0, 1.0)


HSL_CENTERS = [0.0, 30.0, 60.0, 120.0, 180.0, 240.0, 275.0, 310.0]      # rosso .. magenta (gradi)
HSL_NAMES = ["Rosso", "Arancione", "Giallo", "Verde", "Acqua", "Blu", "Viola", "Magenta"]


def _hsl_weights(hue_deg: np.ndarray) -> list[np.ndarray]:
    ws = []
    for i, c in enumerate(HSL_CENTERS):
        prev = HSL_CENTERS[i - 1] if i > 0 else HSL_CENTERS[-1] - 360.0
        nxt = HSL_CENTERS[i + 1] if i < 7 else HSL_CENTERS[0] + 360.0
        d = (hue_deg - c + 180.0) % 360.0 - 180.0
        wl = max(c - prev, 1.0)
        wr = max(nxt - c, 1.0)
        w = np.where(d < 0, np.clip(1.0 + d / wl, 0.0, 1.0), np.clip(1.0 - d / wr, 0.0, 1.0))
        ws.append(w.astype(np.float32))
    return ws


def apply_hsl(x: np.ndarray, hsl_h: list, hsl_s: list, hsl_l: list) -> np.ndarray:
    """Tonalità / saturazione / luminanza per gamma di colore (stile Lightroom)."""
    if not (any(hsl_h) or any(hsl_s) or any(hsl_l)):
        return x
    hsv = cv2.cvtColor(np.clip(x, 0.0, 1.0), cv2.COLOR_RGB2HSV)      # H 0..360, S 0..1, V 0..1
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    ws = _hsl_weights(H)
    sat_w = np.clip(S * 3.0, 0.0, 1.0)              # i grigi non vengono toccati
    dh = np.zeros_like(H)
    gs = np.ones_like(S)
    gl = np.ones_like(V)
    for i in range(8):
        w = ws[i] * sat_w
        if hsl_h[i]:
            dh += w * (float(hsl_h[i]) / 100.0) * 30.0
        if hsl_s[i]:
            gs *= 1.0 + w * (float(hsl_s[i]) / 100.0)
        if hsl_l[i]:
            gl *= 1.0 + w * (float(hsl_l[i]) / 100.0) * 0.6
    hsv[:, :, 0] = (H + dh) % 360.0
    hsv[:, :, 1] = np.clip(S * gs, 0.0, 1.0)
    hsv[:, :, 2] = np.clip(V * gl, 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def reduce_stars(x: np.ndarray, amount: float, px: float) -> np.ndarray:
    """Rimpicciolisce le stelle: erosione morbida applicata solo dove ci sono strutture piccole e brillanti."""
    if amount <= 0:
        return x
    k = float(amount) / 100.0
    L = np.clip(_lum(x), 0.0, 1.0)
    r_big = max(3, int(round(12 * px)) | 1)
    bg = cv2.morphologyEx(L, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r_big, r_big)))
    tophat = np.clip(L - bg, 0.0, 1.0)                    # strutture più piccole di r_big: le stelle
    sub = tophat[::4, ::4]
    noise = 1.4826 * float(np.median(np.abs(sub - np.median(sub)))) + 1e-6
    thr = max(4.0 * noise, 0.02)                          # sopra il rumore: solo vere stelle
    starmask = np.clip((tophat - thr) / thr, 0.0, 1.0)
    starmask = cv2.dilate(starmask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    starmask = cv2.GaussianBlur(starmask, (0, 0), max(0.6, 1.5 * px))
    # erosione più forte al crescere della quantità: il nucleo si restringe davvero
    r_er = max(3, int(round((2.0 + 6.0 * k) * px)) | 1)
    eroded = cv2.erode(L, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r_er, r_er)))
    eroded = cv2.GaussianBlur(eroded, (0, 0), max(0.6, 1.0 * px))
    L2 = L - min(1.0, 0.4 + 0.6 * k) * starmask * (L - eroded)
    return _apply_lum_ratio(x, L, np.maximum(L2, 0.0))


def make_star_mask(x: np.ndarray, px: float = 1.0) -> np.ndarray:
    """Maschera morbida 0..1 delle stelle, riusata dalla protezione dettaglio/rumore."""
    L = np.clip(_lum(x), 0.0, 1.0)
    r_big = max(3, int(round(12 * px)) | 1)
    bg = cv2.morphologyEx(L, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r_big, r_big)))
    tophat = np.clip(L - bg, 0.0, 1.0)
    sub = tophat[::4, ::4]
    noise = 1.4826 * float(np.median(np.abs(sub - np.median(sub)))) + 1e-6
    thr = max(4.0 * noise, 0.015)
    mask = np.clip((tophat - thr) / max(2.5 * thr, 1e-6), 0.0, 1.0)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    return cv2.GaussianBlur(mask, (0, 0), max(0.6, 1.5 * px)).astype(np.float32)


def _protect_stars(processed: np.ndarray, original: np.ndarray, mask: np.ndarray | None, amount: float) -> np.ndarray:
    if mask is None or amount <= 0:
        return processed
    a = np.clip(mask * (amount / 100.0), 0.0, 1.0)[:, :, None]
    return processed * (1.0 - a) + original * a


def develop(image: np.ndarray, p: DevelopParams, is_linear: bool = True, scale: float = 1.0) -> np.ndarray:
    """Applica stretch + tutte le regolazioni. `scale` = larghezza di questa immagine / larghezza originale."""
    source = image.astype(np.float32, copy=False)
    if p.gradient_correction:
        try:
            from .gradient import remove_gradient
            corrected, _ = remove_gradient(source, degree=2, force=True)
            a = float(np.clip(p.gradient_correction / 100.0, 0.0, 1.0))
            source = source * (1.0 - a) + corrected * a
        except Exception:
            pass
    if p.sky_neutralization and source.ndim == 3 and source.shape[2] == 3:
        try:
            from .gradient import neutralize_background
            neutral = neutralize_background(source)
            a = float(np.clip(p.sky_neutralization / 100.0, 0.0, 1.0))
            source = source * (1.0 - a) + neutral * a
        except Exception:
            pass
    x = base_image(source, p, is_linear)
    if x.ndim == 2:
        x = np.repeat(x[:, :, None], 3, axis=2)
    if not p.enabled:
        return np.ascontiguousarray(x)
    x = apply_geometry(x, p).copy()
    h, w = x.shape[:2]
    px = max(float(scale), 0.05)             # 1 px dell'originale = px pixel qui
    star_mask = make_star_mask(np.clip(x, 0.0, 1.0), px) if p.star_protect > 0 else None

    # --- colore: temperatura e tinta
    if p.temperature or p.tint:
        t = p.temperature / 100.0
        ti = p.tint / 100.0
        mult = np.array([1.0 + 0.45 * t, 1.0 - 0.25 * ti, 1.0 - 0.45 * t], np.float32)
        mult /= float(mult.mean())
        x *= mult[None, None, :]

    # --- esposizione
    if p.exposure:
        x *= float(2.0 ** p.exposure)

    # --- tono (in luminanza, conservando i rapporti di colore)
    L = np.clip(_lum(x), 0.0, 4.0)
    Lc = np.clip(L, 0.0, 1.0)
    L2 = L.copy()
    if p.blacks:
        b = p.blacks / 100.0
        if b < 0:
            k = 0.2 * (-b)
            L2 = (L2 - k) / (1.0 - k)
        else:
            L2 = L2 + 0.15 * b * (1.0 - Lc)
    if p.whites:
        wv = p.whites / 100.0
        L2 = L2 + 0.35 * wv * Lc * Lc if wv > 0 else L2 * (1.0 + 0.3 * wv * Lc)
    if p.shadows:
        s = p.shadows / 100.0
        wgt = np.clip((0.5 - Lc) / 0.5, 0, 1) ** 1.5
        L2 = L2 + 0.25 * s * wgt * np.sqrt(Lc)
    if p.highlights:
        hl = p.highlights / 100.0
        wgt = np.clip((Lc - 0.5) / 0.5, 0, 1) ** 1.5
        L2 = L2 + 0.35 * hl * wgt * (1.0 - Lc)
    if p.contrast:
        c = p.contrast / 100.0
        t = np.clip(L2, 0.0, 1.0)
        L2 = t + c * (_smoothstep(t) - t) + np.maximum(L2 - 1.0, 0.0)
    if not _curve_is_identity(p.curve):
        lut = curve_lut(p.curve)
        t = np.clip(L2, 0.0, 1.0)
        L2 = lut[np.minimum((t * (len(lut) - 1)).astype(np.int32), len(lut) - 1)] + np.maximum(L2 - 1.0, 0.0)
    L2 = np.maximum(L2, 0.0)
    x = _apply_lum_ratio(x, L, L2)

    # --- chiarezza e velatura
    if p.clarity or p.dehaze:
        L = np.clip(_lum(x), 0.0, 4.0)
        Lc = np.clip(L, 0.0, 1.0)
        L2 = L.copy()
        if p.clarity:
            sig = max(1.0, 0.012 * max(h, w))
            blur = cv2.GaussianBlur(Lc, (0, 0), sig)
            mid = 1.0 - np.abs(2.0 * Lc - 1.0)
            L2 = L2 + (p.clarity / 100.0) * 0.6 * (Lc - blur) * (0.3 + 0.7 * mid)
        if p.dehaze:
            sig = max(2.0, 0.06 * max(h, w))
            veil = cv2.GaussianBlur(Lc, (0, 0), sig)
            d = p.dehaze / 100.0
            L2 = L2 - 0.5 * d * (veil - float(np.median(veil))) + 0.15 * d * (Lc - veil)
        L2 = np.maximum(L2, 0.0)
        x = _apply_lum_ratio(x, L, L2)

    # --- vividezza e saturazione
    if p.vibrance or p.saturation:
        L = _lum(x)[:, :, None]
        chroma = x - L
        mx = x.max(axis=2)
        mn = x.min(axis=2)
        sat = np.clip((mx - mn) / np.maximum(mx, 1e-4), 0.0, 1.0)
        gain = np.full((h, w), 1.0 + p.saturation / 100.0, np.float32)
        if p.vibrance:
            v = p.vibrance / 100.0
            gain = gain * (1.0 + v * (1.0 - sat))
        x = L + chroma * gain[:, :, None]

    # --- HSL per gamma di colore
    x = apply_hsl(x, p.hsl_h, p.hsl_s, p.hsl_l)

    # --- deconvoluzione e wavelet
    if p.deconv:
        before = x
        x = deconvolve(np.clip(x, 0.0, 1.0), p.deconv, p.deconv_radius, px)
        x = _protect_stars(x, before, star_mask, p.star_protect)
    if p.wavelet_small or p.wavelet_medium or p.wavelet_large:
        before = x
        x = wavelets(np.clip(x, 0.0, 1.0), p.wavelet_small, p.wavelet_medium, p.wavelet_large, px)
        x = _protect_stars(x, before, star_mask, p.star_protect)

    # --- riduzione delle stelle
    if p.star_reduce:
        x = reduce_stars(np.clip(x, 0.0, 1.0), p.star_reduce, px)

    # --- riduzione del rumore
    if p.nr_luminance or p.nr_color:
        before_nr = x.copy() if star_mask is not None else None
        L = np.clip(_lum(x), 0.0, 4.0)
        chroma = x - L[:, :, None]
        if p.nr_luminance:
            nl = p.nr_luminance / 100.0
            d = max(3, min(int(round(5 * px)) | 1, 9))
            Ls = cv2.bilateralFilter(np.ascontiguousarray(L), d, 0.02 + 0.12 * nl, max(1.0, 2.0 * px))
            L = L + nl * (Ls - L)
        if p.nr_color:
            nc = p.nr_color / 100.0
            chroma = cv2.GaussianBlur(chroma, (0, 0), max(0.6, (1.0 + 6.0 * nc) * px))
        x = L[:, :, None] + chroma
        if before_nr is not None:
            x = _protect_stars(x, before_nr, star_mask, p.star_protect)

    # --- nitidezza (maschera di contrasto sulla luminanza)
    if p.sharpen:
        before_sharp = x.copy() if star_mask is not None else None
        L = np.clip(_lum(x), 0.0, 4.0)
        r = max(0.4, float(p.sharpen_radius) * px)
        detail = L - cv2.GaussianBlur(L, (0, 0), r)
        if p.sharpen_masking:
            edge = np.abs(cv2.GaussianBlur(detail, (0, 0), max(0.8, 1.5 * px)))
            thr = (p.sharpen_masking / 100.0) * 0.03
            detail = detail * np.clip(edge / max(thr, 1e-6), 0.0, 1.0)
        L2 = np.maximum(L + (p.sharpen / 100.0) * detail, 0.0)
        x = _apply_lum_ratio(x, L, L2)
        if before_sharp is not None:
            x = _protect_stars(x, before_sharp, star_mask, p.star_protect)

    # --- effetti
    if p.vignette:
        v = p.vignette / 100.0
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        rr = np.clip((((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2) / 2.0, 0, 1)
        f = 1.0 + 0.7 * v * rr * rr if v < 0 else 1.0 + 0.5 * v * rr
        x *= f[:, :, None]
    if p.grain:
        g = p.grain / 100.0
        rng = np.random.default_rng(12345)
        noise = rng.normal(0.0, 0.04 * g, (h, w)).astype(np.float32)
        if px < 1.0:
            noise *= float(np.sqrt(px))
        x += noise[:, :, None]

    np.clip(x, 0.0, 1.0, out=x)
    return np.ascontiguousarray(x, dtype=np.float32)


def histogram(img: np.ndarray, bins: int = 128) -> np.ndarray:
    """Istogrammi RGB (3, bins) normalizzati (scala radice) dell'immagine 0..1."""
    sub = img[::4, ::4] if img.shape[0] * img.shape[1] > 400_000 else img
    out = np.zeros((3, bins), np.float32)
    for c in range(3):
        hist, _ = np.histogram(np.clip(sub[:, :, c], 0, 1), bins=bins, range=(0.0, 1.0))
        out[c] = hist
    out = np.sqrt(out)
    m = out.max()
    return out / m if m > 0 else out


def auto_tone(image: np.ndarray, p: DevelopParams, is_linear: bool = True) -> DevelopParams:
    """Regola Neri e Bianchi perché l'istogramma usi tutta la gamma senza tagliare."""
    q = DevelopParams.from_json(p.to_json())
    q.blacks, q.whites = 0.0, 0.0
    dev = develop(image, q, is_linear, scale=1.0)
    L = _lum(dev)
    lo, hi = float(np.percentile(L, 0.3)), float(np.percentile(L, 99.5))   # 99.5: ignora le stelle sature
    if lo > 0.02:
        k = (lo - 0.015) / max(1.0 - 0.015, 1e-6)
        q.blacks = float(np.clip(-k / 0.2, -100.0, 0.0))
    if 0.05 < hi < 0.97:
        q.whites = float(np.clip((0.97 - hi) / (0.35 * hi * hi), 0.0, 100.0))
    elif hi > 0.995:
        q.whites = float(np.clip((0.97 / hi - 1.0) / (0.3 * hi), -100.0, 0.0))
    return q


def assisted_develop(image: np.ndarray, p: DevelopParams, is_linear: bool = True) -> tuple[DevelopParams, dict]:
    """Costruisce una ricetta di sviluppo prudente e completamente modificabile.

    Non usa un modello opaco: misura fondo, rumore, saturazione cromatica e
    stelle, poi compila i normali parametri del pannello. Restituisce anche un
    piccolo report per spiegare cosa è stato scelto.
    """
    q = DevelopParams.from_json(p.to_json())
    report: dict[str, float | int | str | bool] = {}

    # Stretch protetto sulle immagini lineari.
    if is_linear:
        q.stretch_type = "masked"
        q.stretch_bg = 22.0
        q.stretch_shadows = 8.0

    src = image.astype(np.float32, copy=False)
    # Analisi del gradiente sul dato di partenza: se è significativo lo propone
    # nell'editor, ma con forza moderata per non mangiare nebulose estese.
    try:
        from .gradient import fit_background
        _model, gi = fit_background(src, degree=2, grid=(10, 14))
        report["gradient_strength"] = float(gi.strength)
        report["gradient_detected"] = bool(gi.detected)
        if gi.detected:
            q.gradient_correction = float(np.clip(55.0 + gi.strength * 80.0, 55.0, 90.0))
            q.sky_neutralization = 70.0
    except Exception:
        pass

    base = base_image(src, q, is_linear)
    if base.ndim == 2:
        base = np.repeat(base[:, :, None], 3, axis=2)
    L = np.clip(_lum(base), 0.0, 1.0)
    sub = L[::4, ::4]
    hp = sub - cv2.GaussianBlur(np.ascontiguousarray(sub, np.float32), (0, 0), 1.2)
    noise = 1.4826 * float(np.median(np.abs(hp - np.median(hp)))) + 1e-9
    lo, med, hi = [float(v) for v in np.percentile(sub, [1.0, 50.0, 99.5])]
    dyn = max(hi - lo, 1e-6)
    report.update({"noise": noise, "median": med, "dynamic_range": dyn})

    # Denoise proporzionato al rumore, mantenendo le stelle protette.
    q.nr_luminance = float(np.clip(8.0 + noise * 1300.0, 8.0, 48.0))
    q.nr_color = float(np.clip(q.nr_luminance * 0.72, 6.0, 38.0))
    q.star_protect = 72.0

    # Contrasto locale/dettaglio: conservativo sui dati rumorosi.
    snr_like = dyn / max(noise, 1e-6)
    q.clarity = float(np.clip(8.0 + np.log10(max(snr_like, 1.0)) * 5.0, 8.0, 22.0))
    q.dehaze = 7.0 if med < 0.45 else 4.0
    q.wavelet_small = 4.0 if noise < 0.02 else 0.0
    q.wavelet_medium = 8.0
    q.wavelet_large = 3.0

    # Colore: aumenta soprattutto le immagini poco sature, evitando l'effetto neon.
    mx, mn = base.max(axis=2), base.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    sat_med = float(np.median(sat[::4, ::4]))
    report["median_saturation"] = sat_med
    q.vibrance = float(np.clip(28.0 - 45.0 * sat_med, 8.0, 24.0))
    q.saturation = 3.0 if sat_med < 0.25 else 0.0

    # Stelle: stima FWHM e densità per sharpening/riduzione stelle.
    try:
        from .stars import detect_stars
        sf = detect_stars(src if is_linear else base, max_stars=300, sigma=4.5)
        report["stars"] = int(sf.n_detected)
        report["fwhm"] = float(sf.fwhm)
        if sf.fwhm > 0:
            q.sharpen_radius = float(np.clip(sf.fwhm / 2.8, 0.8, 2.4))
            q.sharpen = float(np.clip(20.0 - noise * 220.0, 8.0, 20.0))
        density = sf.n_detected / max(base.shape[0] * base.shape[1] / 1_000_000.0, 0.1)
        q.star_reduce = float(np.clip((density - 80.0) / 18.0, 0.0, 24.0))
    except Exception:
        pass

    # Chiude la ricetta con neri/bianchi robusti sul risultato proposto.
    q = auto_tone(image, q, is_linear=is_linear)
    return q, report


# ----------------------------------------------------------------------------
# esportazione
# ----------------------------------------------------------------------------
@dataclass
class ExportOptions:
    fmt: str = "tif16"                # tif16 | tif8 | png16 | png8 | jpg | fits
    quality: int = 92                 # JPG
    png_level: int = 6                # PNG 0..9
    tiff_compression: str = "zlib"    # zlib | none
    scale_mode: str = "original"      # original | percent | width
    scale_percent: float = 100.0
    width_px: int = 0
    upscale_method: str = "lanczos"   # lanczos | cubic | linear
    output_sharpen: str = "none"      # none | low | standard | high
    apply_develop: bool = True
    preset: str = "custom"            # custom | instagram | web | print_a3 | wallpaper
    author: str = ""
    copyright: str = ""
    watermark: str = ""               # testo stampato in basso a destra
    watermark_size: float = 2.2       # % dell'altezza


EXPORT_PRESETS = {
    # nome: (formato, larghezza px, qualita, nitidezza)
    "instagram": ("jpg", 1440, 92, "standard"),
    "web": ("jpg", 2048, 90, "low"),
    "print_a3": ("tif16", 4961, 100, "low"),
    "wallpaper": ("jpg", 3840, 94, "standard"),
}


def apply_preset(opt: "ExportOptions", name: str) -> "ExportOptions":
    if name not in EXPORT_PRESETS:
        return opt
    fmt, width, quality, sharp = EXPORT_PRESETS[name]
    opt.fmt, opt.quality, opt.output_sharpen = fmt, quality, sharp
    opt.scale_mode, opt.width_px = "width", width
    opt.preset = name
    return opt


EXT_FOR_FMT = {"tif16": ".tif", "tif8": ".tif", "png16": ".png", "png8": ".png", "jpg": ".jpg", "fits": ".fits"}
_INTERP = {"lanczos": cv2.INTER_LANCZOS4, "cubic": cv2.INTER_CUBIC, "linear": cv2.INTER_LINEAR}


def target_size(w: int, h: int, opt: ExportOptions) -> tuple[int, int]:
    if opt.scale_mode == "percent":
        s = max(float(opt.scale_percent), 1.0) / 100.0
        return max(int(round(w * s)), 8), max(int(round(h * s)), 8)
    if opt.scale_mode == "width" and opt.width_px:
        nw = max(int(opt.width_px), 8)
        return nw, max(int(round(h * nw / max(w, 1))), 8)
    return w, h


def resize_for_export(img: np.ndarray, opt: ExportOptions) -> np.ndarray:
    h, w = img.shape[:2]
    nw, nh = target_size(w, h, opt)
    if (nw, nh) == (w, h):
        return img
    if nw > w:
        interp = _INTERP.get(opt.upscale_method, cv2.INTER_LANCZOS4)
        out = cv2.resize(np.ascontiguousarray(img), (nw, nh), interpolation=interp)
        return np.clip(out, 0.0, 1.0).astype(np.float32)
    return np.ascontiguousarray(cv2.resize(np.ascontiguousarray(img), (nw, nh), interpolation=cv2.INTER_AREA))


def output_sharpen(img: np.ndarray, level: str = "none") -> np.ndarray:
    amount = {"low": 0.35, "standard": 0.7, "high": 1.1}.get(level, 0.0)
    if amount <= 0 or img.ndim != 3:
        return img
    L = np.clip(_lum(img), 0.0, 1.0)
    detail = L - cv2.GaussianBlur(L, (0, 0), 0.8)
    L2 = np.maximum(L + amount * detail, 0.0)
    return np.clip(_apply_lum_ratio(img, L, L2), 0.0, 1.0).astype(np.float32)


def add_watermark(img: np.ndarray, text: str, size_pct: float = 2.2, opacity: float = 0.55) -> np.ndarray:
    """Scrive una firma in basso a destra."""
    if not text:
        return img
    out = np.ascontiguousarray(img, dtype=np.float32)
    h, w = out.shape[:2]
    scale = max(0.4, (size_pct / 100.0) * h / 22.0)
    thick = max(1, int(round(scale * 1.6)))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x, y = w - tw - int(0.02 * w), h - int(0.02 * h)
    layer = np.zeros((h, w), np.float32)
    cv2.putText(layer, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, 1.0, thick, cv2.LINE_AA)
    layer = cv2.GaussianBlur(layer, (0, 0), 0.6)
    if out.ndim == 2:
        out = np.repeat(out[:, :, None], 3, axis=2)
    dark = float(np.median(out[max(0, y - th * 2):h, max(0, x - 10):w])) < 0.5
    col = 1.0 if dark else 0.0
    out = out * (1 - opacity * layer[:, :, None]) + col * opacity * layer[:, :, None]
    return np.clip(out, 0.0, 1.0)


def export_image(path: str, img: np.ndarray, opt: ExportOptions, metadata: Optional[dict] = None):
    """Scrive il file nel formato scelto. `img` è già sviluppata (0..1) tranne per FITS (lineare)."""
    meta = dict(metadata or {})
    meta["SOFTWARE"] = "AstroStack"
    if opt.author:
        meta["AUTHOR"] = opt.author
    if opt.copyright:
        meta["COPYRIGHT"] = opt.copyright
    fmt = opt.fmt
    if opt.watermark and fmt != "fits":
        img = add_watermark(img, opt.watermark, opt.watermark_size)
    if fmt == "fits":
        from .io_out import save_fits
        save_fits(path, img, meta)
        return
    img = np.clip(np.ascontiguousarray(img, dtype=np.float32), 0.0, 1.0)
    if fmt in ("tif16", "tif8"):
        import tifffile
        data = (np.clip(img * 65535.0 + 0.5, 0, 65535).astype(np.uint16) if fmt == "tif16"
                else (img * 255.0 + 0.5).astype(np.uint8))
        comp = None if opt.tiff_compression == "none" else "zlib"
        tifffile.imwrite(path, data, photometric="rgb" if data.ndim == 3 else "minisblack",
                         compression=comp, metadata={k: str(v) for k, v in meta.items()})
        return
    if fmt in ("png16", "png8"):
        data = (np.clip(img * 65535.0 + 0.5, 0, 65535).astype(np.uint16) if fmt == "png16"
                else (img * 255.0 + 0.5).astype(np.uint8))
        if data.ndim == 3:
            data = np.ascontiguousarray(data[:, :, ::-1])
        ok, buf = cv2.imencode(".png", data, [cv2.IMWRITE_PNG_COMPRESSION, int(np.clip(opt.png_level, 0, 9))])
        if not ok:
            raise IOError("Errore nella codifica PNG")
        buf.tofile(path)
        return
    if fmt == "jpg":
        data = (img * 255.0 + 0.5).astype(np.uint8)
        if data.ndim == 3:
            data = np.ascontiguousarray(data[:, :, ::-1])
        ok, buf = cv2.imencode(".jpg", data, [cv2.IMWRITE_JPEG_QUALITY, int(np.clip(opt.quality, 1, 100))])
        if not ok:
            raise IOError("Errore nella codifica JPG")
        buf.tofile(path)
        return
    raise ValueError(f"Formato non supportato: {fmt}")


# ----------------------------------------------------------------------------
# maschera delle stelle, deconvoluzione, wavelet
# ----------------------------------------------------------------------------
def star_mask(img: np.ndarray, px: float = 1.0, threshold: float = 4.0) -> np.ndarray:
    """Maschera 0..1 delle stelle (strutture piccole e brillanti)."""
    L = np.clip(_lum(img) if img.ndim == 3 else img, 0.0, 1.0)
    r = max(3, int(round(12 * px)) | 1)
    bg = cv2.morphologyEx(L, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r)))
    top = np.clip(L - bg, 0.0, 1.0)
    sub = top[::4, ::4]
    noise = 1.4826 * float(np.median(np.abs(sub - np.median(sub)))) + 1e-6
    thr = max(threshold * noise, 0.02)
    m = np.clip((top - thr) / thr, 0.0, 1.0)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    return cv2.GaussianBlur(m, (0, 0), max(0.6, 1.5 * px)).astype(np.float32)


def deconvolve(x: np.ndarray, amount: float, fwhm_px: float, px: float = 1.0, iters: int = 12) -> np.ndarray:
    """Richardson-Lucy sulla luminanza, applicata solo sulle stelle e sui dettagli (il fondo resta liscio)."""
    if amount <= 0:
        return x
    k = float(amount) / 100.0
    L = np.clip(_lum(x), 1e-4, 1.0)
    sigma = max(0.5, float(fwhm_px) * px / 2.3548)
    est = L.copy()
    for _ in range(max(3, int(round(iters * (0.4 + 0.6 * k))))):
        conv = cv2.GaussianBlur(est, (0, 0), sigma) + 1e-6
        est = est * cv2.GaussianBlur(L / conv, (0, 0), sigma)
        np.clip(est, 0.0, 4.0, out=est)
    mask = np.clip(star_mask(x, px) + np.clip((L - np.median(L)) * 4.0, 0.0, 1.0), 0.0, 1.0)
    L2 = L + k * mask * (est - L)
    return _apply_lum_ratio(x, L, np.maximum(L2, 0.0))


def wavelets(x: np.ndarray, small: float, medium: float, large: float, px: float = 1.0) -> np.ndarray:
    """Tre livelli "à trous": esalta o attenua dettaglio fine, medio e strutture grandi."""
    if not (small or medium or large):
        return x
    L = np.clip(_lum(x), 0.0, 4.0)
    sigmas = [max(0.6, 1.0 * px), max(1.2, 2.5 * px), max(2.5, 6.0 * px)]
    b1 = cv2.GaussianBlur(L, (0, 0), sigmas[0])
    b2 = cv2.GaussianBlur(b1, (0, 0), sigmas[1])
    b3 = cv2.GaussianBlur(b2, (0, 0), sigmas[2])
    d1, d2, d3 = L - b1, b1 - b2, b2 - b3
    L2 = b3 + d1 * (1 + small / 100.0) + d2 * (1 + medium / 100.0) + d3 * (1 + large / 100.0)
    return _apply_lum_ratio(x, L, np.maximum(L2, 0.0))
