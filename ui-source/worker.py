"""Thread di lavoro: la pipeline gira fuori dal thread della GUI."""
from __future__ import annotations

import threading
import traceback

import numpy as np
from PySide6.QtCore import QThread, Signal

from ..core.pipeline import Callbacks, Cancelled, FrameInfo, Pipeline, Settings, StackResult, postprocess
from ..core.stretch import to_uint8


class StackWorker(QThread):
    progress = Signal(str, int, int, str)
    preview = Signal(object, str)          # np.uint8 RGB, testo
    frame = Signal(object)                 # FrameInfo
    log = Signal(str)
    finished_ok = Signal(object)           # StackResult
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, lights, darks, flats, bias, settings: Settings, parent=None):
        super().__init__(parent)
        self.args = (lights, darks, flats, bias)
        self.settings = settings
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        w = self

        class CB(Callbacks):
            def on_progress(self, step, done, total, msg=""):
                w.progress.emit(step, int(done), int(total), str(msg))

            def on_preview(self, rgb8, text=""):
                w.preview.emit(np.ascontiguousarray(rgb8), str(text))

            def on_frame(self, info: FrameInfo):
                w.frame.emit(info)

            def on_log(self, msg):
                w.log.emit(str(msg))

        try:
            pipe = Pipeline(*self.args, self.settings, CB(), self.cancel_event)
            res = pipe.run()
            self.finished_ok.emit(res)
        except Cancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{e}\n\n{traceback.format_exc(limit=3)}")


class PostWorker(QThread):
    """Riapplica gradiente/neutralizzazione e prepara l'anteprima (senza ri-stackare)."""
    done = Signal(object, object, object)   # image float32, gradient info, preview uint8
    failed = Signal(str)

    def __init__(self, linear: np.ndarray, settings: Settings, preview_max: int = 2200, parent=None):
        super().__init__(parent)
        self.linear = linear
        self.settings = settings
        self.preview_max = preview_max

    def run(self):
        try:
            image, ginfo = postprocess(self.linear, self.settings)
            self.done.emit(image, ginfo, render_preview(image, self.preview_max, True))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class RenderWorker(QThread):
    """Rendering dell'anteprima (stretch o lineare) a una certa dimensione."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, image: np.ndarray, max_dim: int, stretch: bool, parent=None):
        super().__init__(parent)
        self.image, self.max_dim, self.stretch = image, max_dim, stretch

    def run(self):
        try:
            self.done.emit(render_preview(self.image, self.max_dim, self.stretch))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


def render_preview(image: np.ndarray, max_dim: int, stretch: bool) -> np.ndarray:
    import cv2
    h, w = image.shape[:2]
    f = 1
    while max(h, w) / f > max_dim:
        f *= 2
    small = image if f == 1 else cv2.resize(image, (w // f, h // f), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(to_uint8(small, stretch=stretch))


class ToolWorker(QThread):
    """Esegue una funzione (strumento IA) fuori dal thread della GUI."""
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(self.log.emit))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class DevelopWorker(QThread):
    """Applica lo sviluppo (anteprima ridotta o piena risoluzione)."""
    done = Signal(object, object)      # rgb8, istogramma
    before_ready = Signal(object)      # rgb8 senza regolazioni (confronto prima/dopo)
    failed = Signal(str)

    def __init__(self, image: np.ndarray, params, is_linear: bool, scale: float = 1.0, compare: bool = False, parent=None):
        super().__init__(parent)
        self.image, self.params, self.is_linear, self.scale, self.compare = image, params, is_linear, scale, compare

    def run(self):
        try:
            from ..core.develop import DevelopParams, develop, histogram
            out = develop(self.image, self.params, self.is_linear, scale=self.scale)
            if self.compare:
                q = DevelopParams.from_json(self.params.to_json())
                q.enabled = False
                before = develop(self.image, q, self.is_linear, scale=self.scale)
                self.before_ready.emit(np.ascontiguousarray(to_uint8(before, stretch=False)))
            self.done.emit(np.ascontiguousarray(to_uint8(out, stretch=False)), histogram(out))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class ExportWorker(QThread):
    """Sviluppo a piena risoluzione + ridimensionamento + scrittura del file."""
    done = Signal(str)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, path: str, image: np.ndarray, params, is_linear: bool, options, metadata: dict,
                 stars_image=None, render_fn=None, parent=None):
        super().__init__(parent)
        self.path, self.image, self.params, self.is_linear = path, image, params, is_linear
        self.options, self.metadata, self.stars_image = options, metadata, stars_image
        self.render_fn = render_fn          # con i livelli: funzione che restituisce la composizione piena

    def run(self):
        try:
            import os
            from ..core.develop import DevelopParams, develop, export_image, output_sharpen, resize_for_export
            from ..core.stretch import auto_stretch
            opt = self.options
            if opt.fmt == "fits":
                img = self.image
            else:
                self.progress.emit("Sviluppo a piena risoluzione…")
                if self.render_fn is not None:
                    img = self.render_fn()
                elif opt.apply_develop:
                    img = develop(self.image, self.params, self.is_linear)
                else:
                    img = auto_stretch(self.image) if self.is_linear else np.clip(self.image, 0, 1)
                self.progress.emit("Ridimensionamento…")
                img = resize_for_export(img, opt)
                img = output_sharpen(img, opt.output_sharpen)
            self.progress.emit("Scrittura del file…")
            export_image(self.path, img, opt, self.metadata)
            extra = ""
            if self.stars_image is not None and opt.fmt != "fits":
                root, ext = os.path.splitext(self.path)
                st = resize_for_export(np.clip(self.stars_image, 0, 1), opt)
                export_image(root + "_stelle" + ext, st, opt, self.metadata)
                extra = root + "_stelle" + ext
            self.done.emit(extra)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class CompositeWorker(QThread):
    """Composizione dei livelli (anteprima) fuori dal thread della GUI."""
    done = Signal(object, object)      # rgb8, istogramma
    failed = Signal(str)

    def __init__(self, layers, proxies, show_mask_of=None, parent=None):
        super().__init__(parent)
        self.layers, self.proxies, self.show_mask_of = layers, proxies, show_mask_of

    def run(self):
        try:
            from ..core.develop import histogram
            from ..core.layers import composite
            out = composite(self.layers, self.proxies, full=False, show_mask_of=self.show_mask_of)
            self.done.emit(np.ascontiguousarray(to_uint8(out, stretch=False)), histogram(out))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
