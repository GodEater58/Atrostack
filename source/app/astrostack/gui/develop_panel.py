"""Pannello "Sviluppo": regolazioni fotografiche con anteprima in tempo reale."""
from __future__ import annotations

import os
from dataclasses import asdict

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider, QTabWidget,
                               QVBoxLayout, QWidget)

from ..core.develop import HSL_NAMES, DevelopParams
from . import tooltips as T
from .i18n import skip, tr
from . import theme as TH
from .widgets import AnimatedButton


class ParamSlider(QWidget):
    """Etichetta + cursore + valore. Doppio clic sull'etichetta = valore predefinito."""
    changed = Signal()

    def retranslate_i18n(self):
        self.label.setText(tr(self._label_it))
        self.label.setToolTip(tr("Doppio clic: valore predefinito"))

    def __init__(self, label: str, vmin: float, vmax: float, default: float, decimals: int = 0,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        self.default = float(default)
        self.decimals = decimals
        self.scale = 10 ** decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._label_it = label
        self.label = QLabel(tr(label))
        self.label.setMinimumWidth(92)
        self.label.setToolTip(tr("Doppio clic: valore predefinito"))
        skip(self.label)
        lay.addWidget(self.label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(round(vmin * self.scale)), int(round(vmax * self.scale)))
        self.slider.setValue(int(round(default * self.scale)))
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self.slider, 1)
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setRange(vmin, vmax)
        self.spin.setValue(default)
        self.spin.setSuffix(suffix)
        self.spin.setSingleStep(1.0 / self.scale if decimals else 1.0)
        self.spin.setFixedWidth(84)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.setStyleSheet("QDoubleSpinBox { padding-right: 6px; padding-left: 6px; }")
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.spin)
        self._block = False
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self.label.mouseDoubleClickEvent = lambda e: self.reset()   # type: ignore[assignment]

    def _from_slider(self, v: int):
        if self._block:
            return
        self._block = True
        self.spin.setValue(v / self.scale)
        self._block = False
        self.changed.emit()

    def _from_spin(self, v: float):
        if self._block:
            return
        self._block = True
        self.slider.setValue(int(round(v * self.scale)))
        self._block = False
        self.changed.emit()

    def value(self) -> float:
        return float(self.spin.value())

    def set_value(self, v: float, emit: bool = False):
        self._block = True
        self.spin.setValue(float(v))
        self.slider.setValue(int(round(float(v) * self.scale)))
        self._block = False
        if emit:
            self.changed.emit()

    def reset(self):
        self.set_value(self.default, emit=True)


