"""Finestra Informazioni e Diagnostica di AstroStack."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from astrostack import __version__
from astrostack.diagnostics import (
    latest_crash_report,
    logs_dir,
    system_info_text,
)

PROJECT_URL = "https://github.com/GodEater58/Atrostack"


def _open_path(path: Path) -> bool:
    """Apre file/cartella con il gestore nativo del sistema operativo."""
    try:
        path = path.resolve()
        if not path.exists():
            return False

        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


class AboutDiagnosticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Informazioni su AstroStack")
        self.setMinimumWidth(640)
        self.resize(700, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        title = QLabel("AstroStack")
        title.setProperty("role", "title")
        root.addWidget(title)

        version = QLabel(f"Versione {__version__}")
        version.setProperty("role", "muted")
        root.addWidget(version)

        privacy = QLabel(
            "I report diagnostici vengono salvati solo sul tuo PC. "
            "AstroStack non li invia automaticamente."
        )
        privacy.setWordWrap(True)
        root.addWidget(privacy)

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setPlainText(system_info_text())
        self.info.setMinimumHeight(250)
        root.addWidget(self.info, 1)

        row1 = QHBoxLayout()
        self.btn_logs = QPushButton("Apri cartella log")
        self.btn_crash = QPushButton("Apri ultimo crash report")
        self.btn_copy = QPushButton("Copia informazioni")
        row1.addWidget(self.btn_logs)
        row1.addWidget(self.btn_crash)
        row1.addWidget(self.btn_copy)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_github = QPushButton("Apri GitHub")
        self.btn_close = QPushButton("Chiudi")
        row2.addWidget(self.btn_github)
        row2.addStretch(1)
        row2.addWidget(self.btn_close)
        root.addLayout(row2)

        self.btn_logs.clicked.connect(self._open_logs)
        self.btn_crash.clicked.connect(self._open_crash)
        self.btn_copy.clicked.connect(self._copy_info)
        self.btn_github.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(PROJECT_URL))
        )
        self.btn_close.clicked.connect(self.accept)

        self._refresh_crash_button()

    def _refresh_crash_button(self) -> None:
        report = latest_crash_report()
        self.btn_crash.setEnabled(report is not None)
        if report is None:
            self.btn_crash.setToolTip("Nessun crash report trovato")
        else:
            self.btn_crash.setToolTip(str(report))

    def _open_logs(self) -> None:
        if not _open_path(logs_dir()):
            QMessageBox.warning(
                self,
                "Diagnostica",
                "Non è stato possibile aprire la cartella dei log.",
            )

    def _open_crash(self) -> None:
        report = latest_crash_report()
        if report is None:
            self._refresh_crash_button()
            return
        if not _open_path(report):
            QMessageBox.warning(
                self,
                "Diagnostica",
                "Non è stato possibile aprire il crash report.",
            )

    def _copy_info(self) -> None:
        text = system_info_text()
        QGuiApplication.clipboard().setText(text)
        self.info.setPlainText(text)
        self.btn_copy.setText("Copiato")
