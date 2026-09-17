"""Regressioni: Live incrementale e Ricombina con Drizzle 2x.

Eseguibile senza RAW/FITS: usa piccoli TIFF sintetici.
"""
from __future__ import annotations

import os
import sys
import tempfile

import cv2
import numpy as np
import tifffile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from astrostack.core.pipeline import Pipeline, Settings, extend_live_stack, restack


def make_session(folder: str, size: int = 192) -> list[str]:
    rng = np.random.default_rng(4)
    h = w = size
    yy, xx = np.mgrid[:h, :w]
    base = np.full((h, w, 3), 0.015, np.float32)
    for _ in range(55):
        x = float(rng.uniform(12, w - 12))
        y = float(rng.uniform(12, h - 12))
        amp = float(rng.uniform(0.25, 0.9))
        sigma = float(rng.uniform(0.8, 1.5))
        g = amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma * sigma))
        base += g[..., None] * np.array([1.0, 0.92, 0.82], np.float32)
    base = np.clip(base, 0, 1)

    paths = []
    for i, (dx, dy) in enumerate(((0, 0), (2, -1), (-2, 2), (3, 1))):
        mat = np.array([[1, 0, dx], [0, 1, dy]], np.float32)
        image = cv2.warpAffine(base, mat, (w, h), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0.015,) * 3)
        image = np.clip(image + rng.normal(0, 0.0015, image.shape).astype(np.float32), 0, 1)
        path = os.path.join(folder, f"light_{i}.tif")
        tifffile.imwrite(path, (image * 65535).astype(np.uint16), photometric="rgb")
        paths.append(path)
    return paths


def main() -> None:
    folder = tempfile.mkdtemp(prefix="astrostack_regression_")
    paths = make_session(folder)
    settings = Settings(workers=1, auto_reject=False, gradient_removal=False, neutralize=False,
                        star_color=False, auto_crop=False, master_library=False, keep_cache=True,
                        method="media", drizzle=1)

    result = Pipeline(paths[:3], [], [], [], settings).run()
    assert result.n_used == 3
    assert result.cache is not None and result.masters is not None

    result = extend_live_stack(result, [paths[3]], settings)
    assert len(result.frames) == 4
    assert any(os.path.basename(f.path) == "light_3.tif" and f.transform is not None
               for f in result.frames if f.status == "ok")

    drizzle = Settings(**{**settings.__dict__, "drizzle": 2})
    result = restack(result, drizzle)
    assert result.drizzle == 2
    assert result.shape[:2] == (384, 384)
    assert result.image.shape[:2] == (384, 384)
    result.cleanup()
    print("OK: Live incrementale + Ricombina Drizzle 2x")


if __name__ == "__main__":
    main()
