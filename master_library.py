"""Libreria dei master dark / bias: salvati per fotocamera, ISO e posa, riusati in automatico."""
from __future__ import annotations

import glob
import json
import os
import re
import time
from typing import Optional

import numpy as np


def default_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "AstroStack", "master")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-") or "camera"


class MasterLibrary:
    def __init__(self, directory: Optional[str] = None):
        self.dir = directory or default_dir()
        os.makedirs(self.dir, exist_ok=True)

    # ------------------------------------------------------------------ salva
    def store(self, kind: str, master: np.ndarray, info: dict, sample_path: str = "") -> Optional[str]:
        """Salva il master (FITS float32) con i metadati in un .json accanto."""
        from .loader import quick_meta
        exif = quick_meta(sample_path) if sample_path else {}
        camera = exif.get("camera") or info.get("camera") or ""
        if not camera:
            return None
        meta = {"kind": kind, "camera": camera, "iso": exif.get("iso"), "exposure": info.get("exposure") or exif.get("exposure"),
                "n": info.get("n", 0), "shape": list(master.shape), "is_bayer": bool(info.get("is_bayer")),
                "pattern": info.get("pattern"), "date": time.strftime("%Y-%m-%d %H:%M")}
        exp = meta["exposure"]
        name = f"{kind}_{_slug(camera)}_iso{meta['iso'] or 0}_{(f'{exp:g}s' if exp else 'x')}_{master.shape[1]}x{master.shape[0]}"
        path = os.path.join(self.dir, name + ".fits")
        try:
            from astropy.io import fits
            hdu = fits.PrimaryHDU(master.astype(np.float32))
            hdu.header["MSTRKIND"] = kind
            hdu.writeto(path, overwrite=True)
            meta["file"] = os.path.basename(path)
            with open(os.path.join(self.dir, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=1)
            return path
        except Exception:
            return None

    # ------------------------------------------------------------------ cerca
    def find(self, kind: str, light_meta: dict) -> Optional[tuple[np.ndarray, dict]]:
        """Master compatibile con i light (stessa fotocamera; per i dark anche ISO e posa entro il 25 %)."""
        camera = light_meta.get("camera")
        if not camera:
            return None
        best, best_score = None, None
        for jf in glob.glob(os.path.join(self.dir, f"{kind}_*.json")):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                continue
            if meta.get("camera") != camera:
                continue
            score = 0.0
            iso_l, iso_m = light_meta.get("iso"), meta.get("iso")
            if iso_l and iso_m and int(iso_l) != int(iso_m):
                continue
            if kind == "dark":
                el, em = light_meta.get("exposure"), meta.get("exposure")
                if el and em:
                    r = float(el) / float(em)
                    if not (0.75 <= r <= 1.33):
                        continue
                    score = abs(np.log(r))
            if best_score is None or score < best_score:
                best, best_score = meta, score
        if best is None:
            return None
        path = os.path.join(self.dir, best.get("file", ""))
        if not os.path.isfile(path):
            return None
        try:
            from astropy.io import fits
            with fits.open(path, memmap=False) as h:
                data = np.asarray(h[0].data, dtype=np.float32)
        except Exception:
            return None
        return data, best
