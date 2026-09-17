"""Pannello opzioni: pochi controlli essenziali, il resto in "Avanzate"."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..core.pipeline import Settings
from . import tooltips as T
from .widgets import AnimatedButton, Collapser
from .i18n import skip, tr

METHODS = [("auto", "Automatico (consigliato)"), ("sigma", "Kappa-sigma"),
           ("winsor", "Sigma winsorizzato"), ("linearfit", "Linear-fit clipping (sessioni miste)"),
           ("mediana", "Mediana"), ("media", "Media semplice"), ("scie", "Scie stellari (senza allineamento)")]
DEBAYER = [("bilinear", "Piena risoluzione"), ("superpixel", "Super-pixel (½ risoluzione)")]
INTERP = [("cubica", "Cubica (consigliata)"), ("lanczos", "Lanczos (più nitida)"), ("lineare", "Lineare (veloce)")]
WHITE_BALANCE = [("daylight", "Luce diurna (consigliato)"), ("camera", "Come scattato"), ("none", "Nessuno")]


def _compact(w):
    """Widget che non impone una larghezza minima: il pannello resta leggibile anche stretto."""
    if isinstance(w, QComboBox):
        w.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(10)
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    w.setMinimumWidth(60)
    return w


class SettingsPanel(QWidget):
    post_changed = Signal()     # opzioni che si possono riapplicare senza ri-stackare

    def __init__(self, parent=None):
        super().__init__(parent)
        self.qs = QSettings("AstroStack", "AstroStack")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # --- essenziali
        g = QGroupBox("Opzioni")
        f = QFormLayout(g)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        f.setHorizontalSpacing(10)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.method = _compact(QComboBox())
        for k, label in METHODS:
            self.method.addItem(label, k)
        f.addRow("Combinazione", self.method)

        self.auto_reject = QCheckBox("Scarta i frame peggiori")
        self.auto_reject.setChecked(True)
        f.addRow(self.auto_reject)
        sev_row = QHBoxLayout()
        self.severity = QSlider(Qt.Orientation.Horizontal)
        self.severity.setRange(0, 100)
        self.severity.setValue(50)
        self.sev_label = QLabel("normale")
        self.sev_label.setProperty("role", "muted")
        self.sev_label.setMinimumWidth(60)
        sev_row.addWidget(self.severity)
        sev_row.addWidget(self.sev_label)
        f.addRow("Severità", sev_row)
        self.severity.valueChanged.connect(self._sev_text)
        self.auto_reject.toggled.connect(self.severity.setEnabled)

        self.weights = QCheckBox("Pesa i frame in base alla qualità")
        self.weights.setChecked(True)
        f.addRow(self.weights)

        self.gradient = QCheckBox("Rimuovi l'inquinamento luminoso")
        self.gradient.setChecked(True)
        f.addRow(self.gradient)
        self.degree = _compact(QSpinBox())
        self.degree.setRange(1, 4)
        self.degree.setValue(2)
        self.degree.setToolTip("1 = piano, 2 = curvatura semplice (consigliato).\n3-4 = gradienti complessi: rischiano di alterare le foto con primo piano")
        f.addRow("Grado del modello", self.degree)
        self.neutralize = QCheckBox("Neutralizza il fondo cielo")
        self.neutralize.setChecked(True)
        f.addRow(self.neutralize)
        self.star_color = QCheckBox("Calibra i colori sulle stelle")
        self.star_color.setChecked(True)
        f.addRow(self.star_color)
        self.landscape = QCheckBox("Paesaggio: primo piano nitido")
        self.landscape.setChecked(False)
        f.addRow(self.landscape)
        lay.addWidget(g)

        # --- avanzate (nascoste)
        self.adv_btn = AnimatedButton("Avanzate ▸", "link")
        self.adv_btn.clicked.connect(self._toggle_adv)
        lay.addWidget(self.adv_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.adv = QGroupBox("Avanzate")
        fa = QFormLayout(self.adv)
        fa.setHorizontalSpacing(10)
        fa.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.white_balance = _compact(QComboBox())
        for k, label in WHITE_BALANCE:
            self.white_balance.addItem(label, k)
        self.white_balance.setToolTip("Coefficienti del bianco letti dal file RAW, applicati prima del debayer")
        fa.addRow("Bianco", self.white_balance)
        self.kappa_low = _compact(QDoubleSpinBox()); self.kappa_low.setRange(1.0, 10.0); self.kappa_low.setSingleStep(0.5); self.kappa_low.setValue(3.0)
        self.kappa_high = _compact(QDoubleSpinBox()); self.kappa_high.setRange(1.0, 10.0); self.kappa_high.setSingleStep(0.5); self.kappa_high.setValue(2.5)
        fa.addRow("Kappa basso (σ)", self.kappa_low)
        fa.addRow("Kappa alto (σ)", self.kappa_high)
        self.iterations = _compact(QSpinBox()); self.iterations.setRange(1, 5); self.iterations.setValue(2)
        fa.addRow("Iterazioni rigetto", self.iterations)
        self.debayer = _compact(QComboBox())
        for k, label in DEBAYER:
            self.debayer.addItem(label, k)
        fa.addRow("Debayer", self.debayer)
        self.interp = _compact(QComboBox())
        for k, label in INTERP:
            self.interp.addItem(label, k)
        fa.addRow("Interpolazione", self.interp)
        self.hot_sigma = _compact(QDoubleSpinBox()); self.hot_sigma.setRange(3.0, 20.0); self.hot_sigma.setValue(6.0)
        self.hot_sigma.setToolTip("Soglia (in σ) per riconoscere gli hot pixel senza dark")
        fa.addRow("Soglia hot pixel", self.hot_sigma)
        self.auto_cosmetic = QCheckBox("Hot pixel automatici senza dark")
        self.auto_cosmetic.setChecked(True)
        self.auto_cosmetic.setToolTip("Correzione cosmetica automatica quando mancano i dark")
        fa.addRow(self.auto_cosmetic)
        self.dark_scaling = QCheckBox("Riscala i dark (posa diversa)")
        self.dark_scaling.setChecked(True)
        self.dark_scaling.setToolTip("Adatta i dark alla posa dei light: servono anche i bias")
        fa.addRow(self.dark_scaling)
        self.auto_crop = QCheckBox("Ritaglia i bordi non coperti")
        self.auto_crop.setChecked(True)
        self.auto_crop.setToolTip("Elimina i bordi che non sono coperti da tutti i frame")
        fa.addRow(self.auto_crop)
        self.align_model = _compact(QComboBox())
        for k, label in (("similarita", "Similarità (consigliato)"), ("affine", "Affine (campo inclinato)"),
                         ("omografia", "Omografia (grandangoli)")):
            self.align_model.addItem(label, k)
        fa.addRow("Allineamento", self.align_model)
        self.keep_cache = QCheckBox("Tieni i frame in cache (Ricombina veloce)")
        self.keep_cache.setChecked(True)
        fa.addRow(self.keep_cache)
        self.drizzle = _compact(QComboBox())
        self.drizzle.addItem("1× normale", 1)
        self.drizzle.addItem("2× super-risoluzione (serve dithering)", 2)
        fa.addRow("Drizzle", self.drizzle)
        self.master_library = QCheckBox("Libreria master dark/bias automatica")
        self.master_library.setChecked(True)
        fa.addRow(self.master_library)
        lrow = QHBoxLayout()
        self.library_dir = _compact(QLineEdit())
        self.library_dir.setPlaceholderText("cartella predefinita (AppData\\AstroStack\\master)")
        lbtn = AnimatedButton("…", "default")
        lbtn.setFixedWidth(34)
        lbtn.clicked.connect(lambda: self._pick_dir(self.library_dir, "Cartella della libreria dei master"))
        lrow.addWidget(self.library_dir); lrow.addWidget(lbtn)
        fa.addRow("Libreria", lrow)
        self.workers = _compact(QSpinBox()); self.workers.setRange(1, 16); self.workers.setValue(max(1, min(4, (os.cpu_count() or 2) // 2)))
        fa.addRow("Thread", self.workers)
        self.band_mb = _compact(QSpinBox()); self.band_mb.setRange(200, 8000); self.band_mb.setSingleStep(100); self.band_mb.setValue(900); self.band_mb.setSuffix(" MB")
        self.band_mb.setToolTip("Memoria usata per ogni banda di stacking: più alta = più veloce")
        fa.addRow("Memoria/banda", self.band_mb)
        crow = QHBoxLayout()
        self.cache_dir = _compact(QLineEdit())
        self.cache_dir.setPlaceholderText("cartella temporanea")
        cbtn = AnimatedButton("…", "default")
        cbtn.setFixedWidth(34)
        cbtn.clicked.connect(self._pick_cache)
        crow.addWidget(self.cache_dir); crow.addWidget(cbtn)
        fa.addRow("Cache", crow)
        self._collapser = Collapser(self.adv, self)   # chiuso all'avvio, si apre con animazione
        lay.addWidget(self._collapser)

        skip(self.adv_btn, self.sev_label)
        self._apply_tooltips((f, fa))
        for w in (self.gradient, self.neutralize, self.star_color):
            w.toggled.connect(lambda *_: self.post_changed.emit())
        self.degree.valueChanged.connect(lambda *_: self.post_changed.emit())
        self.load()

    def _apply_tooltips(self, forms):
        """Popup di spiegazione su ogni opzione (campo + etichetta), visibile finché il mouse ci sta sopra."""
        for name, text in T.OPTIONS.items():
            w = getattr(self, name, None)
            if w is not None:
                w.setToolTip(text)
                w.setToolTipDuration(60000)
        self.sev_label.setToolTip(T.OPTIONS["severity"])
        for f in forms:
            for row in range(f.rowCount()):
                lab = f.itemAt(row, QFormLayout.ItemRole.LabelRole)
                fld = f.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if lab is None or lab.widget() is None or fld is None:
                    continue
                w = fld.widget()
                if w is None and fld.layout() is not None:      # riga con un layout (slider, cache)
                    for i in range(fld.layout().count()):
                        cw = fld.layout().itemAt(i).widget()
                        if cw is not None and cw.toolTip():
                            w = cw
                            break
                if w is not None and w.toolTip():
                    lab.widget().setToolTip(w.toolTip())
                    lab.widget().setToolTipDuration(60000)

    def _sev_text(self, v: int):
        self.sev_label.setText(tr("mai" if v == 0 else "leggera" if v < 35 else "normale" if v < 70 else "severa"))

    def retranslate_i18n(self):
        self._sev_text(self.severity.value())
        self.adv_btn.setText(tr("Avanzate ▾") if self.adv.isVisible() else tr("Avanzate ▸"))

    def _toggle_adv(self):
        vis = self._collapser.toggle()
        self.adv_btn.setText("Avanzate ▾" if vis else "Avanzate ▸")

    def _pick_dir(self, edit: QLineEdit, title: str):
        d = QFileDialog.getExistingDirectory(self, title)
        if d:
            edit.setText(d)

    def _pick_cache(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella per la cache temporanea")
        if d:
            self.cache_dir.setText(d)

    # ------------------------------------------------------------ Settings
    def to_settings(self) -> Settings:
        return Settings(
            method=self.method.currentData(), kappa_low=self.kappa_low.value(), kappa_high=self.kappa_high.value(),
            iterations=self.iterations.value(), auto_reject=self.auto_reject.isChecked(),
            reject_severity=self.severity.value() / 100.0, quality_weights=self.weights.isChecked(),
            gradient_removal=self.gradient.isChecked(), gradient_degree=self.degree.value(),
            neutralize=self.neutralize.isChecked(), debayer=self.debayer.currentData(),
            cache_dir=self.cache_dir.text().strip(), max_band_mb=self.band_mb.value(),
            hot_sigma=self.hot_sigma.value(), auto_cosmetic=self.auto_cosmetic.isChecked(),
            dark_scaling=self.dark_scaling.isChecked(), interp=self.interp.currentData(),
            workers=self.workers.value(), auto_crop=self.auto_crop.isChecked(),
            white_balance=self.white_balance.currentData(), star_color=self.star_color.isChecked(),
            landscape=self.landscape.isChecked(), drizzle=int(self.drizzle.currentData() or 1),
            master_library=self.master_library.isChecked(), master_library_dir=self.library_dir.text().strip(),
            align_model=self.align_model.currentData(), keep_cache=self.keep_cache.isChecked(),
        )

    def set_from_settings(self, s: Settings):
        """Carica i valori da un oggetto Settings (progetto)."""
        for k, v in s.__dict__.items():
            self.qs.setValue(k, v)
        self.load()

    def save(self):
        s = self.to_settings()
        for k, v in s.__dict__.items():
            self.qs.setValue(k, v)

    def load(self):
        d = Settings()
        def g(k, cast):
            v = self.qs.value(k, None)
            if v is None:
                return getattr(d, k)
            if cast is bool:
                return str(v).lower() in ("true", "1")
            try:
                return cast(v)
            except Exception:
                return getattr(d, k)
        self._set_combo(self.method, g("method", str))
        self.kappa_low.setValue(g("kappa_low", float)); self.kappa_high.setValue(g("kappa_high", float))
        self.iterations.setValue(g("iterations", int)); self.auto_reject.setChecked(g("auto_reject", bool))
        self.severity.setValue(int(round(g("reject_severity", float) * 100))); self._sev_text(self.severity.value())
        self.weights.setChecked(g("quality_weights", bool)); self.gradient.setChecked(g("gradient_removal", bool))
        self.degree.setValue(g("gradient_degree", int)); self.neutralize.setChecked(g("neutralize", bool))
        self._set_combo(self.debayer, g("debayer", str)); self.cache_dir.setText(g("cache_dir", str))
        self.band_mb.setValue(g("max_band_mb", int)); self.hot_sigma.setValue(g("hot_sigma", float))
        self.auto_cosmetic.setChecked(g("auto_cosmetic", bool)); self.dark_scaling.setChecked(g("dark_scaling", bool))
        self._set_combo(self.interp, g("interp", str)); self.workers.setValue(g("workers", int))
        self.auto_crop.setChecked(g("auto_crop", bool))
        self._set_combo(self.white_balance, g("white_balance", str)); self.star_color.setChecked(g("star_color", bool))
        self.landscape.setChecked(g("landscape", bool))
        i = self.drizzle.findData(g("drizzle", int)); self.drizzle.setCurrentIndex(i if i >= 0 else 0)
        self.master_library.setChecked(g("master_library", bool)); self.library_dir.setText(g("master_library_dir", str))
        self._set_combo(self.align_model, g("align_model", str)); self.keep_cache.setChecked(g("keep_cache", bool))

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        i = combo.findData(value)
        if i >= 0:
            combo.setCurrentIndex(i)
