"""Pannello "Livelli": elenco, opacità, fusione, posizione, maschere e pennello."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QScrollArea, QSizePolicy, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from ..core.layers import BLEND_MODES, MASK_TYPES, Layer
from . import tooltips as T
from .i18n import skip, tr
from .widgets import AnimatedButton


class LayersPanel(QWidget):
    changed = Signal()                  # proprietà cambiate: ricomponi
    selection_changed = Signal(int)
    add_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()
    move_requested = Signal(int)        # -1 = su (verso il fondo dell'elenco?), +1 = giù
    paint_mode_changed = Signal(bool)
    show_mask_changed = Signal(bool)
    clear_brush_requested = Signal()
    load_mask_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layers: list[Layer] = []
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

        # --- elenco (dall'alto: livello più in alto = disegnato per ultimo)
        self.list = QListWidget()
        self.list.setMinimumHeight(120)
        self.list.setMaximumHeight(200)
        self.list.itemChanged.connect(self._item_changed)
        self.list.currentRowChanged.connect(self._row_changed)
        lay.addWidget(self.list)
        brow = QHBoxLayout()
        self.btn_add = AnimatedButton("Aggiungi immagine…")
        self.btn_dup = AnimatedButton("Duplica", "link")
        self.btn_del = AnimatedButton("Elimina", "link")
        self.btn_up = AnimatedButton("▲", "link")
        self.btn_down = AnimatedButton("▼", "link")
        for b in (self.btn_add, self.btn_dup, self.btn_del, self.btn_up, self.btn_down):
            brow.addWidget(b)
        lay.addLayout(brow)
        self.btn_add.clicked.connect(self.add_requested.emit)
        self.btn_dup.clicked.connect(self.duplicate_requested.emit)
        self.btn_del.clicked.connect(self.delete_requested.emit)
        self.btn_up.clicked.connect(lambda: self.move_requested.emit(+1))
        self.btn_down.clicked.connect(lambda: self.move_requested.emit(-1))

        # --- proprietà del livello
        g = QGroupBox("Livello selezionato")
        f = QFormLayout(g)
        f.setHorizontalSpacing(10)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        orow = QHBoxLayout()
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity_label = QLabel("100 %")
        self.opacity_label.setMinimumWidth(44)
        orow.addWidget(self.opacity)
        orow.addWidget(self.opacity_label)
        f.addRow("Opacità", orow)
        self.blend = QComboBox()
        for k, label in BLEND_MODES:
            self.blend.addItem(label, k)
        f.addRow("Fusione", self.blend)
        prow = QHBoxLayout()
        self.off_x = QSpinBox(); self.off_x.setRange(-20000, 20000); self.off_x.setSuffix(" px")
        self.off_y = QSpinBox(); self.off_y.setRange(-20000, 20000); self.off_y.setSuffix(" px")
        prow.addWidget(QLabel("X")); prow.addWidget(self.off_x); prow.addWidget(QLabel("Y")); prow.addWidget(self.off_y)
        f.addRow("Posizione", prow)
        self.scale = QDoubleSpinBox(); self.scale.setRange(5, 800); self.scale.setValue(100); self.scale.setSuffix(" %"); self.scale.setDecimals(1)
        f.addRow("Scala", self.scale)
        lay.addWidget(g)

        # --- maschera
        gm = QGroupBox("Maschera")
        fm = QFormLayout(gm)
        fm.setHorizontalSpacing(10)
        fm.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.mask_type = QComboBox()
        for k, label in MASK_TYPES:
            self.mask_type.addItem(label, k)
        fm.addRow("Tipo", self.mask_type)
        self.mask_invert = QCheckBox("Inverti")
        self.show_mask = QCheckBox("Mostra in rosso")
        mrow = QHBoxLayout(); mrow.addWidget(self.mask_invert); mrow.addWidget(self.show_mask); mrow.addStretch(1)
        fm.addRow(mrow)
        self.feather = QDoubleSpinBox(); self.feather.setRange(0, 500); self.feather.setSuffix(" px"); self.feather.setDecimals(0)
        fm.addRow("Sfumatura bordo", self.feather)
        # sfumatura lineare
        self.grad_start = QDoubleSpinBox(); self.grad_start.setRange(0, 100); self.grad_start.setValue(40); self.grad_start.setSuffix(" %"); self.grad_start.setDecimals(0)
        self.grad_end = QDoubleSpinBox(); self.grad_end.setRange(0, 100); self.grad_end.setValue(60); self.grad_end.setSuffix(" %"); self.grad_end.setDecimals(0)
        grow = QHBoxLayout(); grow.addWidget(QLabel("da")); grow.addWidget(self.grad_start); grow.addWidget(QLabel("a")); grow.addWidget(self.grad_end)
        self.grad_row = QWidget(); self.grad_row.setLayout(grow)
        fm.addRow("Sfumatura", self.grad_row)
        self._fm = fm
        self.grad_horizontal = QCheckBox("Orizzontale (da sinistra a destra)")
        fm.addRow(self.grad_horizontal)
        # luminosità
        self.lum_low = QDoubleSpinBox(); self.lum_low.setRange(0, 100); self.lum_low.setValue(20); self.lum_low.setSuffix(" %"); self.lum_low.setDecimals(0)
        self.lum_high = QDoubleSpinBox(); self.lum_high.setRange(0, 100); self.lum_high.setValue(60); self.lum_high.setSuffix(" %"); self.lum_high.setDecimals(0)
        lrow = QHBoxLayout(); lrow.addWidget(QLabel("scuro")); lrow.addWidget(self.lum_low); lrow.addWidget(QLabel("chiaro")); lrow.addWidget(self.lum_high)
        self.lum_row = QWidget(); self.lum_row.setLayout(lrow)
        fm.addRow("Luminosità", self.lum_row)
        # pennello
        self.brush_size = QSpinBox(); self.brush_size.setRange(2, 600); self.brush_size.setValue(60); self.brush_size.setSuffix(" px")
        self.brush_hard = QSlider(Qt.Orientation.Horizontal); self.brush_hard.setRange(0, 100); self.brush_hard.setValue(40)
        self.brush_erase = QCheckBox("Cancella invece di aggiungere")
        self.btn_paint = AnimatedButton("Dipingi sull'anteprima")
        self.btn_paint.setCheckable(True)
        self.btn_clear_brush = AnimatedButton("Cancella tutto", "link")
        self.brush_box = QWidget()
        bl = QFormLayout(self.brush_box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addRow("Dimensione", self.brush_size)
        bl.addRow("Durezza", self.brush_hard)
        bl.addRow(self.brush_erase)
        pr = QHBoxLayout(); pr.addWidget(self.btn_paint); pr.addWidget(self.btn_clear_brush)
        bl.addRow(pr)
        fm.addRow(self.brush_box)
        self.btn_load_mask = AnimatedButton("Carica maschera da file…")
        fm.addRow(self.btn_load_mask)
        lay.addWidget(gm)
        self.hint = QLabel("Il livello 1 è la base (lo stack o l'immagine aperta). Aggiungi una foto per il primo "
                           "piano, scegli fusione e maschera; il pannello Sviluppo regola il livello selezionato.")
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        lay.addStretch(1)

        # collegamenti
        self.opacity.valueChanged.connect(lambda v: (self.opacity_label.setText(f"{v} %"), self._apply()))
        for w in (self.blend, self.mask_type):
            w.currentIndexChanged.connect(self._apply)
        for w in (self.off_x, self.off_y, self.scale, self.feather, self.grad_start, self.grad_end, self.lum_low, self.lum_high):
            w.valueChanged.connect(self._apply)
        for w in (self.mask_invert, self.grad_horizontal):
            w.toggled.connect(self._apply)
        self.show_mask.toggled.connect(self.show_mask_changed.emit)
        self.btn_paint.toggled.connect(self.paint_mode_changed.emit)
        self.btn_clear_brush.clicked.connect(self.clear_brush_requested.emit)
        self.btn_load_mask.clicked.connect(self.load_mask_requested.emit)
        for w, key in ((self.btn_add, "add"), (self.btn_dup, "dup"), (self.btn_del, "del"), (self.opacity, "opacity"),
                       (self.blend, "blend"), (self.off_x, "position"), (self.off_y, "position"), (self.scale, "scale"),
                       (self.mask_type, "mask_type"), (self.mask_invert, "invert"), (self.show_mask, "show_mask"),
                       (self.feather, "feather"), (self.grad_row, "gradient"), (self.lum_row, "luminosity"),
                       (self.brush_size, "brush_size"), (self.brush_hard, "brush_hard"), (self.btn_paint, "paint"),
                       (self.btn_load_mask, "load_mask"), (self.btn_up, "move"), (self.btn_down, "move")):
            w.setToolTip(T.LAYERS.get(key, ""))
            w.setToolTipDuration(60000)
        skip(self.opacity_label)
        self._refresh_visibility()

    # ------------------------------------------------------------------ elenco
    def set_layers(self, layers: list[Layer], select: int | None = None):
        self._layers = layers
        cur = self.list.currentRow() if select is None else select
        self._block = True
        self.list.clear()
        for i in range(len(layers) - 1, -1, -1):          # in alto il livello più in alto
            lay = layers[i]
            it = QListWidgetItem(f"{i + 1}. {lay.name}" + (tr("  (base)") if i == 0 else ""))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if lay.visible else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(it)
        self._block = False
        if layers:
            idx = max(0, min(cur if cur is not None and cur >= 0 else len(layers) - 1, len(layers) - 1))
            self.select(idx)

    def select(self, index: int):
        for r in range(self.list.count()):
            if self.list.item(r).data(Qt.ItemDataRole.UserRole) == index:
                self.list.setCurrentRow(r)
                break
        self._load_props()

    def current_index(self) -> int:
        it = self.list.currentItem()
        return int(it.data(Qt.ItemDataRole.UserRole)) if it is not None else 0

    def _item_changed(self, it: QListWidgetItem):
        if self._block:
            return
        i = int(it.data(Qt.ItemDataRole.UserRole))
        if 0 <= i < len(self._layers):
            self._layers[i].visible = it.checkState() == Qt.CheckState.Checked
            self.changed.emit()

    def _row_changed(self, row: int):
        if self._block or row < 0:
            return
        self._load_props()
        self.selection_changed.emit(self.current_index())

    # ------------------------------------------------------------------ proprietà
    def _load_props(self):
        i = self.current_index()
        if not (0 <= i < len(self._layers)):
            return
        lay = self._layers[i]
        self._block = True
        self.opacity.setValue(int(lay.opacity))
        self.opacity_label.setText(f"{int(lay.opacity)} %")
        self.blend.setCurrentIndex(max(0, self.blend.findData(lay.blend)))
        self.off_x.setValue(int(lay.offset_x))
        self.off_y.setValue(int(lay.offset_y))
        self.scale.setValue(float(lay.scale))
        self.mask_type.setCurrentIndex(max(0, self.mask_type.findData(lay.mask_type)))
        self.mask_invert.setChecked(lay.mask_invert)
        self.feather.setValue(float(lay.mask_feather))
        self.grad_start.setValue(float(lay.grad_start))
        self.grad_end.setValue(float(lay.grad_end))
        self.grad_horizontal.setChecked(lay.grad_horizontal)
        self.lum_low.setValue(float(lay.lum_low))
        self.lum_high.setValue(float(lay.lum_high))
        is_base = i == 0
        for w in (self.opacity, self.blend, self.off_x, self.off_y, self.scale, self.mask_type, self.mask_invert,
                  self.feather, self.grad_row, self.grad_horizontal, self.lum_row, self.brush_box, self.btn_load_mask,
                  self.show_mask, self.btn_del):
            w.setEnabled(not is_base)
        self._block = False
        self._refresh_visibility()

    def _refresh_visibility(self):
        t = self.mask_type.currentData()
        for w, vis in ((self.grad_row, t == "gradient"), (self.grad_horizontal, t == "gradient"),
                       (self.lum_row, t == "luminosity"), (self.brush_box, t == "brush"), (self.btn_load_mask, t == "file")):
            w.setVisible(vis)
            lab = self._fm.labelForField(w) if hasattr(self, "_fm") else None
            if lab is not None:
                lab.setVisible(vis)
        if t != "brush" and self.btn_paint.isChecked():
            self.btn_paint.setChecked(False)

    def _apply(self, *_):
        if self._block:
            return
        i = self.current_index()
        if not (0 <= i < len(self._layers)):
            return
        lay = self._layers[i]
        lay.opacity = float(self.opacity.value())
        lay.blend = self.blend.currentData()
        lay.offset_x = float(self.off_x.value())
        lay.offset_y = float(self.off_y.value())
        lay.scale = float(self.scale.value())
        lay.mask_type = self.mask_type.currentData()
        lay.mask_invert = self.mask_invert.isChecked()
        lay.mask_feather = float(self.feather.value())
        lay.grad_start = float(self.grad_start.value())
        lay.grad_end = float(self.grad_end.value())
        lay.grad_horizontal = self.grad_horizontal.isChecked()
        lay.lum_low = float(self.lum_low.value())
        lay.lum_high = float(self.lum_high.value())
        self._refresh_visibility()
        self.changed.emit()

    def brush(self) -> tuple[int, float, bool]:
        return int(self.brush_size.value()), self.brush_hard.value() / 100.0, self.brush_erase.isChecked()
