"""Tabella dei frame: qualità, allineamento, stato."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from ..core.pipeline import FrameInfo
from . import theme as TH
from . import tooltips as T
from .i18n import tr

COLUMNS = [
    ("nome", "File"), ("stato", "Stato"), ("stelle", "Stelle"), ("fwhm", "FWHM px"),
    ("ecc", "Ecc."), ("sat", "Sat. %"), ("trasp", "Traspar."),
    ("punteggio", "Qualità"), ("peso", "Peso"), ("spost", "Spostamento"),
    ("rot", "Rotazione"), ("rms", "RMS px"), ("metodo", "Allineamento"), ("posa", "Posa"),
    ("iso", "ISO"), ("hot", "Hot px"), ("scie", "Scie"), ("motivo", "Note"),
]
STATUS_COLOR = {"ok": TH.OK, "scartato": TH.WARN, "errore": TH.WARN, "in coda": TH.MUTED, "escluso": TH.MUTED}


class FramesTable(QTableWidget):
    frame_toggled = Signal(str, bool)      # percorso, escluso
    frame_activated = Signal(str)          # doppio clic sulla riga

    def __init__(self, parent=None):
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        for c, (key, label) in enumerate(COLUMNS):
            it = self.horizontalHeaderItem(c)
            if it is not None and key in T.COLUMNS:
                it.setToolTip(T.tip(label, T.COLUMNS[key]))
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(False)
        last = len(COLUMNS) - 1                      # "Note": larghezza fissa ma regolabile a mano
        hdr.setSectionResizeMode(last, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(last, 280)
        hdr.setMinimumSectionSize(48)
        self._rows: dict[str, int] = {}
        self._block = False
        self.itemChanged.connect(self._on_item_changed)
        self.itemDoubleClicked.connect(
            lambda it: self.frame_activated.emit(self.item(it.row(), 0).data(Qt.ItemDataRole.UserRole) or ""))

    def reset_frames(self, paths: list[str]):
        self.setSortingEnabled(False)
        self.setRowCount(0)
        import os
        for p in paths:
            r = self.rowCount()
            self.insertRow(r)
            for c, (key, _) in enumerate(COLUMNS):
                it = QTableWidgetItem(os.path.basename(p) if key == "nome" else (tr("in coda") if key == "stato" else ""))
                if key == "nome":
                    it.setData(Qt.ItemDataRole.UserRole, p)
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    it.setCheckState(Qt.CheckState.Checked)
                    it.setToolTip(T.tip("Includi / escludi", "Togli la spunta per escludere questo scatto, poi premi "
                                        "<b>Ricombina</b>: bastano pochi secondi.<br>Doppio clic sulla riga per "
                                        "vedere questo singolo frame nell'anteprima."))   # chiave stabile anche dopo l'ordinamento
                if key == "stato":
                    it.setForeground(QColor(TH.MUTED))
                self.setItem(r, c, it)
        self.setSortingEnabled(True)

    def _row_of(self, path: str) -> int | None:
        for r in range(self.rowCount()):
            it = self.item(r, 0)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) == path:
                return r
        return None

    def _on_item_changed(self, it: QTableWidgetItem):
        if self._block or it.column() != 0:
            return
        path = it.data(Qt.ItemDataRole.UserRole)
        if path:
            self.frame_toggled.emit(path, it.checkState() != Qt.CheckState.Checked)

    def update_frame(self, fi: FrameInfo):
        r = self._row_of(fi.path)
        if r is None:
            return
        self._block = True
        self.setSortingEnabled(False)
        row = fi.as_row()
        for c, (key, _) in enumerate(COLUMNS):
            v = row.get(key, "")
            it = self.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                self.setItem(r, c, it)
            if isinstance(v, float):
                it.setData(Qt.ItemDataRole.DisplayRole, f"{v:.4g}" if key == "rumore" else f"{v:g}")
            elif key == "metodo":
                it.setData(Qt.ItemDataRole.DisplayRole, tr(str(v)))
            else:
                it.setData(Qt.ItemDataRole.DisplayRole, str(v))
            if key == "motivo":
                it.setToolTip(str(v))                # il testo completo compare passando il mouse
            if key == "stato":
                text = tr("riferimento" if fi.is_reference else fi.status)
                it.setText(text)
                it.setForeground(QColor(TH.ACCENT if fi.is_reference else STATUS_COLOR.get(fi.status, TH.MUTED)))
            if key == "nome" and fi.is_reference:
                it.setForeground(QColor(TH.ACCENT))
        self.setSortingEnabled(True)
        self._block = False
