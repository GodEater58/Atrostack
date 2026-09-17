"""Pannello "Strumenti IA": GraXpert, StarNet++, astrometry.net, annulla."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QSlider, QVBoxLayout, QWidget)

from ..core.ai_tools import find_graxpert, find_starnet
from . import tooltips as T
from .i18n import skip, tr
from . import theme as TH
from .widgets import AnimatedButton, Collapser


class ToolsPanel(QWidget):
    run_tool = Signal(str, dict)        # nome strumento, parametri
    undo = Signal()
    labels_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.qs = QSettings("AstroStack", "AstroStack")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.head = AnimatedButton("Strumenti IA ▸", "link")
        self.head.clicked.connect(self._toggle)
        lay.addWidget(self.head, alignment=Qt.AlignmentFlag.AlignLeft)

        box = QGroupBox("Strumenti IA")
        f = QFormLayout(box)
        f.setHorizontalSpacing(10)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # --- GraXpert
        self.gx_path = QLineEdit(self.qs.value("graxpert_path", "") or "")
        self.gx_path.setPlaceholderText("GraXpert-win64.exe")
        f.addRow("GraXpert", self._path_row(self.gx_path, "Dov'è GraXpert?", "GraXpert (GraXpert*.exe GraXpert*);;Tutti (*)"))
        srow = QHBoxLayout()
        self.gx_strength = QSlider(Qt.Orientation.Horizontal)
        self.gx_strength.setRange(10, 100)
        self.gx_strength.setValue(int(self.qs.value("gx_strength", 50)))
        self.gx_strength_label = QLabel("")
        self.gx_strength_label.setProperty("role", "muted")
        self.gx_strength_label.setMinimumWidth(36)
        self.gx_strength.valueChanged.connect(lambda v: self.gx_strength_label.setText(f"{v} %"))
        self.gx_strength_label.setText(f"{self.gx_strength.value()} %")
        srow.addWidget(self.gx_strength)
        srow.addWidget(self.gx_strength_label)
        f.addRow("Forza denoise", srow)
        self.gx_gpu = QCheckBox("Usa la scheda video (GPU)")
        self.gx_gpu.setChecked(str(self.qs.value("gx_gpu", "true")).lower() in ("true", "1"))
        f.addRow(self.gx_gpu)
        brow = QHBoxLayout()
        self.btn_denoise = AnimatedButton("Denoise IA")
        self.btn_gradient = AnimatedButton("Gradiente IA")
        self.btn_denoise.clicked.connect(lambda: self.run_tool.emit("denoise", self.params()))
        self.btn_gradient.clicked.connect(lambda: self.run_tool.emit("background", self.params()))
        brow.addWidget(self.btn_denoise)
        brow.addWidget(self.btn_gradient)
        f.addRow(brow)

        # --- StarNet++
        self.sn_path = QLineEdit(self.qs.value("starnet_path", "") or "")
        self.sn_path.setPlaceholderText("starnet++.exe")
        f.addRow("StarNet++", self._path_row(self.sn_path, "Dov'è StarNet++?", "StarNet (starnet++* *.exe);;Tutti (*)"))
        self.btn_starnet = AnimatedButton("Rimuovi le stelle")
        self.btn_starnet.clicked.connect(lambda: self.run_tool.emit("starnet", self.params()))
        f.addRow(self.btn_starnet)

        # --- astrometry.net
        self.api_key = QLineEdit(self.qs.value("astrometry_key", "") or "")
        self.api_key.setPlaceholderText("chiave API (gratuita)")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("astrometry.net", self.api_key)
        arow = QHBoxLayout()
        self.btn_annotate = AnimatedButton("Riconosci oggetti")
        self.btn_annotate.clicked.connect(lambda: self.run_tool.emit("annotate", self.params()))
        self.show_labels = QCheckBox("Mostra etichette")
        self.show_labels.setChecked(True)
        self.show_labels.toggled.connect(self.labels_toggled.emit)
        arow.addWidget(self.btn_annotate)
        arow.addWidget(self.show_labels)
        f.addRow(arow)

        # --- annulla
        self.btn_undo = AnimatedButton("Annulla ultima modifica")
        self.btn_undo.clicked.connect(self.undo.emit)
        self.btn_undo.setEnabled(False)
        f.addRow(self.btn_undo)
        self.hint = QLabel("")
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        f.addRow(self.hint)

        self._collapser = Collapser(box, self)
        lay.addWidget(self._collapser)
        skip(self.hint, self.head, self.gx_strength_label)
        self._tips()
        self.set_ready(False)
        self.refresh_paths()

    # ------------------------------------------------------------------ util
    def _path_row(self, edit: QLineEdit, title: str, filt: str) -> QHBoxLayout:
        row = QHBoxLayout()
        b = AnimatedButton("…")
        b.setFixedWidth(34)

        def pick():
            p, _ = QFileDialog.getOpenFileName(self, tr(title), "", tr(filt))
            if p:
                edit.setText(p)
                self.refresh_paths()
        b.clicked.connect(pick)
        edit.editingFinished.connect(self.refresh_paths)
        row.addWidget(edit)
        row.addWidget(b)
        return row

    def _toggle(self):
        vis = self._collapser.toggle()
        self.head.setText("Strumenti IA ▾" if vis else "Strumenti IA ▸")

    def _tips(self):
        for w, key in ((self.gx_path, "gx_path"), (self.gx_strength, "gx_strength"), (self.gx_gpu, "gx_gpu"),
                       (self.btn_denoise, "denoise"), (self.btn_gradient, "gradient_ai"), (self.sn_path, "sn_path"),
                       (self.btn_starnet, "starnet"), (self.api_key, "api_key"), (self.btn_annotate, "annotate"),
                       (self.show_labels, "labels"), (self.btn_undo, "undo")):
            w.setToolTip(T.TOOLS[key])
            w.setToolTipDuration(60000)

    def refresh_paths(self):
        gx = find_graxpert(self.gx_path.text().strip())
        sn = find_starnet(self.sn_path.text().strip())
        if gx and not self.gx_path.text().strip():
            self.gx_path.setText(gx)
        if sn and not self.sn_path.text().strip():
            self.sn_path.setText(sn)
        msgs = []
        if not gx:
            msgs.append("GraXpert non trovato: scaricalo da graxpert.com (gratuito) e indica il file .exe")
        if not sn:
            msgs.append("StarNet++ non trovato: scaricalo da starnetastro.com e indica starnet++.exe")
        self.hint.setText("\n".join(tr(m) for m in msgs))
        self.hint.setStyleSheet(f"color: {TH.WARN if msgs else TH.OK};")
        self.save()

    def retranslate_i18n(self):
        self.refresh_paths()
        self.head.setText(tr("Strumenti IA ▾") if self._collapser.open else tr("Strumenti IA ▸"))

    def params(self) -> dict:
        self.save()
        return {"graxpert": self.gx_path.text().strip(), "starnet": self.sn_path.text().strip(),
                "api_key": self.api_key.text().strip(), "strength": self.gx_strength.value() / 100.0,
                "gpu": self.gx_gpu.isChecked()}

    def save(self):
        self.qs.setValue("graxpert_path", self.gx_path.text().strip())
        self.qs.setValue("starnet_path", self.sn_path.text().strip())
        self.qs.setValue("astrometry_key", self.api_key.text().strip())
        self.qs.setValue("gx_strength", self.gx_strength.value())
        self.qs.setValue("gx_gpu", self.gx_gpu.isChecked())

    def set_ready(self, ready: bool, busy: bool = False):
        """I pulsanti si attivano solo quando c'è un risultato e nessuno strumento è in esecuzione."""
        for b in (self.btn_denoise, self.btn_gradient, self.btn_starnet, self.btn_annotate):
            b.setEnabled(ready and not busy)

    def set_undo(self, available: bool):
        self.btn_undo.setEnabled(available)
