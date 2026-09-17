"""Progetto .astrostack: file, impostazioni, sviluppo, livelli e maschere, riapribile in un secondo momento."""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np

VERSION = 2


def _masks_dir(project_path: str) -> str:
    root, _ = os.path.splitext(project_path)
    return root + "_dati"


def save_project(path: str, zones: dict, settings: dict, layers: list, base_linear: Optional[np.ndarray],
                 base_is_linear: bool, opened_path: Optional[str], annotations: list,
                 ui_state: Optional[dict] = None) -> None:
    """layers: lista di Layer (il livello 0 è la base). Il livello base viene salvato in FITS accanto al progetto."""
    from .io_out import save_fits
    import cv2
    d = _masks_dir(path)
    os.makedirs(d, exist_ok=True)
    data = {"version": VERSION, "zones": zones, "settings": settings, "opened_path": opened_path,
            "annotations": annotations, "base_is_linear": base_is_linear, "layers": []}
    data["ui_state"] = dict(ui_state or {})
    if base_linear is not None:
        base_file = os.path.join(d, "base.fits")
        save_fits(base_file, base_linear, {"SOFTWARE": "AstroStack"})
        data["base_file"] = os.path.relpath(base_file, os.path.dirname(path))
    for i, lay in enumerate(layers):
        item = {"name": lay.name, "is_linear": lay.is_linear, "params": json.loads(lay.params.to_json()),
                "visible": lay.visible, "opacity": lay.opacity, "blend": lay.blend, "offset_x": lay.offset_x,
                "offset_y": lay.offset_y, "scale": lay.scale, "mask_type": lay.mask_type, "mask_invert": lay.mask_invert,
                "mask_feather": lay.mask_feather, "grad_start": lay.grad_start, "grad_end": lay.grad_end,
                "grad_horizontal": lay.grad_horizontal, "lum_low": lay.lum_low, "lum_high": lay.lum_high,
                "source": getattr(lay, "source_path", None)}
        # Salviamo SEMPRE una copia dei livelli aggiuntivi. In precedenza i
        # livelli provenienti da file esterni conservavano solo il path della
        # sorgente: spostando/eliminando quel file il progetto non era più
        # autosufficiente e non si ricostruiva correttamente alla riapertura.
        if i > 0:
            f = os.path.join(d, f"layer_{i}.fits")
            save_fits(f, lay.image, {})
            item["image_file"] = os.path.relpath(f, os.path.dirname(path))
        for kind, arr in (("brush", lay.brush_mask), ("file", lay.file_mask)):
            if arr is not None:
                f = os.path.join(d, f"layer_{i}_{kind}.png")
                ok, buf = cv2.imencode(".png", (np.clip(arr, 0, 1) * 65535).astype(np.uint16))
                if ok:
                    buf.tofile(f)
                    item[kind + "_mask_file"] = os.path.relpath(f, os.path.dirname(path))
        data["layers"].append(item)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def load_project(path: str) -> dict:
    """Restituisce il dizionario del progetto con le immagini già caricate (base, livelli, maschere)."""
    import cv2
    from .develop import DevelopParams
    from .layers import Layer
    from .loader import load_frame
    base_dir = os.path.dirname(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    out = {"zones": data.get("zones", {}), "settings": data.get("settings", {}), "opened_path": data.get("opened_path"),
           "annotations": data.get("annotations", []), "base_is_linear": data.get("base_is_linear", True),
           "ui_state": data.get("ui_state", {}), "base": None, "layers": [], "missing": []}
    if data.get("base_file"):
        bf = os.path.join(base_dir, data["base_file"])
        if os.path.isfile(bf):
            out["base"] = np.ascontiguousarray(load_frame(bf).data[:, :, :3], dtype=np.float32)
        else:
            out["missing"].append(bf)

    def _load_gray(rel):
        f = os.path.join(base_dir, rel)
        if not os.path.isfile(f):
            out["missing"].append(f)
            return None
        img = cv2.imdecode(np.fromfile(f, np.uint8), cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        return img.astype(np.float32) / (65535.0 if img.dtype == np.uint16 else 255.0)

    for i, item in enumerate(data.get("layers", [])):
        img = None
        if i == 0:
            img = out["base"]
        elif item.get("image_file"):
            f = os.path.join(base_dir, item["image_file"])
            if os.path.isfile(f):
                img = np.ascontiguousarray(load_frame(f).data[:, :, :3], dtype=np.float32)
            else:
                out["missing"].append(f)
        elif item.get("source") and os.path.isfile(item["source"]):
            fr = load_frame(item["source"])
            img = fr.data
            if img.ndim == 2:
                img = np.repeat(img[:, :, None], 3, axis=2)
            img = np.ascontiguousarray(img[:, :, :3], dtype=np.float32)
        if img is None:
            if i > 0:
                out["missing"].append(item.get("source") or item.get("name", f"livello {i}"))
            continue
        lay = Layer(item.get("name", f"Livello {i + 1}"), img, is_linear=bool(item.get("is_linear", False)),
                    params=DevelopParams.from_json(json.dumps(item.get("params", {}))),
                    visible=item.get("visible", True), opacity=item.get("opacity", 100.0), blend=item.get("blend", "normal"),
                    offset_x=item.get("offset_x", 0.0), offset_y=item.get("offset_y", 0.0), scale=item.get("scale", 100.0),
                    mask_type=item.get("mask_type", "none"), mask_invert=item.get("mask_invert", False),
                    mask_feather=item.get("mask_feather", 0.0), grad_start=item.get("grad_start", 40.0),
                    grad_end=item.get("grad_end", 60.0), grad_horizontal=item.get("grad_horizontal", False),
                    lum_low=item.get("lum_low", 20.0), lum_high=item.get("lum_high", 60.0))
        lay.source_path = item.get("source")
        if item.get("brush_mask_file"):
            lay.brush_mask = _load_gray(item["brush_mask_file"])
        if item.get("file_mask_file"):
            lay.file_mask = _load_gray(item["file_mask_file"])
        out["layers"].append(lay)
    return out
