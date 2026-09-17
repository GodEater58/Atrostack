"""Regressione Assistito 1.4: paesaggio + gradiente forte."""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from astrostack.core import gradient
from astrostack.core.develop import (
    DevelopParams,
    _lum,
    assisted_develop,
    develop,
)


def _synthetic_scene() -> np.ndarray:
    h, w = 260, 420

    yy, xx = np.mgrid[0:h, 0:w]

    # Cielo lineare con gradiente molto forte.
    sky = (
        0.018
        + 0.055 * (xx / max(w - 1, 1))
        + 0.020 * (yy / max(h - 1, 1))
    ).astype(np.float32)

    img = np.dstack(
        (
            sky * 1.04,
            sky,
            sky * 0.96,
        )
    )

    # Stelle.
    rng = np.random.default_rng(42)
    for _ in range(140):
        x = int(rng.integers(5, w - 5))
        y = int(rng.integers(5, int(h * 0.68)))
        value = float(rng.uniform(0.12, 0.55))
        img[y - 1:y + 2, x - 1:x + 2] += value

    # Primo piano scuro: deve restare scuro senza far chiudere anche il cielo.
    horizon = int(h * 0.72)
    img[horizon:, :, :] *= 0.08

    # Sagoma nera limitata.
    img[int(h * 0.80):, :int(w * 0.24), :] = 0.001

    return np.clip(img, 0.0, 1.0).astype(np.float32)


def main() -> int:
    scene = _synthetic_scene()

    original_fit = gradient.fit_background

    try:
        def fake_fit_background(img, degree=2, grid=(16, 24)):
            info = gradient.GradientInfo(
                detected=True,
                strength=2.30,
                snr=50.0,
                degree=degree,
                n_samples=100,
            )
            model = np.zeros_like(img, dtype=np.float32)
            return model, info

        gradient.fit_background = fake_fit_background

        params, report = assisted_develop(
            scene,
            DevelopParams(),
            is_linear=True,
        )

    finally:
        gradient.fit_background = original_fit

    assert report.get("gradient_reliable") is False
    assert params.gradient_correction <= 5.0
    assert params.sky_neutralization <= 20.0
    assert params.stretch_shadows < 0.0
    assert params.blacks >= -2.01

    result = develop(
        scene,
        params,
        is_linear=True,
        scale=1.0,
    )

    lum = _lum(result)

    # Il primo piano può essere una silhouette; ciò che non deve accadere
    # è trasformare gran parte del cielo in nero puro.
    sky_lum = lum[: int(lum.shape[0] * 0.70)]

    assert float(np.mean(sky_lum < 0.015)) < 0.10
    assert float(np.median(sky_lum)) > 0.08

    print("ASTROSTACK_140_ASSISTED_SHADOW_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
