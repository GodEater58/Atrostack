"""Orchestrazione completa: master → calibrazione → stelle → allineamento → stacking → gradiente."""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

import cv2
import numpy as np

from . import calibration as cal
from .gradient import GradientInfo, neutralize_background, remove_gradient
from .loader import load_frame
from .registration import (Transform, find_transform, identity, phase_transform,
                           scale_transform, warp_full)
from .stacking import FrameCache, StackOptions, auto_crop_box, stack_frames
from .stars import StarField, detect_stars, downsample_factor, quality_score
from .stretch import to_uint8


class Cancelled(Exception):
    pass


@dataclass
class Settings:
    method: str = "auto"             # auto | media | mediana | sigma | winsor | linearfit
    kappa_low: float = 3.0
    kappa_high: float = 2.5
    iterations: int = 2
    auto_reject: bool = True
    reject_severity: float = 0.5     # 0 = mai, 1 = molto severo
    quality_weights: bool = True
    gradient_removal: bool = True
    gradient_degree: int = 2
    neutralize: bool = True
    debayer: str = "bilinear"        # bilinear | superpixel
    cache_dir: str = ""
    max_band_mb: int = 900
    hot_sigma: float = 6.0
    auto_cosmetic: bool = True
    dark_scaling: bool = True
    interp: str = "cubica"
    workers: int = 2
    auto_crop: bool = True
    max_stars: int = 250
    detection_sigma: float = 5.0
    white_balance: str = "daylight"  # daylight | camera | none (coefficienti del RAW)
    star_color: bool = False          # calibrazione dei colori sulle stelle a fine stack
    landscape: bool = False          # paesaggio: primo piano riconosciuto e tenuto nitido
    align_model: str = "similarita"  # similarita | affine | omografia (grandangoli)
    keep_cache: bool = True          # tiene i frame calibrati per rifare lo stack in pochi secondi
    excluded: tuple = ()             # percorsi dei light esclusi a mano
    drizzle: int = 1                 # 1 = normale, 2 = super-risoluzione 2x (serve dithering)
    master_library: bool = True      # salva e riusa i master dark/bias per fotocamera, ISO e posa
    master_library_dir: str = ""


@dataclass
class FrameInfo:
    index: int
    path: str
    name: str
    status: str = "in coda"          # ok | scartato | errore | in coda
    reason: str = ""
    n_stars: int = 0
    fwhm: float = 0.0
    eccentricity: float = 0.0
    noise: float = 0.0
    background: float = 0.0
    saturated_pct: float = 0.0
    transparency: float = 1.0
    star_signal: float = 0.0
    score: float = 0.0
    weight: float = 1.0
    exposure: Optional[float] = None
    iso: Optional[int] = None
    hot_fixed: int = 0
    trails: int = 0
    transform: Optional[Transform] = None
    cache_path: str = ""
    stack_weight: float = 1.0
    stars: Optional[StarField] = None
    is_reference: bool = False
    shape: Optional[tuple] = None
    wb: Optional[tuple] = None

    def as_row(self) -> dict:
        t = self.transform
        return {
            "nome": self.name, "stato": self.status, "stelle": self.n_stars,
            "fwhm": round(self.fwhm, 2), "ecc": round(self.eccentricity, 2),
            "rumore": self.noise, "sat": round(self.saturated_pct, 1),
            "trasp": round(self.transparency, 2), "punteggio": round(self.score, 2), "peso": round(self.weight, 2),
            "spost": (f"{t.shift[0]:+.1f}, {t.shift[1]:+.1f}" if t else ""),
            "rot": (f"{t.rotation_deg:+.3f}°" if t else ""),
            "rms": (f"{t.rms:.2f}" if t else ""), "metodo": (t.method if t else ""),
            "posa": (f"{self.exposure:g}s" if self.exposure else ""), "iso": (str(self.iso) if self.iso else ""),
            "hot": self.hot_fixed, "scie": self.trails, "motivo": self.reason,
        }


@dataclass
class StackResult:
    image: np.ndarray                     # risultato finale (dopo gradiente/neutralizzazione)
    linear: np.ndarray                    # stack lineare (prima del post-processing)
    frames: list[FrameInfo]
    reference: str
    n_used: int
    gradient: GradientInfo
    masters_info: dict
    elapsed: float
    crop: tuple[int, int, int, int]
    log: list[str] = field(default_factory=list)
    cache: object = None              # FrameCache tenuta in vita se keep_cache = True
    shape: tuple = ()                 # (H, W, C) dello stack prima del ritaglio
    drizzle: int = 1                  # fattore geometrico dell'uscita (1 o 2)
    masters: object = None            # master di calibrazione riusabili durante Live

    def cleanup(self):
        if self.cache is not None:
            try:
                self.cache.cleanup()
            except Exception:
                pass
            self.cache = None


class Callbacks:
    """Sovrascrivi i metodi che ti servono (thread di lavoro)."""
    def on_progress(self, step: str, done: int, total: int, msg: str = ""): ...
    def on_preview(self, rgb8: np.ndarray, text: str = ""): ...
    def on_frame(self, info: FrameInfo): ...
    def on_log(self, msg: str): ...