class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setMaximumHeight(120)
        self._hist = None

    def set_histogram(self, hist):
        self._hist = hist
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(TH.BORDER), 1))
        p.setBrush(QColor(TH.PANEL))
        p.drawRoundedRect(r, 6, 6)
        if self._hist is None:
            p.setPen(QColor(TH.MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Istogramma")
            return
        for i in range(1, 4):
            x = r.left() + r.width() * i / 4
            p.setPen(QPen(QColor(TH.BORDER), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(x, r.top() + 2), QPointF(x, r.bottom() - 2))
        colors = [QColor(255, 90, 90, 120), QColor(90, 220, 120, 120), QColor(110, 150, 255, 120)]
        n = self._hist.shape[1]
        for c in range(3):
            path = QPainterPath(QPointF(r.left() + 2, r.bottom() - 2))
            for i in range(n):
                x = r.left() + 2 + (r.width() - 4) * i / (n - 1)
                y = r.bottom() - 2 - (r.height() - 6) * float(self._hist[c, i])
                path.lineTo(QPointF(x, y))
            path.lineTo(QPointF(r.right() - 2, r.bottom() - 2))
            path.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(colors[c]))
            p.drawPath(path)
        p.end()


class CurveWidget(QWidget):
    """Curva dei toni: trascina i punti, clic sulla curva per aggiungerne, tasto destro per togliere."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setMaximumHeight(230)
        self.points: list[list[float]] = [[0.0, 0.0], [1.0, 1.0]]
        self._drag = -1
        self.setMouseTracking(True)

    def set_points(self, pts):
        self.points = [[float(a), float(b)] for a, b in pts] or [[0.0, 0.0], [1.0, 1.0]]
        self.update()

    def reset(self):
        self.points = [[0.0, 0.0], [1.0, 1.0]]
        self.update()
        self.changed.emit()

    def _rect(self) -> QRectF:
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        s = min(r.width(), r.height())
        return QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s)

    def _to_px(self, x, y) -> QPointF:
        r = self._rect()
        return QPointF(r.left() + x * r.width(), r.bottom() - y * r.height())

    def _from_px(self, pos) -> tuple[float, float]:
        r = self._rect()
        return (max(0.0, min(1.0, (pos.x() - r.left()) / r.width())),
                max(0.0, min(1.0, (r.bottom() - pos.y()) / r.height())))

    def _curve_y(self, xs):
        import numpy as np
        pts = sorted(self.points)
        px = np.array([q[0] for q in pts]); py = np.array([q[1] for q in pts])
        px, idx = np.unique(px, return_index=True); py = py[idx]
        if px.size < 2:
            return xs
        try:
            from scipy.interpolate import PchipInterpolator
            return np.clip(PchipInterpolator(px, py)(xs), 0, 1)
        except Exception:
            return np.interp(xs, px, py)

    def paintEvent(self, e):
        import numpy as np
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._rect()
        p.setPen(QPen(QColor(TH.BORDER), 1))
        p.setBrush(QColor(TH.PANEL))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QPen(QColor(TH.BORDER), 1, Qt.PenStyle.DotLine))
        for i in range(1, 4):
            p.drawLine(QPointF(r.left() + r.width() * i / 4, r.top()), QPointF(r.left() + r.width() * i / 4, r.bottom()))
            p.drawLine(QPointF(r.left(), r.top() + r.height() * i / 4), QPointF(r.right(), r.top() + r.height() * i / 4))
        p.setPen(QPen(QColor(TH.MUTED), 1, Qt.PenStyle.DashLine))
        p.drawLine(self._to_px(0, 0), self._to_px(1, 1))
        xs = np.linspace(0, 1, 120)
        ys = self._curve_y(xs)
        path = QPainterPath(self._to_px(xs[0], ys[0]))
        for x, y in zip(xs[1:], ys[1:]):
            path.lineTo(self._to_px(x, y))
        p.setPen(QPen(QColor(TH.TEXT), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        for i, (x, y) in enumerate(self.points):
            c = self._to_px(x, y)
            p.setPen(QPen(QColor(TH.ACCENT), 1.5))
            p.setBrush(QColor(TH.ACCENT) if i == self._drag else QColor(TH.PANEL2))
            p.drawEllipse(c, 5, 5)
        p.end()

    def _hit(self, pos) -> int:
        for i, (x, y) in enumerate(self.points):
            c = self._to_px(x, y)
            if (c - pos).manhattanLength() < 10:
                return i
        return -1

    def mousePressEvent(self, e):
        i = self._hit(e.position())
        if e.button() == Qt.MouseButton.RightButton:
            if i > 0 and i < len(self.points) - 1:
                self.points.pop(i)
                self.update()
                self.changed.emit()
            return
        if i < 0:
            x, y = self._from_px(e.position())
            self.points.append([x, y])
            self.points.sort()
            i = self.points.index([x, y])
        self._drag = i
        self.update()

    def mouseMoveEvent(self, e):
        if self._drag < 0:
            return
        x, y = self._from_px(e.position())
        i = self._drag
        if i == 0:
            x = 0.0
        elif i == len(self.points) - 1:
            x = 1.0
        else:
            lo = self.points[i - 1][0] + 0.02
            hi = self.points[i + 1][0] - 0.02
            x = max(lo, min(hi, x))
        self.points[i] = [x, y]
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, e):
        self._drag = -1
        self.update()


class DevelopPanel(QWidget):
    params_changed = Signal(object)     # DevelopParams
    auto_requested = Signal()
    assist_requested = Signal()

    SLIDERS = [
        # sezione, chiave, etichetta, min, max, default, decimali, suffisso
        ("base", "stretch_bg", "Fondo cielo", 5, 45, 25, 0, " %"),
        ("base", "stretch_shadows", "Taglio ombre", -100, 100, 0, 0, ""),
        ("base", "exposure", "Esposizione", -3, 3, 0, 2, " EV"),
        ("base", "contrast", "Contrasto", -100, 100, 0, 0, ""),
        ("base", "highlights", "Alte luci", -100, 100, 0, 0, ""),
        ("base", "shadows", "Ombre", -100, 100, 0, 0, ""),
        ("base", "whites", "Bianchi", -100, 100, 0, 0, ""),
        ("base", "blacks", "Neri", -100, 100, 0, 0, ""),
        ("colore", "temperature", "Temperatura", -100, 100, 0, 0, ""),
        ("colore", "tint", "Tinta", -100, 100, 0, 0, ""),
        ("colore", "vibrance", "Vividezza", -100, 100, 0, 0, ""),
        ("colore", "saturation", "Saturazione", -100, 100, 0, 0, ""),
        ("astro", "gradient_correction", "Rimozione gradiente", 0, 100, 0, 0, " %"),
        ("astro", "sky_neutralization", "Neutralizza cielo", 0, 100, 0, 0, " %"),
        ("astro", "star_protect", "Protezione stelle", 0, 100, 0, 0, " %"),
        ("dettaglio", "clarity", "Chiarezza", -100, 100, 0, 0, ""),
        ("dettaglio", "dehaze", "Riduci velatura", -100, 100, 0, 0, ""),
        ("dettaglio", "sharpen", "Nitidezza", 0, 150, 0, 0, ""),
        ("dettaglio", "sharpen_radius", "Raggio", 0.5, 3.0, 1.0, 1, " px"),
        ("dettaglio", "sharpen_masking", "Mascheratura", 0, 100, 30, 0, ""),
        ("dettaglio", "nr_luminance", "Rumore lumin.", 0, 100, 0, 0, ""),
        ("dettaglio", "nr_color", "Rumore colore", 0, 100, 0, 0, ""),
        ("astro", "star_reduce", "Riduzione stelle", 0, 100, 0, 0, ""),
        ("astro", "deconv", "Deconvoluzione", 0, 100, 0, 0, ""),
        ("astro", "deconv_radius", "Raggio deconv.", 0.8, 8.0, 1.6, 1, " px"),
        ("dettaglio", "wavelet_small", "Dettaglio fine", -100, 100, 0, 0, ""),
        ("dettaglio", "wavelet_medium", "Dettaglio medio", -100, 100, 0, 0, ""),
        ("dettaglio", "wavelet_large", "Strutture grandi", -100, 100, 0, 0, ""),
        ("effetti", "vignette", "Vignettatura", -100, 100, 0, 0, ""),
        ("effetti", "grain", "Grana", 0, 100, 0, 0, ""),
        ("geometria", "rotation", "Rotazione", -45, 45, 0, 1, "°"),
    ]
    TITLES = {"base": "Base", "colore": "Colore", "astro": "Astrofoto", "dettaglio": "Dettaglio", "effetti": "Effetti", "geometria": "Geometria"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.qs = QSettings("AstroStack", "AstroStack")
        self._block = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.setSpacing(8)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.scroll = scroll
        self.section_groups = {}
        self.active_section = "base"

        # intestazione: attiva / auto / reimposta
        head = QHBoxLayout()
        self.enabled = QCheckBox("Sviluppo attivo")
        self.enabled.setChecked(True)
        self.btn_pick = AnimatedButton("Pipetta", "link")
        self.btn_pick.setCheckable(True)
        self.btn_pick.setToolTip(T.tip("Pipetta fondo cielo", "Attiva la pipetta e fai clic su una zona di cielo "
                                       "senza stelle: temperatura e tinta vengono regolate perché quel punto "
                                       "diventi grigio neutro."))
        self.btn_auto = AnimatedButton("Auto", "link")
        self.btn_assist = AnimatedButton("Assistito", "primary")
        self.btn_reset = AnimatedButton("Reimposta", "link")
        head.addWidget(self.enabled)
        head.addStretch(1)
        lay.addLayout(head)
        actions = QHBoxLayout()
        for button in (self.btn_pick, self.btn_auto, self.btn_assist, self.btn_reset):
            button.setMinimumWidth(0)
            button.setMinimumHeight(30)
            actions.addWidget(button)
        lay.addLayout(actions)
        self.hist = HistogramWidget()
        outer.addWidget(self.hist)

        self.sliders: dict[str, ParamSlider] = {}
        groups: dict[str, QVBoxLayout] = {}
        for key, title in self.TITLES.items():
            g = QGroupBox(title)
            gl = QVBoxLayout(g)
            gl.setSpacing(4)
            groups[key] = gl
            self.section_groups[key] = g
            if key == "base":
                srow = QHBoxLayout()
                lab = QLabel("Tipo di stretch")
                lab.setMinimumWidth(92)
                self.stretch_type = QComboBox()
                for k, label in (("mtf", "Classico (MTF)"), ("arcsinh", "Arcsinh: stelle colorate"),
                                 ("hybrid", "Ibrido (metà e metà)"),
                                 ("masked", "Masked: protegge stelle e nuclei")):
                    self.stretch_type.addItem(label, k)
                self.stretch_type.currentIndexChanged.connect(self._emit)
                srow.addWidget(lab)
                srow.addWidget(self.stretch_type, 1)
                gl.addLayout(srow)
            if key == "dettaglio":
                self._hsl_group(lay)
            if key == "effetti":
                self._curve_group(lay)
            lay.addWidget(g)
        for sec, key, label, vmin, vmax, default, dec, suffix in self.SLIDERS:
            sl = ParamSlider(label, vmin, vmax, default, dec, suffix)
            sl.changed.connect(self._emit)
            self.sliders[key] = sl
            groups[sec].addWidget(sl)
            if key in T.DEVELOP:
                sl.setToolTip(T.DEVELOP[key])
                sl.setToolTipDuration(60000)
                sl.label.setToolTip(T.DEVELOP[key])

        # geometria: ritaglio e riflessioni
        geo = groups["geometria"]
        self.auto_crop_rot = QCheckBox("Elimina i bordi neri della rotazione")
        self.auto_crop_rot.setChecked(True)
        self.auto_crop_rot.toggled.connect(self._emit)
        geo.addWidget(self.auto_crop_rot)
        crop = QGridLayout()
        crop.addWidget(QLabel("Ritaglio %"), 0, 0)
        self.crop_spins = []
        for i, name in enumerate(("sinistra", "alto", "destra", "basso")):
            sp = QDoubleSpinBox()
            sp.setRange(0, 45)
            sp.setDecimals(1)
            sp.setSuffix(" " + name[:2])
            sp.setToolTip(f"Ritaglio dal lato {name}, in percentuale")
            sp.valueChanged.connect(self._emit)
            self.crop_spins.append(sp)
            crop.addWidget(sp, 0, 1 + i)
        geo.addLayout(crop)
        flips = QHBoxLayout()
        self.flip_h = QCheckBox("Rifletti ↔")
        self.flip_v = QCheckBox("Rifletti ↕")
        self.flip_h.toggled.connect(self._emit)
        self.flip_v.toggled.connect(self._emit)
        flips.addWidget(self.flip_h)
        flips.addWidget(self.flip_v)
        flips.addStretch(1)
        geo.addLayout(flips)

        # preset
        prow = QHBoxLayout()
        self.btn_save_preset = AnimatedButton("Salva preset…", "link")
        self.btn_load_preset = AnimatedButton("Carica preset…", "link")
        prow.addWidget(self.btn_save_preset)
        prow.addWidget(self.btn_load_preset)
        prow.addStretch(1)
        lay.addLayout(prow)
        lay.addStretch(1)

        self.enabled.toggled.connect(self._emit)
        self.btn_auto.clicked.connect(self.auto_requested.emit)
        self.btn_assist.clicked.connect(self.assist_requested.emit)
        self.btn_reset.clicked.connect(self.reset_all)
        self.btn_save_preset.clicked.connect(self.save_preset)
        self.btn_load_preset.clicked.connect(self.load_preset)
        for w, key in ((self.enabled, "enabled"), (self.btn_auto, "auto"), (self.btn_reset, "reset"),
                       (self.btn_save_preset, "preset_save"), (self.btn_load_preset, "preset_load"),
                       (self.auto_crop_rot, "auto_crop_rotation"), (self.curve, "curve")):
            w.setToolTip(T.DEVELOP.get(key, ""))
            w.setToolTipDuration(60000)
        self.btn_assist.setToolTip("Analizza fondo, rumore, colore e stelle e costruisce una ricetta di sviluppo modificabile.")
        self.btn_assist.setToolTipDuration(60000)
        self._load_last()

    def show_section(self, section: str):
        self.active_section = section
        visible = {"base": {"base"}, "astro": {"astro"},
                   "colore": {"colore", "hsl"}, "dettaglio": {"dettaglio"},
                   "curve": {"curve"}, "geometria": {"geometria", "effetti"}}.get(section, {section})
        for key, group in self.section_groups.items():
            group.setVisible(key in visible)
        self.scroll.verticalScrollBar().setValue(0)

    def _hsl_group(self, lay):
        g = QGroupBox("HSL — colore per colore")
        self.section_groups["hsl"] = g
        gl = QVBoxLayout(g)
        self.hsl_tabs = QTabWidget()
        self.hsl_sliders: dict[str, list[ParamSlider]] = {"h": [], "s": [], "l": []}
        colors = ["#FF5C5C", "#FF9F45", "#F2D34B", "#5FD39B", "#4FD4D4", "#6F9BFF", "#A98BFF", "#F07CDD"]
        for kind, title in (("h", "Tonalità"), ("s", "Saturazione"), ("l", "Luminanza")):
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setSpacing(3)
            pl.setContentsMargins(4, 6, 4, 4)
            for i, name in enumerate(HSL_NAMES):
                sl = ParamSlider(name, -100, 100, 0, 0, "")
                sl.label.setStyleSheet(f"color: {colors[i]}; font-weight: 600;")
                sl.changed.connect(self._emit)
                self.hsl_sliders[kind].append(sl)
                pl.addWidget(sl)
            self.hsl_tabs.addTab(page, title)
        gl.addWidget(self.hsl_tabs)
        b = AnimatedButton("Reimposta HSL", "link")
        b.clicked.connect(self._reset_hsl)
        gl.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)
        g.setToolTip(T.DEVELOP.get("hsl", ""))
        lay.addWidget(g)

    def _reset_hsl(self):
        self._block = True
        for kind in ("h", "s", "l"):
            for sl in self.hsl_sliders[kind]:
                sl.set_value(0)
        self._block = False
        self._emit()

    def _curve_group(self, lay):
        g = QGroupBox("Curva dei toni")
        self.section_groups["curve"] = g
        gl = QVBoxLayout(g)
        self.curve = CurveWidget()
        self.curve.changed.connect(self._emit)
        gl.addWidget(self.curve)
        b = AnimatedButton("Reimposta curva", "link")
        b.clicked.connect(self.curve.reset)
        gl.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addWidget(g)

    # ---------------------------------------------------------------- params
    def params(self) -> DevelopParams:
        p = DevelopParams()
        p.enabled = self.enabled.isChecked()
        for key, sl in self.sliders.items():
            setattr(p, key, sl.value())
        p.curve = [list(q) for q in self.curve.points]
        p.stretch_type = self.stretch_type.currentData()
        p.hsl_h = [sl.value() for sl in self.hsl_sliders["h"]]
        p.hsl_s = [sl.value() for sl in self.hsl_sliders["s"]]
        p.hsl_l = [sl.value() for sl in self.hsl_sliders["l"]]
        p.auto_crop_rotation = self.auto_crop_rot.isChecked()
        p.crop = [sp.value() for sp in self.crop_spins]
        p.flip_h = self.flip_h.isChecked()
        p.flip_v = self.flip_v.isChecked()
        return p

    def set_params(self, p: DevelopParams, emit: bool = True):
        self._block = True
        self.enabled.setChecked(p.enabled)
        for key, sl in self.sliders.items():
            sl.set_value(getattr(p, key))
        self.curve.set_points(p.curve)
        self.stretch_type.setCurrentIndex(max(0, self.stretch_type.findData(p.stretch_type)))
        for kind, vals in (("h", p.hsl_h), ("s", p.hsl_s), ("l", p.hsl_l)):
            for sl, v in zip(self.hsl_sliders[kind], list(vals) + [0.0] * 8):
                sl.set_value(float(v))
        self.auto_crop_rot.setChecked(p.auto_crop_rotation)
        for sp, v in zip(self.crop_spins, p.crop):
            sp.setValue(float(v))
        self.flip_h.setChecked(p.flip_h)
        self.flip_v.setChecked(p.flip_v)
        self._block = False
        if emit:
            self._emit()

    def _emit(self, *_):
        if self._block:
            return
        p = self.params()
        self.qs.setValue("develop_params", p.to_json())
        self.params_changed.emit(p)

    def reset_all(self):
        self.set_params(DevelopParams(), emit=True)

    def set_histogram(self, hist):
        self.hist.set_histogram(hist)

    def _load_last(self):
        txt = self.qs.value("develop_params", "")
        if txt:
            try:
                self.set_params(DevelopParams.from_json(str(txt)), emit=False)
            except Exception:
                pass

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Salva preset di sviluppo"), "", "Preset AstroStack (*.json)")
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.params().to_json())

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Carica preset di sviluppo"), "", "Preset AstroStack (*.json)")
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self.set_params(DevelopParams.from_json(f.read()), emit=True)
