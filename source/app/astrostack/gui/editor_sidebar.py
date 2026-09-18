"""Barra laterale dell'Editor standalone: sorgente, preset, snapshot e cronologia."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from .widgets import AnimatedButton


class EditorSidebar(QWidget):
    preset_requested = Signal(str)
    snapshot_requested = Signal()
    snapshot_restore_requested = Signal(str)

    PRESETS = (
        ("natural", "Naturale"),
        ("contrast", "Più contrasto"),
        ("nebula", "Nebulose vivaci"),
        ("detail", "Dettaglio massimo"),
        ("soft", "Versione morbida"),
        ("mono", "Mono / Ha"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)
        self.setMaximumWidth(330)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 6, 0)
        root.setSpacing(8)

        source = QFrame()
        source.setProperty("role", "panel")
        sl = QVBoxLayout(source)
        sl.setContentsMargins(12, 10, 12, 10)
        title = QLabel("Immagine sorgente")
        title.setProperty("role", "sectionTitle")
        sl.addWidget(title)
        self.source_name = QLabel("Nessuna immagine aperta")
        self.source_name.setWordWrap(True)
        self.source_name.setStyleSheet("font-weight: 600;")
        sl.addWidget(self.source_name)
        self.source_meta = QLabel("Apri TIFF, FITS, PNG, JPG o RAW per iniziare.")
        self.source_meta.setProperty("role", "muted")
        self.source_meta.setWordWrap(True)
        sl.addWidget(self.source_meta)
        root.addWidget(source)

        presets = QFrame()
        presets.setProperty("role", "panel")
        pl = QVBoxLayout(presets)
        pl.setContentsMargins(10, 10, 10, 10)
        ptitle = QLabel("Preset rapidi")
        ptitle.setProperty("role", "sectionTitle")
        pl.addWidget(ptitle)
        self.preset_list = QListWidget()
        self.preset_list.setAlternatingRowColors(False)
        self.preset_list.setSpacing(2)
        for key, label in self.PRESETS:
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.preset_list.addItem(it)
        self.preset_list.itemActivated.connect(self._preset)
        self.preset_list.itemClicked.connect(self._preset)
        pl.addWidget(self.preset_list)
        root.addWidget(presets)

        snaps = QFrame()
        snaps.setProperty("role", "panel")
        snl = QVBoxLayout(snaps)
        snl.setContentsMargins(10, 10, 10, 10)
        sr = QHBoxLayout()
        stitle = QLabel("Snapshot")
        stitle.setProperty("role", "sectionTitle")
        self.btn_snapshot = AnimatedButton("+", "link")
        self.btn_snapshot.setFixedWidth(32)
        self.btn_snapshot.setToolTip("Salva lo stato corrente dello sviluppo")
        self.btn_snapshot.clicked.connect(self.snapshot_requested.emit)
        sr.addWidget(stitle)
        sr.addStretch(1)
        sr.addWidget(self.btn_snapshot)
        snl.addLayout(sr)
        self.snapshot_list = QListWidget()
        self.snapshot_list.setMaximumHeight(150)
        self.snapshot_list.itemActivated.connect(self._snapshot)
        self.snapshot_list.itemDoubleClicked.connect(self._snapshot)
        snl.addWidget(self.snapshot_list)
        root.addWidget(snaps)

        history = QFrame()
        history.setProperty("role", "panel")
        hl = QVBoxLayout(history)
        hl.setContentsMargins(10, 10, 10, 10)
        htitle = QLabel("Cronologia modifiche")
        htitle.setProperty("role", "sectionTitle")
        hl.addWidget(htitle)
        self.history = QListWidget()
        self.history.setMaximumHeight(170)
        hl.addWidget(self.history)
        root.addWidget(history)
        root.addStretch(1)

    def _preset(self, item: QListWidgetItem):
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if key:
            self.preset_requested.emit(key)

    def _snapshot(self, item: QListWidgetItem):
        payload = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if payload:
            self.snapshot_restore_requested.emit(payload)

    def set_source(self, path: str | None, shape=None, is_linear: bool = False):
        if not path:
            self.source_name.setText("Stack corrente" if shape else "Nessuna immagine aperta")
        else:
            self.source_name.setText(os.path.basename(path))
        parts = []
        if shape and len(shape) >= 2:
            parts.append(f"{shape[1]} × {shape[0]} px")
        if path:
            ext = os.path.splitext(path)[1].lstrip(".").upper()
            if ext:
                parts.append(ext)
        parts.append("Lineare" if is_linear else "Non lineare")
        self.source_meta.setText("  ·  ".join(parts))

    def add_snapshot(self, params_json: str, name: str | None = None):
        if not name:
            name = datetime.now().strftime("Snapshot  %H:%M:%S")
        it = QListWidgetItem(name)
        it.setData(Qt.ItemDataRole.UserRole, params_json)
        self.snapshot_list.insertItem(0, it)
        while self.snapshot_list.count() > 20:
            self.snapshot_list.takeItem(self.snapshot_list.count() - 1)

    def snapshots(self) -> list[dict]:
        out = []
        for i in range(self.snapshot_list.count()):
            it = self.snapshot_list.item(i)
            row = {"name": it.text(), "params": str(it.data(Qt.ItemDataRole.UserRole) or "")}
            if not it.icon().isNull():
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                it.icon().pixmap(110, 65).save(buffer, "PNG")
                row["thumbnail"] = bytes(buffer.data().toBase64()).decode("ascii")
            out.append(row)
        return out

    def set_snapshots(self, items: list[dict]):
        self._restoring_snapshots = True
        try:
            self.snapshot_list.clear()
            # Insertion is at the front; reverse to preserve the saved order.
            for row in reversed(items or []):
                payload = str(row.get("params", ""))
                if payload:
                    self.add_snapshot(payload, str(row.get("name", "Snapshot")))
                    encoded = str(row.get("thumbnail", ""))
                    if encoded and len(encoded) < 200000:
                        pixmap = QPixmap()
                        pixmap.loadFromData(QByteArray.fromBase64(encoded.encode("ascii", errors="ignore")))
                        if not pixmap.isNull():
                            self.snapshot_list.item(0).setIcon(QIcon(pixmap))
        finally:
            self._restoring_snapshots = False

    def add_history(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.history.insertItem(0, f"{stamp}  {text}")
        while self.history.count() > 30:
            self.history.takeItem(self.history.count() - 1)

    def clear_history(self):
        self.history.clear()
