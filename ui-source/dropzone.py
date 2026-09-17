"""Zona di trascinamento per una categoria di frame (light, dark, flat, bias)."""
from __future__ import annotations

import os

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core.loader import collect_files
from . import theme as TH
from . import tooltips as T
from .widgets import AnimatedButton
from .i18n import skip, tr

FILTER = ("Immagini (*.cr2 *.cr3 *.crw *.nef *.nrw *.arw *.dng *.raf *.orf *.pef *.rw2 *.raw "
          "*.3fr *.fff *.iiq *.mos *.mrw *.kdc *.dcr *.erf *.mef *.srw *.x3f *.srf *.sr2 *.rwl *.ari "
          "*.fits *.fit *.fts *.tif *.tiff *.png *.jpg *.jpeg);;Tutti i file (*)")

DESCRIPTIONS = {
    "light": ("Light", "Le foto del cielo (obbligatorie)"),
    "dark": ("Dark", "Stessa posa e ISO dei light, tappo sull'obiettivo"),
    "flat": ("Flat", "Campo uniforme: correggono vignettatura e polvere"),
    "bias": ("Bias / Offset", "Posa più breve possibile, tappo sull'obiettivo"),
}


class DropZone(QFrame):
    changed = Signal()
    manage = Signal()

    def __init__(self, kind: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.kind = kind
        self.files: list[str] = []
        self._hover = False
        self.color = TH.ZONE_COLORS[kind]
        self.setAcceptDrops(True)
        self.setProperty("role", "panel")
        self.setMinimumHeight(86)
        self.setToolTip(T.ZONES[kind])
        self.setToolTipDuration(60000)
        title, hint = DESCRIPTIONS[kind]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 10, 8)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setStyleSheet(f"color: {self.color}; font-weight: 700; font-size: 14px;")
        self.count = QLabel("nessun file")
        self.count.setProperty("role", "muted")
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.count)
        lay.addLayout(top)
        self.hint = QLabel(hint)
        self.hint.setProperty("role", "muted")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        btns = QHBoxLayout()
        btns.setSpacing(6)
        b1 = AnimatedButton("Aggiungi file", "link")
        b2 = AnimatedButton("Cartella", "link")
        b4 = AnimatedButton("Gestisci…", "link")
        b4.setToolTip(T.tip("Gestisci i file", "Elenco dei file di questa zona: puoi rimuoverne alcuni oppure "
                            "spostarli in un'altra zona (utile se lo smistamento automatico ha sbagliato)."))
        b4.clicked.connect(self.manage.emit)
        b3 = AnimatedButton("Svuota", "link")
        b1.clicked.connect(self.pick_files)
        b2.clicked.connect(self.pick_folder)
        b3.clicked.connect(self.clear)
        b1.setToolTip(T.tip("Aggiungi file", "Scegli uno o più file da aggiungere a questa zona."))
        b2.setToolTip(T.tip("Cartella", "Aggiunge tutti i file supportati della cartella (e delle sottocartelle)."))
        b3.setToolTip(T.tip("Svuota", "Toglie tutti i file da questa zona (i file su disco non vengono toccati)."))
        btns.addWidget(b1)
        btns.addWidget(b2)
        btns.addWidget(b4)
        btns.addStretch(1)
        btns.addWidget(b3)
        lay.addLayout(btns)
        self._flash = 0.0
        self._a_flash = QPropertyAnimation(self, b"flash", self)
        self._a_flash.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._apply_style()

    # ----------------------------------------------------------------- animazione
    def _get_flash(self) -> float:
        return self._flash

    def _set_flash(self, v: float):
        self._flash = float(v)
        self.update()

    flash = Property(float, _get_flash, _set_flash)

    def _animate_flash(self, target: float, ms: int):
        self._a_flash.stop()
        self._a_flash.setDuration(ms)
        self._a_flash.setStartValue(self._flash)
        self._a_flash.setEndValue(target)
        self._a_flash.start()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._flash > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            col = QColor(self.color)
            col.setAlphaF(0.32 * self._flash)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
            p.end()

    # ----------------------------------------------------------------- style
    def _apply_style(self):
        bg = TH.PANEL2 if self._hover else TH.PANEL
        border = self.color if (self._hover or self.files) else "#2E3A57"
        self.setStyleSheet(f"DropZone {{ background: {bg}; border: 1px solid {border}; border-left: 4px solid {self.color}; border-radius: 8px; }}")

    def _refresh_labels(self):
        n = len(self.files)
        self.count.setText(tr("nessun file") if n == 0 else tr(f"{n} file"))
        self.count.setStyleSheet(f"color: {self.color if n else TH.MUTED};")
        if n:
            folder = os.path.dirname(self.files[0])
            self.hint.setText(f"{os.path.basename(folder) or folder}  ·  {os.path.basename(self.files[0])} … {os.path.basename(self.files[-1])}"
                              if n > 1 else os.path.basename(self.files[0]))
        else:
            self.hint.setText(tr(DESCRIPTIONS[self.kind][1]))

    def _refresh(self):
        self._refresh_labels()
        self._apply_style()
        self.changed.emit()

    # ------------------------------------------------------------ operations
    def add_paths(self, paths):
        self._animate_flash(0.0, 650) if self._flash else None
        self._flash = 1.0
        self._animate_flash(0.0, 650)   # lampo colorato: conferma che i file sono arrivati
        new = collect_files(paths)
        existing = {os.path.normcase(os.path.abspath(p)) for p in self.files}
        for p in new:
            key = os.path.normcase(os.path.abspath(p))
            if key not in existing:
                self.files.append(p)
                existing.add(key)
        self.files.sort(key=lambda s: s.lower())
        self._refresh()

    def set_files(self, files):
        self.files = []
        self.add_paths(files)

    def remove_files(self, files):
        keep = {os.path.normcase(os.path.abspath(f)) for f in files}
        self.files = [f for f in self.files if os.path.normcase(os.path.abspath(f)) not in keep]
        self._refresh()

    def clear(self):
        self.files = []
        self._refresh()

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("Scegli i file") + f" {DESCRIPTIONS[self.kind][0]}", "", tr(FILTER))
        if files:
            self.add_paths(files)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr("Scegli la cartella dei") + f" {DESCRIPTIONS[self.kind][0]}")
        if d:
            self.add_paths([d])

    # ------------------------------------------------------------ drag&drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover = True
            self._apply_style()
            self._animate_flash(0.45, 160)

    def dragLeaveEvent(self, e):
        self._hover = False
        self._apply_style()
        self._animate_flash(0.0, 200)

    def dropEvent(self, e):
        self._hover = False
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        e.acceptProposedAction()
        self.add_paths(paths)
