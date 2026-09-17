"""Regressioni AstroStack 1.2: sviluppo assistito + linear-fit clipping."""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from astrostack.core.develop import DevelopParams, assisted_develop, develop  # noqa: E402
from astrostack.core.stacking import StackOptions, combine  # noqa: E402


def synthetic_astro() -> np.ndarray:
    h, w = 240, 320
    y, x = np.mgrid[0:h, 0:w]
    base = 0.03 + 0.035 * (x / w) + 0.018 * (y / h)
    img = np.repeat(base[..., None], 3, axis=2).astype(np.float32)
    rng = np.random.default_rng(42)
    for _ in range(90):
        cx, cy = rng.integers(8, w - 8), rng.integers(8, h - 8)
        amp, sig = rng.uniform(0.08, 0.6), rng.uniform(0.7, 1.5)
        star = (amp * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sig * sig))).astype(np.float32)
        img += star[..., None] * np.array([1.0, 0.93, 0.86], np.float32)
    neb = 0.035 * np.exp(-(((x - 190) / 65) ** 2 + ((y - 120) / 50) ** 2)).astype(np.float32)
    img += neb[..., None] * np.array([1.0, 0.35, 0.25], np.float32)
    img += rng.normal(0, 0.003, img.shape).astype(np.float32)
    return np.clip(img, 0, 1)


def test_editor():
    img = synthetic_astro()
    q, report = assisted_develop(img, DevelopParams(), is_linear=True)
    assert q.stretch_type == "masked"
    assert q.star_protect > 0
    out = develop(img, q, is_linear=True)
    assert out.shape == img.shape
    assert np.isfinite(out).all()
    assert 0.0 <= float(out.min()) <= float(out.max()) <= 1.0
    assert "noise" in report


def test_linearfit():
    ref = np.full((32, 32, 3), 0.2, np.float32)
    ref[8:24, 8:24] += 0.15
    cube = np.stack([ref, ref * 1.12 + 0.03, ref * 0.9 - 0.015, ref.copy(), ref.copy()], axis=0)
    cube[4, 15, 15, :] = 1.0
    cov = np.ones((5, 32, 32), bool)
    res = combine(cube, cov, np.ones(5, np.float32),
                  StackOptions(method="linearfit", iterations=2, kappa_low=2.5, kappa_high=2.5))
    assert np.isfinite(res).all()
    assert abs(float(res[15, 15, 0]) - float(ref[15, 15, 0])) < 0.08


if __name__ == "__main__":
    test_editor()
    test_linearfit()
    print("OK: Editor assistito + Masked Stretch + Linear-fit clipping")
