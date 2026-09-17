"""Finestre di servizio: gestione dei file di una zona, elaborazione a lotti, guida rapida."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QFileDialog, QVBoxLayout, QWidget)

from .i18n import tr
from . import theme as TH
from .widgets import AnimatedButton

ZONE_LABELS = {"light": "Light", "dark": "Dark", "flat": "Flat", "bias": "Bias"}


class FileManagerDialog(QDialog):
    """Elenco dei file di una zona: rimuovi o sposta in un'altra zona."""
    moved = Signal(str, str, list)     # da, a, file
    removed = Signal(str, list)        # zona, file

    def __init__(self, zone: str, files: list[str], parent=None):
        super().__init__(parent)
        self.zone = zone
        self.setWindowTitle(tr("Gestisci i file") + f" — {ZONE_LABELS.get(zone, zone)}")
        self.setMinimumSize(620, 460)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        info = QLabel(tr("Seleziona uno o più file (Ctrl o Maiusc per sceglierne diversi), poi rimuovili "
                         "oppure spostali nella zona giusta."))
        info.setProperty("role", "muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for f in files:
            it = QListWidgetItem(os.path.basename(f))
            it.setData(Qt.ItemDataRole.UserRole, f)
            it.setToolTip(f)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        self.count = QLabel("")
        self.count.setProperty("role", "muted")
        lay.addWidget(self.count)
        row = QHBoxLayout()
        self.btn_remove = AnimatedButton(tr("Rimuovi dalla zona"))
        self.btn_remove.clicked.connect(self._remove)
        row.addWidget(self.btn_remove)
        row.addSpacing(12)
        row.addWidget(QLabel(tr("Sposta in:")))
        for k, label in ZONE_LABELS.items():
            if k == zone:
                continue
            b = AnimatedButton(label, "link")
            b.clicked.connect(lambda _=False, dest=k: self._move(dest))
            row.addWidget(b)
        row.addStretch(1)
        close = AnimatedButton(tr("Chiudi"), "primary")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.list.itemSelectionChanged.connect(self._update_count)
        self._update_count()

    def _selected(self) -> list[str]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]

    def _update_count(self):
        n = len(self.list.selectedItems())
        self.count.setText(tr(f"{self.list.count()} file") + (f"  ·  {n} " + tr("selezionati") if n else ""))
        self.btn_remove.setEnabled(n > 0)

    def _remove(self):
        files = self._selected()
        if not files:
            return
        self.removed.emit(self.zone, files)
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))
        self._update_count()

    def _move(self, dest: str):
        files = self._selected()
        if not files:
            return
        self.moved.emit(self.zone, dest, files)
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))
        self._update_count()


class BatchDialog(QDialog):
    """Elaborazione a lotti: più sessioni una dopo l'altra."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Elaborazione a lotti"))
        self.setMinimumSize(640, 440)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        info = QLabel(tr("Aggiungi le cartelle delle sessioni (ognuna con le sottocartelle Lights / Darks / "
                         "Flats / Bias). Verranno elaborate una dopo l'altra con le impostazioni attuali e il "
                         "risultato sarà salvato dentro ogni cartella."))
        info.setProperty("role", "muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        add = AnimatedButton(tr("Aggiungi cartella…"))
        add.clicked.connect(self._add)
        rem = AnimatedButton(tr("Togli"), "link")
        rem.clicked.connect(self._remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)
        self.save_report = QCheckBox(tr("Salva anche il report della sessione"))
        self.save_report.setChecked(True)
        lay.addWidget(self.save_report)
        self.autoexport = QCheckBox(tr("Esporta anche un JPG pronto da guardare"))
        self.autoexport.setChecked(True)
        lay.addWidget(self.autoexport)
        row2 = QHBoxLayout()
        row2.addStretch(1)
        cancel = AnimatedButton(tr("Annulla"))
        cancel.clicked.connect(self.reject)
        start = AnimatedButton(tr("Avvia"), "primary")
        start.clicked.connect(self.accept)
        row2.addWidget(cancel)
        row2.addWidget(start)
        lay.addLayout(row2)

    def _add(self):
        d = QFileDialog.getExistingDirectory(self, tr("Cartella della sessione"))
        if d:
            self.list.addItem(d)

    def _remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def folders(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]


GUIDE_HTML = """
<h2 style="color:{accent};margin:0 0 6px">Benvenuto in AstroStack</h2>
<p style="color:{muted};margin:0 0 14px">Tre passi per la tua prima foto.</p>
<p><b>1. Carica le foto.</b> Trascina i file nelle quattro zone a sinistra, oppure premi
<b>Smista file…</b> e lascia che sia il programma a riconoscere light, dark, flat e bias.
Solo i <b>light</b> sono obbligatori.</p>
<p><b>2. Premi Stack.</b> Calibrazione, allineamento sulle stelle, scarto dei frame mossi, somma,
rimozione dell'inquinamento luminoso e colori: tutto automatico. L'anteprima migliora frame dopo frame.</p>
<p><b>3. Sviluppa ed esporta.</b> Il pannello <b>Sviluppo</b> (a destra) ha i cursori in stile Lightroom;
<b>Livelli</b> serve a fondere il cielo con una foto del primo piano. Poi <b>Esporta…</b>.</p>
<p style="color:{muted}">Passando il mouse su qualsiasi opzione compare una spiegazione.
In alto a destra puoi cambiare lingua (IT / EN).</p>
"""


class GuideDialog(QDialog):
    """Guida rapida mostrata alla prima apertura."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Guida rapida"))
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        text = QLabel(GUIDE_HTML.format(accent=TH.ACCENT, muted=TH.MUTED))
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setStyleSheet(f"QLabel {{ background: {TH.PANEL}; color: {TH.TEXT}; border-radius: 10px; padding: 16px; }}")
        lay.addWidget(text)
        row = QHBoxLayout()
        self.dont_show = QCheckBox(tr("Non mostrare più all'avvio"))
        self.dont_show.setChecked(True)
        row.addWidget(self.dont_show)
        row.addStretch(1)
        ok = AnimatedButton(tr("Comincia"), "primary")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)