class Pipeline:
    def __init__(self, lights: list[str], darks: list[str], flats: list[str], bias: list[str],
                 settings: Settings, callbacks: Optional[Callbacks] = None,
                 cancel_event: Optional[threading.Event] = None):
        self.lights, self.darks, self.flats, self.bias = list(lights), list(darks), list(flats), list(bias)
        self.s = settings
        self.cb = callbacks or Callbacks()
        self.cancel = cancel_event or threading.Event()
        self.cache: Optional[FrameCache] = None
        self.log_lines: list[str] = []

    # ------------------------------------------------------------------ utils
    def log(self, msg: str):
        self.log_lines.append(msg)
        self.cb.on_log(msg)

    def _check(self):
        if self.cancel.is_set():
            raise Cancelled()

    def _progress(self, step, done, total, msg=""):
        self.cb.on_progress(step, done, total, msg)

    @staticmethod
    def _resolved_method(method: str, n_frames: int) -> str:
        """Scelta automatica conservativa in base al numero di frame."""
        if method != "auto":
            return method
        if n_frames < 5:
            return "media"
        if n_frames < 10:
            return "winsor"
        return "sigma"

    # ---------------------------------------------------------------- masters
    def build_masters(self) -> cal.Masters:
        m = cal.Masters()
        info: dict = {}
        lib = None
        light_meta = {}
        if self.s.master_library:
            try:
                from .master_library import MasterLibrary
                from .loader import quick_meta
                lib = MasterLibrary(self.s.master_library_dir or None)
                light_meta = quick_meta(self.lights[0]) if self.lights else {}
            except Exception as e:  # noqa: BLE001
                self.log(f"Libreria master non disponibile: {e}")
                lib = None
        # riuso dalla libreria quando mancano i frame
        if lib is not None and not self.bias and light_meta.get("camera"):
            found = lib.find("bias", light_meta)
            if found is not None:
                m.bias, i = found
                m.is_bayer, m.pattern = bool(i.get("is_bayer")), i.get("pattern")
                info["bias"] = i.get("n", 0)
                self.log(f"Master bias preso dalla libreria ({i.get('file', '')})")
        if lib is not None and not self.darks and light_meta.get("camera"):
            found = lib.find("dark", light_meta)
            if found is not None:
                m.dark, i = found
                m.is_bayer, m.pattern = bool(i.get("is_bayer")), i.get("pattern")
                m.dark_exposure = i.get("exposure")
                info["dark"] = i.get("n", 0)
                self.log(f"Master dark preso dalla libreria ({i.get('file', '')})")
        if self.bias:
            self._check()
            b, i = cal.build_master(self.bias, "bias", lambda d, t, s: self._progress("Master bias", d, t, s))
            m.bias, m.is_bayer, m.pattern = b, bool(i.get("is_bayer")), i.get("pattern")
            info["bias"] = i["n"]
            self.log(f"Master bias: {i['n']} frame")
            if lib is not None:
                lib.store("bias", b, i, self.bias[0])
        if self.darks:
            self._check()
            d, i = cal.build_master(self.darks, "dark", lambda d_, t, s: self._progress("Master dark", d_, t, s))
            m.dark, m.is_bayer, m.pattern = d, bool(i.get("is_bayer")), i.get("pattern")
            m.dark_exposure = i.get("exposure")
            info["dark"] = i["n"]
            self.log(f"Master dark: {i['n']} frame" + (f", posa media {i['exposure']:.1f}s" if i.get("exposure") else ""))
            if lib is not None:
                lib.store("dark", d, i, self.darks[0])
        if self.flats:
            self._check()
            f, i = cal.build_master(self.flats, "flat", lambda d_, t, s: self._progress("Master flat", d_, t, s))
            if m.dark is not None and f.shape != m.dark.shape:
                self.log("ATTENZIONE: flat e dark hanno dimensioni diverse, flat ignorati")
            else:
                m.flat = cal.normalize_flat(f, m.bias, m.dark, bool(i.get("is_bayer")))
                m.is_bayer, m.pattern = bool(i.get("is_bayer")), i.get("pattern")
                info["flat"] = i["n"]
                self.log(f"Master flat: {i['n']} frame (normalizzato per canale)")
        # mappa dei pixel difettosi
        if m.dark is not None:
            hot = cal.hot_pixels_from_dark(m.dark, m.is_bayer, sigma=max(self.s.hot_sigma, 4.0))
            if m.flat is not None:
                hot |= cal.dead_pixels_from_flat(m.flat)
            m.hot_mask = hot
            info["hot_pixels"] = int(hot.sum())
            self.log(f"Pixel difettosi mappati dal master dark: {int(hot.sum())}")
        m.info = info
        return m

    # ----------------------------------------------------------- single light
    def _process_light(self, idx: int, path: str, masters: cal.Masters) -> FrameInfo:
        fi = FrameInfo(index=idx, path=path, name=os.path.basename(path))
        try:
            fr = load_frame(path, want_bayer=True)
            fi.exposure, fi.iso = fr.exposure, fr.iso
            data, cinfo = cal.calibrate_light(fr, masters, dark_scaling=self.s.dark_scaling,
                                              auto_cosmetic=self.s.auto_cosmetic, hot_sigma=self.s.hot_sigma)
            fi.hot_fixed = cinfo.get("hot_fixed", 0)
            if self.s.white_balance != "none":
                wb = fr.meta.get("wb_daylight" if self.s.white_balance == "daylight" else "wb_camera") \
                    or fr.meta.get("wb_daylight") or fr.meta.get("wb_camera")
                if wb is not None:
                    data = cal.apply_white_balance(data, fr.is_bayer, fr.pattern, wb)
                    fi.wb = tuple(wb)
            rgb = cal.to_rgb(data, fr.is_bayer, fr.pattern, self.s.debayer)
            fi.stack_weight = float(fr.meta.get("n_frames", 1.0))     # somma di più notti
            del data, fr
            rgb = np.ascontiguousarray(rgb, dtype=np.float32)
            sf = detect_stars(rgb, max_stars=self.s.max_stars, sigma=self.s.detection_sigma)
            fi.cache_path = self.cache.put(rgb, idx)
            fi.stars = sf
            fi.n_stars = sf.n_detected
            fi.fwhm, fi.eccentricity, fi.noise, fi.background = sf.fwhm, sf.eccentricity, sf.noise, sf.background
            fi.saturated_pct = 100.0 * float(sf.saturated) / max(float(sf.n), 1.0)
            fi.star_signal = float(np.median(sf.flux)) if sf.flux.size else 0.0
            fi.shape = tuple(rgb.shape)
            fi.trails = count_trails(rgb)
            fi.status = "ok" if sf.n >= 5 else "scartato"
            if sf.n < 5:
                fi.reason = f"solo {sf.n} stelle trovate"
            if path in (self.s.excluded or ()):
                fi.status, fi.reason = "escluso", "escluso a mano"
        except Cancelled:
            raise
        except Exception as e:  # frame singolo: non blocca tutto
            fi.status = "errore"
            fi.reason = f"{type(e).__name__}: {e}"
        return fi

    def _check_shapes(self, frames: list[FrameInfo]):
        """La dimensione più frequente vince: gli altri frame vengono marcati come errore."""
        shapes = [f.shape for f in frames if f.shape is not None and f.status == "ok"]
        if not shapes:
            shapes = [f.shape for f in frames if f.shape is not None]
        if not shapes:
            raise RuntimeError("Nessun frame leggibile")
        from collections import Counter
        self._shape = Counter(shapes).most_common(1)[0][0]
        for f in frames:
            if f.shape is not None and f.shape != self._shape and f.status != "errore":
                f.status = "errore"
                f.reason = f"dimensioni {f.shape[1]}x{f.shape[0]} diverse dagli altri frame ({self._shape[1]}x{self._shape[0]})"

    # ------------------------------------------------------------------- run
    def run(self) -> StackResult:
        t0 = time.time()
        if not self.lights:
            raise ValueError("Nessun light caricato")
        self.cache = FrameCache(self.s.cache_dir or None)
        self._shape = None
        ok = False
        try:
            res = self._run_inner(t0)
            ok = True
            return res
        finally:
            if self.cache and not (ok and self.s.keep_cache):
                self.cache.cleanup()

    def _run_inner(self, t0: float) -> StackResult:
        s = self.s
        masters = self.build_masters()
        if masters.dark is None and masters.bias is None and masters.flat is None:
            self.log("Nessun frame di calibrazione: correzione cosmetica automatica degli hot pixel")

        # 1) calibrazione + analisi stelle (parallela)
        n = len(self.lights)
        frames: list[Optional[FrameInfo]] = [None] * n
        self._progress("Calibrazione e analisi", 0, n, "")
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, s.workers)) as ex:
            futs = {ex.submit(self._process_light, i, p, masters): i for i, p in enumerate(self.lights)}
            for fut in as_completed(futs):
                fi = fut.result()
                frames[fi.index] = fi
                done += 1
                self.cb.on_frame(fi)
                self._progress("Calibrazione e analisi", done, n, fi.name)
                if done == 1 and fi.status == "ok":
                    self._emit_single_preview(fi, "Primo frame calibrato")
                if self.cancel.is_set():
                    for f in futs:
                        f.cancel()
                    raise Cancelled()
        frames_l: list[FrameInfo] = [f for f in frames if f is not None]
        self._check_shapes(frames_l)
        ok = [f for f in frames_l if f.status == "ok"]
        if not ok:
            raise RuntimeError("Nessun frame utilizzabile: " + "; ".join(f"{f.name}: {f.reason}" for f in frames_l[:3]))

        # 2) qualità, pesi e scarto automatico
        self._score_and_reject(ok)
        ok = [f for f in frames_l if f.status == "ok"]
        for f in frames_l:
            self.cb.on_frame(f)

        # 3) riferimento e allineamento
        ref = max(ok, key=lambda f: f.score)
        ref.is_reference = True
        ref.transform = identity()
        self.log(f"Riferimento: {ref.name} (FWHM {ref.fwhm:.2f} px, {ref.n_stars} stelle)")
        startrail = s.method == "scie"
        if startrail:
            for f in ok:
                f.transform = identity()
                self.cb.on_frame(f)
            self.log("Scie stellari: nessun allineamento, combinazione con il pixel più luminoso")
        if ref.wb:
            self.log(f"Bilanciamento del bianco dal RAW ({s.white_balance}): R ×{ref.wb[0]:.2f}, B ×{ref.wb[2]:.2f}")
        H, W, C = self._shape
        source_hw = (H, W)
        pf = downsample_factor((H, W), 1500)
        ref_small_lum = None
        self._progress("Allineamento", 0, len(ok), "")
        for k, f in enumerate(ok):
            self._check()
            if f is ref or startrail:
                self._progress("Allineamento", k + 1, len(ok), f.name)
                continue
            tr = find_transform(f.stars.xy, ref.stars.xy, model=s.align_model)
            if tr is not None and not self._transform_sane(tr, W, H):
                self.log(f"{f.name}: trasformazione anomala (scala {tr.scale:.3f}, rms {tr.rms:.2f}), riprovo con correlazione di fase")
                tr = None
            if tr is None:
                if ref_small_lum is None:
                    ref_small_lum = self._small_lum(ref, pf)
                tr = phase_transform(ref_small_lum, self._small_lum(f, pf), pf)
                if tr is not None:
                    self.log(f"{f.name}: allineato con correlazione di fase (sola traslazione)")
            if tr is None:
                f.status, f.reason = "scartato", "allineamento fallito"
            else:
                f.transform = tr
            self.cb.on_frame(f)
            self._progress("Allineamento", k + 1, len(ok), f.name)
        ok = [f for f in frames_l if f.status == "ok" and f.transform is not None]
        self.log(f"Frame allineati: {len(ok)} su {n}")

        # 4) anteprima live che migliora frame dopo frame
        self._live_preview(ok, pf, (H, W, C))

        # 5) stacking finale per bande
        chosen_method = "max" if startrail else self._resolved_method(s.method, len(ok))
        if s.method == "auto" and not startrail:
            self.log(f"Combinazione automatica: {chosen_method} ({len(ok)} frame)")
        opt = StackOptions(method=chosen_method, kappa_low=s.kappa_low, kappa_high=s.kappa_high,
                           iterations=s.iterations, max_band_mb=s.max_band_mb, interp=s.interp)
        transforms = [f.transform.M for f in ok]
        weights = [f.weight for f in ok]
        drz = 2 if (int(s.drizzle) == 2 and not startrail) else 1
        if drz == 2:
            transforms = [(M[:2].astype(np.float64) * 2.0) if M.shape[0] == 2
                          else (np.diag([2.0, 2.0, 1.0]) @ M.astype(np.float64))
                          for M in transforms]                                  # sorgente 1x -> uscita 2x
            self.log("Drizzle 2x: uscita a doppia risoluzione (richiede frame ditherati)")
        out_shape = (H * drz, W * drz, C)
        self._progress("Stacking", 0, 1, "")
        linear = stack_frames([f.cache_path for f in ok], transforms, weights, out_shape, opt,
                              progress=lambda d, t, m: self._progress("Stacking", d, t, m),
                              cancelled=self.cancel.is_set)
        self._check()
        H, W = out_shape[0], out_shape[1]

        # 5b) paesaggio: primo piano nitido
        if s.landscape and drz == 1 and not startrail:
            linear = self._landscape(linear, ok, ref, (H, W, C), pf)

        # 6) ritaglio automatico dei bordi non coperti
        crop = (0, 0, W, H)
        if s.auto_crop and len(ok) > 1:
            x0, y0, x1, y1 = auto_crop_box(transforms, (H, W), source_shape=source_hw)
            if (x1 - x0) > 0.5 * W and (y1 - y0) > 0.5 * H:
                crop = (x0, y0, x1, y1)
                linear = np.ascontiguousarray(linear[y0:y1, x0:x1])
                self.log(f"Ritaglio automatico: {x1 - x0}x{y1 - y0} px")

        # 7) inquinamento luminoso
        self._progress("Gradiente", 0, 1, "analisi del fondo cielo")
        if startrail:
            s = Settings(**{**s.__dict__, "star_color": False})
        image, ginfo = postprocess(linear, s)
        self.log(ginfo.describe() + (" → rimosso" if ginfo.applied else ""))
        if ginfo.color_mult:
            self.log(ginfo.describe_color())
        if ginfo.strength > 1.0:
            self.log("ATTENZIONE: gradiente molto forte: se c'è un primo piano (alberi, orizzonte) "
                     "prova grado 1 o disattiva la rimozione")
        self._progress("Gradiente", 1, 1, ginfo.describe())
        self.cb.on_preview(to_uint8(self._preview_size(image)), "Risultato finale")

        elapsed = time.time() - t0
        self.log(f"Completato in {elapsed:.0f} s con {len(ok)} frame")
        # Le stelle occupano pochissima memoria rispetto ai frame. Quando la
        # cache resta viva le conserviamo: il Live può così allineare solo i
        # nuovi scatti senza rianalizzare tutti quelli già elaborati.
        if not s.keep_cache:
            for f in frames_l:
                f.stars = None
        trails = sum(1 for f in frames_l if f.trails)
        if trails:
            self.log(f"Scie di satelliti o aerei rilevate in {trails} frame (il rigetto le elimina)")
        return StackResult(image=image, linear=linear, frames=frames_l, reference=ref.name,
                           n_used=len(ok), gradient=ginfo, masters_info=masters.info, elapsed=elapsed,
                           crop=crop, log=list(self.log_lines),
                           cache=self.cache if s.keep_cache else None, shape=(H, W, C), drizzle=drz,
                           masters=masters if s.keep_cache else None)

    # --------------------------------------------------------------- paesaggio
    def _landscape(self, linear: np.ndarray, ok: list[FrameInfo], ref: FrameInfo, shape, pf: int) -> np.ndarray:
        from .foreground import composite, foreground_mask, foreground_shift
        H, W, C = shape
        self._progress("Primo piano", 0, 1, "riconoscimento")
        mask, info = foreground_mask(linear)
        if mask is None:
            self.log("Paesaggio: " + info.get("reason", "nessun primo piano") + " (stack invariato)")
            return linear
        rows = info["rows"]
        self.log(f"Paesaggio: primo piano riconosciuto ({info['fraction'] * 100:.1f} % dell'immagine, "
                 f"righe {rows[0]}-{rows[1]})")
        # allineamento del primo piano su sé stesso (traslazione) e mediana dei frame
        ref_small = self._small_lum(ref, pf)
        mask_small = cv2.resize(mask, (ref_small.shape[1], ref_small.shape[0]), interpolation=cv2.INTER_AREA)
        transforms, paths = [], []
        for k, f in enumerate(ok):
            self._check()
            if f is ref:
                M = np.array([[1, 0, 0], [0, 1, 0]], np.float64)
            else:
                M = foreground_shift(ref_small, self._small_lum(f, pf), mask_small, pf)
                if M is None:
                    continue
            transforms.append(M)
            paths.append(f.cache_path)
            self._progress("Primo piano", k + 1, len(ok), f.name)
        if len(paths) < 1:
            return linear
        opt = StackOptions(method="mediana" if len(paths) >= 3 else "media", max_band_mb=self.s.max_band_mb,
                           interp="lineare")
        fg = stack_frames(paths, transforms, [1.0] * len(paths), (H, W, C), opt,
                          progress=lambda d, t, m: self._progress("Primo piano", d, t, m),
                          cancelled=self.cancel.is_set, rows=rows)
        self._check()
        self.log(f"Paesaggio: primo piano ricostruito da {len(paths)} frame")
        # copertura reale: dove NESSUN frame ricade in quella zona (bordi dopo lo spostamento,
        # allineamento fallito su troppi frame...) si resta sullo stack originale invece di
        # dipingere di nero — è il bug per cui il primo piano poteva restare scuro/nero
        ones = np.ones((H, W), np.uint8)
        cov_full = np.zeros((H, W), bool)
        for M in transforms:
            _, cov = warp_full(ones, M, "lineare")
            cov_full |= cov
        y0, y1 = rows
        coverage_rows = cov_full[y0:y1]
        fg_area = mask[y0:y1] > 0.5
        uncovered = int(fg_area.sum()) - int((fg_area & coverage_rows).sum())
        if uncovered > 0:
            frac = uncovered / max(int(fg_area.sum()), 1)
            self.log(f"Paesaggio: {frac * 100:.0f}% della zona non era coperto da alcun frame: "
                     "lì resta visibile lo stack originale")
        return composite(linear, fg, mask, rows, coverage=coverage_rows)

    # --------------------------------------------------------------- helpers
    def _transform_sane(self, tr: Transform, W: int, H: int) -> bool:
        if not (0.9 <= tr.scale <= 1.1):
            return False
        if tr.rms > 1.5 or tr.n_inliers < 6:
            return False
        dx, dy = tr.shift
        return abs(dx) < 0.6 * W and abs(dy) < 0.6 * H

    def _small_lum(self, f: FrameInfo, factor: int) -> np.ndarray:
        mm = FrameCache.open(f.cache_path)
        small = FrameCache.decode(np.asarray(mm[::factor, ::factor]))
        if small.ndim == 3:
            small = 0.299 * small[:, :, 0] + 0.587 * small[:, :, 1] + 0.114 * small[:, :, 2]
        return np.ascontiguousarray(small, np.float32)

    def _preview_size(self, img: np.ndarray, max_dim: int = 2200) -> np.ndarray:
        f = downsample_factor(img.shape[:2], max_dim)
        if f == 1:
            return img
        h, w = img.shape[0] // f, img.shape[1] // f
        return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

    def _emit_single_preview(self, f: FrameInfo, text: str):
        try:
            mm = FrameCache.open(f.cache_path)
            pf = downsample_factor(mm.shape[:2], 1500)
            small = FrameCache.decode(np.asarray(mm[::pf, ::pf]))
            self.cb.on_preview(to_uint8(small), text)
        except Exception:
            pass

    def _score_and_reject(self, ok: list[FrameInfo]):
        s = self.s
        fw = np.array([f.fwhm for f in ok if f.fwhm > 0])
        ns = np.array([f.n_stars for f in ok])
        nz = np.array([f.noise for f in ok if f.noise > 0])
        ref_fwhm = float(np.percentile(fw, 15)) if fw.size else 1.0
        ref_n = float(np.median(ns)) if ns.size else 1.0
        ref_noise = float(np.percentile(nz, 15)) if nz.size else 1.0
        signals = np.array([f.star_signal for f in ok if f.star_signal > 0], np.float64)
        ref_signal = float(np.median(signals)) if signals.size else 1.0
        exposures = np.array([f.exposure for f in ok if f.exposure and f.exposure > 0], np.float64)
        med_exposure = float(np.median(exposures)) if exposures.size else 0.0
        for f in ok:
            f.score = quality_score(f.stars, ref_fwhm, ref_n, ref_noise) if f.stars else 0.0
            f.transparency = float(np.clip(f.star_signal / max(ref_signal, 1e-9), 0.2, 2.0)) if f.star_signal > 0 else 1.0
            # La trasparenza entra nel punteggio solo quando le pose sono confrontabili:
            # in uno stack HDR/esposizioni miste non deve penalizzare gli scatti brevi.
            comparable_exp = not med_exposure or not f.exposure or 0.8 <= (f.exposure / med_exposure) <= 1.2
            if comparable_exp:
                f.score *= float(np.clip(f.transparency, 0.5, 1.5) ** 0.25)
        scores = np.array([f.score for f in ok])
        med_score = float(np.median(scores)) if scores.size else 1.0
        med_fwhm = float(np.median(fw)) if fw.size else 1.0
        rejected = 0
        if s.auto_reject and s.reject_severity > 0 and len(ok) >= 3 and s.method != "scie":
            sev = float(np.clip(s.reject_severity, 0, 1))
            fwhm_factor = 1.8 - 0.6 * sev
            star_frac = 0.2 + 0.4 * sev
            score_frac = 0.25 + 0.5 * sev
            for f in ok:
                reasons = []
                if f.fwhm > fwhm_factor * med_fwhm:
                    reasons.append(f"FWHM {f.fwhm:.1f} px (mediana {med_fwhm:.1f})")
                if f.n_stars < star_frac * ref_n:
                    reasons.append(f"poche stelle ({f.n_stars} vs {ref_n:.0f})")
                if f.score < score_frac * med_score:
                    reasons.append(f"punteggio {f.score:.2f} (mediana {med_score:.2f})")
                if reasons:
                    f.status, f.reason = "scartato", "; ".join(reasons)
                    rejected += 1
            # non scartare mai più del 60 %: in quel caso tieni i migliori
            if rejected > 0.6 * len(ok):
                keep_n = max(3, int(round(0.4 * len(ok))))
                for f in sorted(ok, key=lambda x: -x.score)[:keep_n]:
                    if f.status == "scartato" and "allineamento" not in f.reason:
                        f.status, f.reason = "ok", ""
                rejected = sum(1 for f in ok if f.status == "scartato")
        smax = float(scores.max()) if scores.size and scores.max() > 0 else 1.0
        for f in ok:
            base = float(np.clip(f.score / smax, 0.2, 1.0)) if s.quality_weights else 1.0
            f.weight = base * max(float(getattr(f, "stack_weight", 1.0)), 1.0)
        med_tr = float(np.median([f.transparency for f in ok])) if ok else 1.0
        self.log(f"Qualità: FWHM mediana {med_fwhm:.2f} px, trasparenza {med_tr:.2f}×, scartati {rejected} frame")

    def _live_preview(self, ok: list[FrameInfo], pf: int, shape):
        H, W, C = shape
        h, w = (H + pf - 1) // pf, (W + pf - 1) // pf
        acc = np.zeros((h, w, C), np.float32)
        wsum = np.zeros((h, w, 1), np.float32)
        total = len(ok)
        self._progress("Anteprima", 0, total, "")
        for k, f in enumerate(ok):
            self._check()
            mm = FrameCache.open(f.cache_path)
            small = FrameCache.decode(np.asarray(mm[::pf, ::pf]))
            M = scale_transform(f.transform.M, pf)
            warped, cov = warp_full(small, M, "lineare")
            if warped.ndim == 2:
                warped = warped[:, :, None]
            wgt = cov[:, :, None].astype(np.float32) * f.weight
            acc += warped * wgt
            wsum += wgt
            if k < 3 or (k + 1) % max(1, total // 25) == 0 or k == total - 1:
                mean = acc / np.maximum(wsum, 1e-6)
                self.cb.on_preview(to_uint8(mean), f"Anteprima: {k + 1}/{total} frame")
            self._progress("Anteprima", k + 1, total, f.name)


def postprocess(linear: np.ndarray, s: Settings) -> tuple[np.ndarray, GradientInfo]:
    """Rimozione gradiente + neutralizzazione del fondo (ripetibile senza ri-stackare)."""
    if s.gradient_removal:
        image, ginfo = remove_gradient(linear, degree=s.gradient_degree, force=False)
    else:
        from .gradient import fit_background
        _, ginfo = fit_background(linear, s.gradient_degree)
        image = linear
    if s.neutralize:
        image = neutralize_background(image)
    if s.star_color:
        from .gradient import color_calibrate_on_stars
        image, mult, n = color_calibrate_on_stars(image)
        if n >= 10:
            ginfo.color_mult, ginfo.color_stars = mult, n
    return image, ginfo


# ----------------------------------------------------------------------------
# rilevamento delle scie (satelliti, aerei)
# ----------------------------------------------------------------------------
def count_trails(rgb: np.ndarray, min_len_frac: float = 0.12) -> int:
    """Numero di scie rettilinee lunghe nel frame (0 = nessuna)."""
    try:
        from .loader import luminance
        from .stars import downsample_factor
        lum = luminance(rgb)
        f = downsample_factor(lum.shape, 900)
        small = cv2.resize(lum, (lum.shape[1] // f, lum.shape[0] // f), interpolation=cv2.INTER_AREA)
        hp = small - cv2.GaussianBlur(small, (0, 0), 3.0)
        noise = 1.4826 * float(np.median(np.abs(hp - np.median(hp)))) + 1e-9
        mask = (hp > 4.0 * noise).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        min_len = int(min_len_frac * max(small.shape))
        lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=60, minLineLength=min_len, maxLineGap=6)
        return 0 if lines is None else int(len(lines))
    except Exception:
        return 0


def restack(result: StackResult, settings: Settings, excluded: Optional[set] = None,
            progress=None, cancelled=None) -> StackResult:
    """Ricombina i frame già calibrati (cache in memoria): niente rilettura né riallineamento."""
    if result.cache is None:
        raise RuntimeError("Cache non disponibile: rifai lo Stack con 'Tieni la cache' attivo")
    excluded = set(excluded or ())
    use = [f for f in result.frames if f.cache_path and f.status in ("ok", "escluso") and f.path not in excluded
           and f.transform is not None]
    if not use:
        raise RuntimeError("Nessun frame selezionato")
    # La cache contiene sempre i frame calibrati alla risoluzione sorgente.
    # Ricaviamo quindi la geometria 1x dai FrameInfo invece di riusare
    # ``result.shape`` (che può essere 2x se il risultato corrente è Drizzle).
    src_shape = next((tuple(f.shape) for f in use if f.shape and len(f.shape) >= 2), None)
    if src_shape is None:
        # compatibilità con risultati creati da versioni precedenti
        old_drz = max(1, int(getattr(result, "drizzle", 1) or 1))
        H0 = max(1, int(result.shape[0]) // old_drz)
        W0 = max(1, int(result.shape[1]) // old_drz)
        C = int(result.shape[2]) if len(result.shape) > 2 else 3
    else:
        H0, W0 = int(src_shape[0]), int(src_shape[1])
        C = int(src_shape[2]) if len(src_shape) > 2 else 3
    drizzle = 2 if int(getattr(settings, "drizzle", 1) or 1) == 2 and settings.method != "scie" else 1
    H, W = H0 * drizzle, W0 * drizzle
    restack_method = "max" if settings.method == "scie" else Pipeline._resolved_method(settings.method, len(use))
    opt = StackOptions(method=restack_method, kappa_low=settings.kappa_low, kappa_high=settings.kappa_high,
                       iterations=settings.iterations, max_band_mb=settings.max_band_mb, interp=settings.interp)
    transforms = [f.transform.M for f in use]
    if drizzle == 2:
        transforms = [M[:2].astype(np.float64) * 2.0 if M.shape[0] == 2
                      else np.diag([2.0, 2.0, 1.0]) @ M.astype(np.float64)
                      for M in transforms]
    weights = [f.weight for f in use]
    t0 = time.time()
    linear = stack_frames([f.cache_path for f in use], transforms, weights, (H, W, C), opt,
                          progress=progress, cancelled=cancelled)
    crop = (0, 0, W, H)
    if settings.auto_crop and len(use) > 1:
        x0, y0, x1, y1 = auto_crop_box(transforms, (H, W), source_shape=(H0, W0))
        if (x1 - x0) > 0.5 * W and (y1 - y0) > 0.5 * H:
            crop = (x0, y0, x1, y1)
            linear = np.ascontiguousarray(linear[y0:y1, x0:x1])
    image, ginfo = postprocess(linear, settings)
    for f in result.frames:
        if f.path in excluded and f.status == "ok":
            f.status, f.reason = "escluso", "escluso a mano"
        elif f.status == "escluso" and f.path not in excluded:
            f.status, f.reason = "ok", ""
    return StackResult(image=image, linear=linear, frames=result.frames, reference=result.reference,
                       n_used=len(use), gradient=ginfo, masters_info=result.masters_info,
                       elapsed=time.time() - t0, crop=crop,
                       log=result.log + [f"Ricombinati {len(use)} frame in {time.time() - t0:.0f} s"],
                       cache=result.cache, shape=(H, W, C), drizzle=drizzle, masters=result.masters)


def extend_live_stack(result: StackResult, new_paths: list[str], settings: Settings,
                      progress=None, frame_cb=None, log=None, cancelled=None) -> StackResult:
    """Aggiunge nuovi light a uno stack esistente riusando cache e allineamenti.

    Solo i file nuovi vengono letti, calibrati, demosaicizzati e analizzati.
    I frame precedenti restano nella ``FrameCache`` e mantengono le loro
    trasformazioni; al termine viene rifatta soltanto la combinazione.
    """
    if result.cache is None or result.masters is None:
        raise RuntimeError("Live incrementale non disponibile: serve uno stack con cache attiva")
    paths = [p for p in new_paths if p and all(f.path != p for f in result.frames)]
    if not paths:
        return result
    if cancelled and cancelled():
        raise Cancelled()

    pipe = Pipeline([], [], [], [], settings)
    pipe.cache = result.cache
    pipe._shape = next((tuple(f.shape) for f in result.frames if f.shape), None)
    if pipe._shape is None:
        raise RuntimeError("Geometria dei frame non disponibile")
    H0, W0, _ = pipe._shape
    start = max((f.index for f in result.frames), default=-1) + 1
    added: list[FrameInfo] = []

    for i, path in enumerate(paths):
        if cancelled and cancelled():
            raise Cancelled()
        fi = pipe._process_light(start + i, path, result.masters)
        if fi.shape is not None and tuple(fi.shape) != tuple(pipe._shape) and fi.status != "errore":
            fi.status = "errore"
            fi.reason = (f"dimensioni {fi.shape[1]}x{fi.shape[0]} diverse dagli altri frame "
                         f"({W0}x{H0})")
        added.append(fi)
        if frame_cb:
            frame_cb(fi)
        if progress:
            progress(i + 1, len(paths), fi.name)

    existing_ok = [f for f in result.frames if f.status == "ok" and f.transform is not None]
    if not existing_ok:
        raise RuntimeError("Nessun frame di riferimento valido nel Live")
    ref = next((f for f in result.frames if f.name == result.reference or f.is_reference), existing_ok[0])
    if ref.stars is None:
        mm = FrameCache.open(ref.cache_path)
        rgb = FrameCache.decode(np.asarray(mm))
        ref.stars = detect_stars(rgb, max_stars=settings.max_stars, sigma=settings.detection_sigma)

    # Parametri robusti ricavati dalla sessione già valida: servono a pesare
    # e, se richiesto, scartare solo i nuovi scatti senza rimescolare lo storico.
    fw = np.array([f.fwhm for f in existing_ok if f.fwhm > 0], np.float32)
    ns = np.array([f.n_stars for f in existing_ok if f.n_stars > 0], np.float32)
    nz = np.array([f.noise for f in existing_ok if f.noise > 0], np.float32)
    sg = np.array([f.star_signal for f in existing_ok if getattr(f, "star_signal", 0.0) > 0], np.float64)
    exps = np.array([f.exposure for f in existing_ok if f.exposure and f.exposure > 0], np.float64)
    ref_fwhm = float(np.percentile(fw, 15)) if fw.size else max(ref.fwhm, 1.0)
    med_fwhm = float(np.median(fw)) if fw.size else max(ref.fwhm, 1.0)
    ref_n = float(np.median(ns)) if ns.size else max(ref.n_stars, 1)
    ref_noise = float(np.percentile(nz, 15)) if nz.size else max(ref.noise, 1e-6)
    ref_signal = float(np.median(sg)) if sg.size else max(getattr(ref, "star_signal", 1.0), 1e-9)
    med_exposure = float(np.median(exps)) if exps.size else 0.0
    prior_smax = max((f.score for f in existing_ok), default=1.0)
    pf = downsample_factor((H0, W0), 1500)
    ref_small_lum = None
    startrail = settings.method == "scie"
    usable_new = 0

    for fi in added:
        if fi.status != "ok":
            continue
        fi.score = quality_score(fi.stars, ref_fwhm, ref_n, ref_noise) if fi.stars else 0.0
        fi.transparency = float(np.clip(fi.star_signal / max(ref_signal, 1e-9), 0.2, 2.0)) if fi.star_signal > 0 else 1.0
        comparable_exp = not med_exposure or not fi.exposure or 0.8 <= (fi.exposure / med_exposure) <= 1.2
        if comparable_exp:
            fi.score *= float(np.clip(fi.transparency, 0.5, 1.5) ** 0.25)
        if settings.auto_reject and settings.reject_severity > 0 and not startrail:
            sev = float(np.clip(settings.reject_severity, 0, 1))
            reasons = []
            if fi.fwhm > (1.8 - 0.6 * sev) * med_fwhm:
                reasons.append(f"FWHM {fi.fwhm:.1f} px")
            if fi.n_stars < (0.2 + 0.4 * sev) * ref_n:
                reasons.append(f"poche stelle ({fi.n_stars})")
            if reasons:
                fi.status, fi.reason = "scartato", "; ".join(reasons)
                if frame_cb:
                    frame_cb(fi)
                continue
        smax = max(prior_smax, fi.score, 1e-6)
        fi.weight = (float(np.clip(fi.score / smax, 0.2, 1.0)) if settings.quality_weights else 1.0) \
                    * max(float(fi.stack_weight), 1.0)
        if startrail:
            fi.transform = identity()
        else:
            tr = find_transform(fi.stars.xy, ref.stars.xy, model=settings.align_model) if fi.stars else None
            if tr is not None and not pipe._transform_sane(tr, W0, H0):
                tr = None
            if tr is None:
                if ref_small_lum is None:
                    ref_small_lum = pipe._small_lum(ref, pf)
                tr = phase_transform(ref_small_lum, pipe._small_lum(fi, pf), pf)
            if tr is None:
                fi.status, fi.reason = "scartato", "allineamento fallito"
                if frame_cb:
                    frame_cb(fi)
                continue
            fi.transform = tr
        usable_new += 1
        if frame_cb:
            frame_cb(fi)

    result.frames.extend(added)
    if log:
        log(f"Live: {len(added)} nuovi frame analizzati, {usable_new} utilizzabili; ricombino la cache")
    out = restack(result, settings, excluded=set(settings.excluded or ()),
                  progress=progress, cancelled=cancelled)
    out.log.append(f"Live incrementale: +{usable_new} frame (totale {out.n_used})")
    return out
