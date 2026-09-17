"""Test end-to-end con dati sintetici (nessuna fotocamera necessaria).

Genera light/dark/flat/bias FITS con mosaico Bayer RGGB, trasformazioni note,
hot pixel, vignettatura e gradiente di inquinamento luminoso; poi esegue la
pipeline e verifica allineamento, rimozione hot pixel e gradiente.

Uso:  python tests/synthetic_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from astropy.io import fits  # noqa: E402

from astrostack.core.pipeline import Callbacks, Pipeline, Settings  # noqa: E402
from astrostack.core.stars import detect_stars  # noqa: E402

RNG = np.random.default_rng(42)
H, W = 900, 1300
N_LIGHTS, N_DARKS, N_FLATS, N_BIAS = 12, 6, 6, 6
SIGMA_PSF = 1.4
BIAS_LEVEL = 0.03
SKY = 0.08


def render_stars(xy, flux, colors, h, w):
    """Immagine RGB float con stelle gaussiane."""
    img = np.zeros((h, w, 3), np.float32)
    r = int(4 * SIGMA_PSF) + 2
    for (x, y), f, col in zip(xy, flux, colors):
        xi, yi = int(round(x)), int(round(y))
        x0, x1 = max(0, xi - r), min(w, xi + r + 1)
        y0, y1 = max(0, yi - r), min(h, yi + r + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        g = np.exp(-((xs - x) ** 2 + (ys - y) ** 2) / (2 * SIGMA_PSF ** 2))
        g *= f / (2 * np.pi * SIGMA_PSF ** 2)
        img[y0:y1, x0:x1] += g[:, :, None] * col[None, None, :]
    return img


def similarity(theta_deg, dx, dy, cx, cy):
    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    A = np.array([[c, -s], [s, c]])
    tvec = np.array([cx, cy]) - A @ np.array([cx, cy]) + np.array([dx, dy])
    return A, tvec


def mosaic_rggb(rgb):
    m = np.empty(rgb.shape[:2], np.float32)
    m[0::2, 0::2] = rgb[0::2, 0::2, 0]
    m[0::2, 1::2] = rgb[0::2, 1::2, 1]
    m[1::2, 0::2] = rgb[1::2, 0::2, 1]
    m[1::2, 1::2] = rgb[1::2, 1::2, 2]
    return m


def save_fits(path, img01, exposure):
    u16 = np.clip(img01 * 65535, 0, 65535).astype(np.uint16)
    hdu = fits.PrimaryHDU(u16)
    hdu.header["BAYERPAT"] = "RGGB"
    hdu.header["EXPTIME"] = exposure
    hdu.header["INSTRUME"] = "SyntheticCam"
    hdu.writeto(path, overwrite=True)


def main():
    tmp = tempfile.mkdtemp(prefix="astrostack_test_")
    print("Cartella test:", tmp)
    n_stars = 140
    xy = np.stack([RNG.uniform(20, W - 20, n_stars), RNG.uniform(20, H - 20, n_stars)], axis=1)
    flux = 10 ** RNG.uniform(-0.3, 1.8, n_stars)
    colors = RNG.uniform(0.6, 1.0, (n_stars, 3))
    yy, xx = np.mgrid[0:H, 0:W]
    vignette = 1.0 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    hot = RNG.random((H, W)) < 0.0008          # ~0.08 % pixel caldi
    hot_val = RNG.uniform(0.2, 0.9, (H, W)).astype(np.float32)
    gradient = 0.06 * (xx / W) + 0.03 * (yy / H)   # inquinamento luminoso
    skyline = (0.80 + 0.04 * np.sin(xx / 37.0) + 0.02 * np.sin(xx / 11.0)) * H   # alberi in basso
    foreground = yy > skyline

    truths = []
    lights = []
    for i in range(N_LIGHTS):
        theta = RNG.uniform(-1.5, 1.5) if i else 0.0
        dx, dy = (RNG.uniform(-35, 35), RNG.uniform(-35, 35)) if i else (0.0, 0.0)
        A, t = similarity(theta, dx, dy, W / 2, H / 2)
        pts = xy @ A.T + t
        rgb = render_stars(pts, flux * RNG.uniform(0.9, 1.1), colors, H, W)
        rgb[foreground] = 0.0                          # niente stelle dietro gli alberi
        sky = SKY + gradient
        rgb += sky[:, :, None] * np.array([0.9, 1.0, 1.1])[None, None, :]
        rgb *= vignette[:, :, None]
        rgb[foreground] *= 0.15                       # alberi / orizzonte in basso a sinistra
        rgb *= np.array([0.55, 1.0, 0.75])[None, None, :]   # sensibilità del sensore (dominante verde)
        m = mosaic_rggb(rgb) + BIAS_LEVEL
        m += RNG.normal(0, 0.004, m.shape)
        m[hot] = hot_val[hot]
        p = os.path.join(tmp, f"light_{i:02d}.fits")
        save_fits(p, m, 120.0)
        lights.append(p)
        truths.append((theta, dx, dy))
    darks, flats, biases = [], [], []
    for i in range(N_DARKS):
        m = np.full((H, W), BIAS_LEVEL, np.float32) + RNG.normal(0, 0.004, (H, W))
        m[hot] = hot_val[hot]
        p = os.path.join(tmp, f"dark_{i:02d}.fits"); save_fits(p, m, 120.0); darks.append(p)
    for i in range(N_FLATS):
        m = mosaic_rggb(np.repeat((0.5 * vignette)[:, :, None], 3, axis=2)) + BIAS_LEVEL
        m += RNG.normal(0, 0.003, m.shape)
        p = os.path.join(tmp, f"flat_{i:02d}.fits"); save_fits(p, m, 1.0); flats.append(p)
    for i in range(N_BIAS):
        m = np.full((H, W), BIAS_LEVEL, np.float32) + RNG.normal(0, 0.003, (H, W))
        p = os.path.join(tmp, f"bias_{i:02d}.fits"); save_fits(p, m, 0.001); biases.append(p)

    class CB(Callbacks):
        def on_log(self, msg): print("  LOG:", msg)
        def on_progress(self, step, done, total, msg=""):
            if done == total: print(f"  [{step}] {done}/{total}")

    settings = Settings(workers=2, cache_dir=tmp, max_band_mb=200, gradient_degree=2)
    t0 = time.time()
    res = Pipeline(lights, darks, flats, biases, settings, CB()).run()
    print(f"Pipeline: {time.time() - t0:.1f} s, frame usati {res.n_used}/{N_LIGHTS}")

    # --- verifica trasformazioni
    ref_idx = next(i for i, f in enumerate(res.frames) if f.is_reference)
    th_r, dx_r, dy_r = truths[ref_idx]
    A_r, t_r = similarity(th_r, dx_r, dy_r, W / 2, H / 2)
    errs = []
    for f, (th, dx, dy) in zip(res.frames, truths):
        if f.transform is None or f.status != "ok":
            continue
        A_f, t_f = similarity(th, dx, dy, W / 2, H / 2)
        # frame -> mondo -> riferimento
        A_exp = A_r @ np.linalg.inv(A_f)
        t_exp = t_r - A_exp @ t_f
        M = f.transform.M
        pts = np.array([[0, 0], [W, 0], [0, H], [W, H]], float)
        p_exp = pts @ A_exp.T + t_exp
        p_got = pts @ M[:, :2].T + M[:, 2]
        errs.append(np.abs(p_exp - p_got).max())
    print(f"Errore massimo di allineamento ai bordi: {max(errs):.3f} px (media {np.mean(errs):.3f})")
    assert max(errs) < 0.6, "allineamento impreciso"

    # --- verifica risultato
    img = res.linear
    x0, y0, x1, y1 = res.crop
    hot_c = hot[y0:y1, x0:x1]
    lum = img.mean(axis=2)
    med = np.median(lum)
    mad = 1.4826 * np.median(np.abs(lum - med))
    hot_residual = np.mean(lum[hot_c] > med + 6 * mad)
    print(f"Hot pixel residui: {hot_residual * 100:.2f} % (soglia 6 sigma)")
    assert hot_residual < 0.02
    sf = detect_stars(img)
    print(f"Stelle nello stack: {sf.n_detected}, FWHM {sf.fwhm:.2f} px (atteso ~{2.355 * SIGMA_PSF:.2f}), ecc {sf.eccentricity:.2f}")
    assert sf.fwhm < 2.355 * SIGMA_PSF * 1.35
    g = res.gradient
    print("Gradiente:", g.describe(), "applicato:", g.applied)
    from astrostack.core.gradient import fit_background
    _, g2 = fit_background(res.image, 2)
    print(f"Gradiente residuo dopo la correzione: {g2.strength * 100:.2f} % del fondo")
    assert g2.strength < g.strength * 0.3
    # --- colori: le stelle (in media bianche) devono tornare bianche nonostante la dominante del sensore
    from astrostack.core.gradient import color_calibrate_on_stars, background_levels
    _, mult, nst = color_calibrate_on_stars(res.image)
    bgl = background_levels(res.image)
    print(f"Colori: moltiplicatori applicati R×{res.gradient.color_mult[0]:.2f} B×{res.gradient.color_mult[2]:.2f} "
          f"su {res.gradient.color_stars} stelle; residuo R×{mult[0]:.2f} B×{mult[2]:.2f}; fondo {np.round(bgl, 4)}")
    assert abs(mult[0] - 1) < 0.1 and abs(mult[2] - 1) < 0.1, "calibrazione colore imprecisa"
    assert np.ptp(bgl) < 0.02 * bgl.mean(), "fondo non neutro"
    # --- paesaggio: primo piano nitido
    res_n = Pipeline(lights, darks, flats, biases, Settings(workers=2, cache_dir=tmp, auto_crop=False), CB()).run()
    res_l = Pipeline(lights, darks, flats, biases, Settings(workers=2, cache_dir=tmp, auto_crop=False, landscape=True), CB()).run()
    from astrostack.core.foreground import foreground_mask
    mask, minfo = foreground_mask(res_l.linear)
    truth = foreground
    m = (mask > 0.5) if mask is not None else np.zeros_like(truth)
    iou = float((m & truth).sum() / max((m | truth).sum(), 1))
    import cv2
    edge = (cv2.dilate(truth.astype(np.uint8), np.ones((7, 7), np.uint8)) - cv2.erode(truth.astype(np.uint8), np.ones((7, 7), np.uint8))) > 0
    def sharp(im):
        l = im.mean(axis=2)
        return float((np.abs(cv2.Sobel(l, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(l, cv2.CV_32F, 0, 1)))[edge].mean())
    s0, s1 = sharp(res_n.linear), sharp(res_l.linear)
    print(f"Paesaggio: maschera IoU {iou:.2f}, nitidezza del bordo alberi {s0:.4f} → {s1:.4f}")
    assert iou > 0.7, "primo piano non riconosciuto"
    assert s1 > s0 * 1.3, "primo piano non più nitido"
    print("\nTUTTI I TEST SUPERATI")


if __name__ == "__main__":
    main()
