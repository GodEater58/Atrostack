"""Inquinamento luminoso: rilevamento e rimozione del gradiente di fondo cielo.

Il fondo viene campionato su una griglia con statistiche robuste (le stelle e
le nebulose vengono escluse), poi si adatta un polinomio 2D che viene sottratto
dall'immagine mantenendo il livello medio del fondo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .loader import luminance


@dataclass
class GradientInfo:
    detected: bool = False
    strength: float = 0.0          # ampiezza picco-picco del gradiente / fondo (0.10 = 10 %)
    snr: float = 0.0               # ampiezza / rumore del fondo
    degree: int = 2
    n_samples: int = 0
    per_channel: list = field(default_factory=list)
    applied: bool = False
    color_mult: tuple = ()          # moltiplicatori (R, G, B) della calibrazione sulle stelle
    color_stars: int = 0

    def describe_color(self) -> str:
        if not self.color_mult:
            return ""
        r, _g, b = self.color_mult
        return f"Colori calibrati su {self.color_stars} stelle (R ×{r:.2f}, B ×{b:.2f})"

    def describe(self) -> str:
        if not self.detected:
            return f"Gradiente trascurabile ({self.strength * 100:.1f} % del fondo)"
        return f"Gradiente rilevato: {self.strength * 100:.1f} % del fondo (S/N {self.snr:.0f})"


def _poly_terms(x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    cols = []
    for i in range(degree + 1):
        for j in range(degree + 1 - i):
            cols.append((x ** i) * (y ** j))
    return np.stack(cols, axis=-1)


def sample_background(img: np.ndarray, grid: tuple[int, int] = (16, 24)):
    """Campioni robusti del fondo: coordinate normalizzate (-1..1), valori (n, C), pesi."""
    H, W = img.shape[:2]
    C = 1 if img.ndim == 2 else img.shape[2]
    ny, nx = grid
    ty, tx = H / ny, W / nx
    coords, values, weights = [], [], []
    for j in range(ny):
        for i in range(nx):
            y0, y1 = int(j * ty), int((j + 1) * ty)
            x0, x1 = int(i * tx), int((i + 1) * tx)
            tile = img[y0:y1, x0:x1].reshape(-1, C) if img.ndim == 3 else img[y0:y1, x0:x1].reshape(-1, 1)
            if tile.shape[0] < 50:
                continue
            lum = tile.mean(axis=1)
            m = np.median(lum)
            s = 1.4826 * np.median(np.abs(lum - m)) + 1e-9
            sel = lum < m + 1.5 * s
            for _ in range(2):
                if sel.sum() < 20:
                    break
                m = np.median(lum[sel])
                s = 1.4826 * np.median(np.abs(lum[sel] - m)) + 1e-9
                sel = lum < m + 1.5 * s
            if sel.sum() < 20:
                continue
            vals = np.median(tile[sel], axis=0)
            coords.append(((x0 + x1) / W - 1.0, (y0 + y1) / H - 1.0))
            values.append(vals)
            weights.append(1.0)
    return np.asarray(coords, np.float64), np.asarray(values, np.float64), np.asarray(weights, np.float64)


def fit_background(img: np.ndarray, degree: int = 2, grid: tuple[int, int] = (16, 24)):
    """Modello polinomiale del fondo (H, W, C) e informazioni sul gradiente."""
    coords, values, weights = sample_background(img, grid)
    info = GradientInfo(degree=degree, n_samples=int(len(coords)))
    H, W = img.shape[:2]
    C = 1 if img.ndim == 2 else img.shape[2]
    if len(coords) < 12:
        return None, info
    x, y = coords[:, 0], coords[:, 1]
    lum_v = values.mean(axis=1)
    # 1) piano robusto (rigetto iterativo su entrambi i lati): esclude nebulose e
    #    galassie (campioni troppo luminosi) ma anche alberi, orizzonte, primo
    #    piano (campioni troppo scuri) che altrimenti deformano il modello
    # stadio 0: rigetto grossolano rispetto al livello mediano (toglie subito un
    # primo piano esteso, che altrimenti "tira" il piano verso di sé)
    med0 = np.median(lum_v)
    mad0 = 1.4826 * np.median(np.abs(lum_v - med0)) + 1e-9
    keep = np.abs(lum_v - med0) < 3.0 * mad0
    if keep.sum() < 10:
        keep = np.ones(len(x), bool)
    A1 = _poly_terms(x, y, 1)
    for _ in range(4):
        if keep.sum() < 10:
            break
        coef1, *_ = np.linalg.lstsq(A1[keep], lum_v[keep], rcond=None)
        res = lum_v - A1 @ coef1
        med = np.median(res[keep])
        mad = 1.4826 * np.median(np.abs(res[keep] - med)) + 1e-9
        new_keep = np.abs(res - med) < 2.5 * mad      # riammette i campioni buoni esclusi allo stadio 0
        if new_keep.sum() < 10 or np.array_equal(new_keep, keep):
            keep = new_keep if new_keep.sum() >= 10 else keep
            break
        keep = new_keep
    info.n_samples = int(keep.sum())
    x, y, values = x[keep], y[keep], values[keep]
    deg = degree
    while (deg + 1) * (deg + 2) // 2 > max(6, len(x) // 2) and deg > 1:
        deg -= 1
    A = _poly_terms(x, y, deg)
    # 2) fit del grado richiesto, con un ultimo rigetto sui residui
    lum_k = values.mean(axis=1)
    cf, *_ = np.linalg.lstsq(A, lum_k, rcond=None)
    res = lum_k - A @ cf
    mad = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-9
    ok = np.abs(res - np.median(res)) < 3.0 * mad
    if ok.sum() >= max(10, A.shape[1] + 3):
        A, values = A[ok], values[ok]
    coefs = []
    for c in range(C):
        cf, *_ = np.linalg.lstsq(A, values[:, c], rcond=None)
        coefs.append(cf)
    # valuta su una griglia ridotta e ingrandisce (il polinomio è liscio)
    gh, gw = max(2, H // 16), max(2, W // 16)
    gy, gx = np.mgrid[0:gh, 0:gw]
    gxn = (gx + 0.5) / gw * 2 - 1
    gyn = (gy + 0.5) / gh * 2 - 1
    T = _poly_terms(gxn.ravel(), gyn.ravel(), deg)
    import cv2
    model = np.empty((H, W, C), np.float32)
    per_channel = []
    noise = 0.0
    for c in range(C):
        small = (T @ coefs[c]).reshape(gh, gw).astype(np.float32)
        model[:, :, c] = cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC)
        p2p = float(small.max() - small.min())
        per_channel.append(p2p)
    bg_level = float(np.median(values))
    info.per_channel = per_channel
    info.strength = float(max(per_channel) / max(bg_level, 1e-6))
    info.degree = deg
    # rumore del fondo (per il rapporto segnale/rumore del gradiente)
    lum = np.ascontiguousarray(luminance(img[::4, ::4]), np.float32)
    hp = lum - cv2.medianBlur(lum, 5)            # rumore pixel-a-pixel, senza gradiente
    noise = 1.4826 * float(np.median(np.abs(hp - np.median(hp)))) + 1e-9
    info.snr = float(max(per_channel) / noise)
    info.detected = info.strength > 0.02 and info.snr > 3.0
    return model, info


def remove_gradient(img: np.ndarray, degree: int = 2, force: bool = False):
    """Rimuove il gradiente solo quando il modello è abbastanza affidabile."""
    model, info = fit_background(img, degree)

    if model is None or (not info.detected and not force):
        return img, info

    # Un gradiente enorme è spesso causato da orizzonte, alberi,
    # edifici o primo piano scambiati per fondo cielo.
    #
    # In automatico è meglio NON alterare l'immagine.
    if info.strength > 1.25 and not force:
        info.applied = False
        return img, info

    out = img.astype(np.float32, copy=True)

    if out.ndim == 2:
        out = out[:, :, None]

    pedestal = np.median(
        model.reshape(-1, model.shape[2]),
        axis=0,
    )

    out -= model
    out += pedestal[None, None, :]

    info.applied = True

    if img.ndim == 2:
        out = out[:, :, 0]

    return out, info

def neutralize_background(img: np.ndarray) -> np.ndarray:
    """Porta il fondo cielo allo stesso livello nei tre canali (rimuove la dominante)."""
    if img.ndim != 3 or img.shape[2] != 3:
        return img
    out = img.astype(np.float32, copy=True)
    sub = out[::8, ::8].reshape(-1, 3)
    lum = sub.mean(axis=1)
    m = np.median(lum)
    s = 1.4826 * np.median(np.abs(lum - m)) + 1e-9
    sel = lum < m + 1.5 * s
    meds = np.median(sub[sel], axis=0) if sel.sum() > 100 else np.median(sub, axis=0)
    target = float(meds.mean())
    for c in range(3):
        out[:, :, c] += target - meds[c]
    return out


def background_levels(img: np.ndarray) -> np.ndarray:
    """Mediana per canale del fondo cielo (zone scure, senza stelle)."""
    sub = img[::8, ::8].reshape(-1, img.shape[2])
    lum = sub.mean(axis=1)
    m = np.median(lum)
    s = 1.4826 * np.median(np.abs(lum - m)) + 1e-9
    sel = lum < m + 1.5 * s
    return np.median(sub[sel], axis=0) if sel.sum() > 100 else np.median(sub, axis=0)


def color_calibrate_on_stars(
    img: np.ndarray,
    max_stars: int = 300,
    sat_level: float = 0.9,
):
    """Calibrazione cromatica stellare conservativa.

    Il RAW ha già ricevuto un white balance. Questa funzione deve quindi
    rifinire il colore, non reinventarlo.
    """
    from .stars import detect_stars

    if img.ndim != 3 or img.shape[2] != 3:
        return img, (1.0, 1.0, 1.0), 0

    sf = detect_stars(
        img,
        max_stars=max_stars,
    )

    bg = background_levels(img)
    H, W = img.shape[:2]

    r_in = 5
    r_out = 9
    ratios = []

    for x, y in sf.xy:
        xi = int(round(x))
        yi = int(round(y))

        if (
            xi - r_out < 0
            or yi - r_out < 0
            or xi + r_out + 1 > W
            or yi + r_out + 1 > H
        ):
            continue

        box = img[
            yi - r_out : yi + r_out + 1,
            xi - r_out : xi + r_out + 1,
        ]

        if float(box.max()) >= sat_level:
            continue

        ys, xs = np.mgrid[
            -r_out : r_out + 1,
            -r_out : r_out + 1,
        ]

        d2 = xs * xs + ys * ys

        inner = d2 <= r_in * r_in

        ring = (
            (d2 > (r_in + 1) ** 2)
            & (d2 <= r_out * r_out)
        )

        local_bg = np.median(
            box[ring].reshape(-1, 3),
            axis=0,
        )

        flux = (
            box[inner].reshape(-1, 3)
            - local_bg
        ).sum(axis=0)

        if (
            flux[0] <= 0
            or flux[1] <= 0
            or flux[2] <= 0
        ):
            continue

        ratios.append(
            (
                flux[0] / flux[1],
                flux[2] / flux[1],
            )
        )

    # Con poche stelle la misura non è abbastanza affidabile.
    if len(ratios) < 20:
        return img, (1.0, 1.0, 1.0), len(ratios)

    ratios = np.asarray(
        ratios,
        dtype=np.float64,
    )

    # Lavoriamo in log: è più corretto per rapporti cromatici.
    log_r = np.log(
        np.clip(ratios[:, 0], 1e-4, None)
    )
    log_b = np.log(
        np.clip(ratios[:, 1], 1e-4, None)
    )

    med_r = np.median(log_r)
    med_b = np.median(log_b)

    mad_r = (
        1.4826
        * np.median(np.abs(log_r - med_r))
        + 1e-9
    )

    mad_b = (
        1.4826
        * np.median(np.abs(log_b - med_b))
        + 1e-9
    )

    good = (
        (np.abs(log_r - med_r) < 2.5 * mad_r)
        & (np.abs(log_b - med_b) < 2.5 * mad_b)
    )

    if int(good.sum()) < 15:
        return img, (1.0, 1.0, 1.0), int(good.sum())

    mr = float(
        np.exp(np.median(log_r[good]))
    )

    mb = float(
        np.exp(np.median(log_b[good]))
    )

    raw_r = 1.0 / max(mr, 1e-6)
    raw_b = 1.0 / max(mb, 1e-6)

    # Se servirebbe una correzione enorme, la misura non è affidabile.
    if not (
        0.60 <= raw_r <= 1.65
        and 0.60 <= raw_b <= 1.65
    ):
        return img, (1.0, 1.0, 1.0), int(good.sum())

    # Il RAW è già bilanciato: applichiamo solo una rifinitura.
    strength = 0.35

    r_mult = 1.0 + strength * (raw_r - 1.0)
    b_mult = 1.0 + strength * (raw_b - 1.0)

    # Limite duro: Auto stelle non può più produrre B ×1.78.
    r_mult = float(
        np.clip(r_mult, 0.82, 1.18)
    )

    b_mult = float(
        np.clip(b_mult, 0.82, 1.18)
    )

    mult = (
        r_mult,
        1.0,
        b_mult,
    )

    out = img.astype(
        np.float32,
        copy=True,
    )

    pedestal = float(bg.mean())

    for c in range(3):
        out[:, :, c] = (
            (out[:, :, c] - bg[c])
            * mult[c]
            + pedestal
        )

    return out, mult, int(good.sum())