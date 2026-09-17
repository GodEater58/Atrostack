"""Finestra principale di AstroStack."""
from __future__ import annotations

import os
import re
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPlainTextEdit, QScrollArea, QSizePolicy, QSlider,
                               QSplitter, QVBoxLayout, QWidget)

from .. import __version__
from ..core.io_out import save_result
from ..core.loader import collect_files
from ..core.pipeline import FrameInfo, Settings, StackResult
from .dropzone import DropZone
from .frames_table import FramesTable
from .preview import ImageView
from .settings_panel import SettingsPanel
from . import theme as TH
from .worker import (CompositeWorker, DevelopWorker, ExportWorker, PostWorker, RenderWorker, StackWorker,
                     ToolWorker, render_preview)
from .layers_panel import LayersPanel
from .dialogs import BatchDialog, FileManagerDialog, GuideDialog
from ..core.report import write_report
from ..core.pipeline import extend_live_stack, restack
from ..core.layers import Layer, composite, invalidate, paint_brush
from ..core import project as project_io
from ..core.sorter import classify_files
from .develop_panel import DevelopPanel
from .editor_sidebar import EditorSidebar
from .export_dialog import ExportDialog
from ..core.develop import EXT_FOR_FMT, DevelopParams, assisted_develop, auto_tone
from .tools_panel import ToolsPanel
from ..core import ai_tools
from . import tooltips as T
from .widgets import AnimatedButton, LangSwitch, SmoothProgressBar, Toast, TrLabel
from .i18n import retranslate, set_language, tr
from . import i18n

SESSION_DIRS = {
    "light": re.compile(r"^(light|lights|luci|luce|l)$", re.I),
    "dark": re.compile(r"^(dark|darks|d)$", re.I),
    "flat": re.compile(r"^(flat|flats|f)$", re.I),
    "bias": re.compile(r"^(bias|biases|offset|offsets|b|o)$", re.I),
}
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AstroStack {__version__}")
        self.resize(1380, 860)
        self.worker: Optional[StackWorker] = None
        self.post_worker: Optional[PostWorker] = None
        self.render_worker: Optional[RenderWorker] = None
        self.result: Optional[StackResult] = None
        self.current_image: Optional[np.ndarray] = None
        self.stretch = True
        self.nonlinear = False              # True dopo StarNet (immagine già stirata)
        self.stars_image: Optional[np.ndarray] = None
        self.annotations: list = []
        self.preview_scale = 1.0
        self._undo: list = []
        self.tool_worker: Optional[ToolWorker] = None
        self.opened_path: Optional[str] = None
        self.layers: list[Layer] = []
        self.layer_proxies: list[np.ndarray] = []
        self.before_rgb8: Optional[np.ndarray] = None
        self.after_rgb8: Optional[np.ndarray] = None
        self.live_dir: Optional[str] = None
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(5000)
        self.live_timer.timeout.connect(self._live_poll)
        self._live_pending: set[str] = set()
        self.project_path: Optional[str] = None
        self.workspace = "stack"
        self._dev_undo: list = []
        self._dev_redo: list = []
        self._eta_t0 = 0.0
        self._eta_step = ""
        self.excluded: set = set()
        self._batch: list = []
        self._batch_opts: dict = {}
        self.comp_worker: Optional[CompositeWorker] = None
        self._paint_dirty = False
        self.proxy: Optional[np.ndarray] = None
        self.dev_params: DevelopParams = DevelopParams()
        self.dev_worker: Optional[DevelopWorker] = None
        self._dev_pending = False
        self._dev_full = False
        self.export_worker: Optional[ExportWorker] = None
        self._dev_timer = QTimer(self)
        self._dev_timer.setSingleShot(True)
        self._dev_timer.setInterval(110)
        self._dev_timer.timeout.connect(lambda: self._refresh_preview(full=False))
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(650)
        self._history_timer.timeout.connect(self._commit_editor_history)
        self._pending_history = ""
        qs = QSettings("AstroStack", "AstroStack")
        saved = str(qs.value("language", "it"))
        set_language("en" if saved.startswith("en") else "it")
        TH.set_theme(str(qs.value("theme", "scuro")))
        self._build_ui()
        self._restore_geometry()
        if i18n.language() == "en":
            retranslate(self)
        self.btn_theme.setText("☀" if TH.THEME == "scuro" else "☾")
        QTimer.singleShot(400, self._maybe_show_guide)

    def _maybe_show_guide(self):
        qs = QSettings("AstroStack", "AstroStack")
        if str(qs.value("guide_seen", "0")) == "1":
            return
        dlg = GuideDialog(self)
        retranslate(dlg)
        dlg.exec()
        qs.setValue("guide_seen", "1" if dlg.dont_show.isChecked() else "0")

    def _last_dir(self, key: str = "last_dir") -> str:
        return str(QSettings("AstroStack", "AstroStack").value(key, "") or "")

    def _remember_dir(self, path: str, key: str = "last_dir"):
        if path:
            QSettings("AstroStack", "AstroStack").setValue(key, os.path.dirname(path) if os.path.isfile(path) else path)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # intestazione
        head = QHBoxLayout()
        self.context_bar = QWidget()
        context = QHBoxLayout(self.context_bar)
        context.setContentsMargins(0, 0, 0, 0)
        context.setSpacing(6)
        logo = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "astrostack.ico")
        if os.path.isfile(icon_path):
            from PySide6.QtGui import QIcon
            logo.setPixmap(QIcon(icon_path).pixmap(28, 28))
            head.addWidget(logo)
        title = QLabel("AstroStack")
        title.setProperty("role", "title")
        sub = QLabel("Stacking e sviluppo astrofotografico, nello stesso flusso.")
        sub.setProperty("role", "muted")
        head.addWidget(title)
        head.addSpacing(12)
        head.addWidget(sub)
        head.addStretch(1)

        # Modalità principali: lo sviluppo è un editor vero e proprio, non
        # una fase obbligatoriamente successiva allo stack.
        self.btn_mode_stack = AnimatedButton("Stack")
        self.btn_mode_stack.setCheckable(True)
        self.btn_mode_editor = AnimatedButton("Editor")
        self.btn_mode_editor.setCheckable(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.btn_mode_stack)
        self.mode_group.addButton(self.btn_mode_editor)
        self.btn_mode_stack.setChecked(True)
        self.btn_mode_stack.clicked.connect(lambda: self._set_workspace("stack"))
        self.btn_mode_editor.clicked.connect(self._enter_editor)
        head.addWidget(self.btn_mode_stack)
        head.addWidget(self.btn_mode_editor)
        head.addSpacing(8)
        self.btn_proj_open = AnimatedButton("Apri progetto…")
        self.btn_proj_save = AnimatedButton("Salva progetto…")
        self.btn_batch = AnimatedButton("Lotti…")
        self.btn_batch.setToolTip(T.tip("Elaborazione a lotti", "Elabora più sessioni una dopo l'altra con le "
                                        "impostazioni attuali: lanci e vai a dormire."))
        self.btn_batch.clicked.connect(self.run_batch)
        self.btn_report = AnimatedButton("Report…")
        self.btn_report.setToolTip(T.tip("Report della sessione", "Salva una pagina HTML con statistiche, grafici, "
                                         "anteprima e tabella dei frame: da consultare o condividere."))
        self.btn_report.clicked.connect(self.save_report)
        self.btn_report.setEnabled(False)
        self.btn_theme = AnimatedButton("☀")
        self.btn_theme.setFixedWidth(40)
        self.btn_theme.setToolTip(T.tip("Tema", "Passa dal tema notturno a quello chiaro e viceversa."))
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.btn_sort = AnimatedButton("Smista file…")
        self.btn_live = AnimatedButton("Live")
        self.btn_live.setCheckable(True)
        self.btn_proj_open.clicked.connect(self.open_project)
        self.btn_proj_save.clicked.connect(self.save_project)
        self.btn_sort.clicked.connect(self.sort_files)
        self.btn_live.toggled.connect(self._toggle_live)
        for b, key in ((self.btn_proj_open, "project_open"), (self.btn_proj_save, "project_save"),
                       (self.btn_sort, "sort"), (self.btn_live, "live")):
            b.setToolTip(T.BUTTONS[key])
            b.setToolTipDuration(60000)
        head.addWidget(self.btn_proj_open)
        head.addWidget(self.btn_proj_save)
        context.addWidget(self.btn_sort)
        context.addWidget(self.btn_live)
        context.addWidget(self.btn_batch)
        context.addWidget(self.btn_report)
        self.btn_open = AnimatedButton("Apri immagine…")
        self.btn_open.setToolTip(T.tip("Apri immagine", "Apre un TIFF, PNG, JPG o FITS già pronto per svilupparlo "
                                       "con il pannello Sviluppo ed esportarlo, senza fare lo stack."))
        self.btn_open.clicked.connect(self.open_image)
        head.addWidget(self.btn_open)
        self.btn_session = AnimatedButton("Importa sessione…")
        self.btn_session.clicked.connect(self.import_session)
        self.btn_frames = AnimatedButton("Frame")
        self.btn_frames.setCheckable(True)
        self.btn_log = AnimatedButton("Registro")
        self.btn_log.setCheckable(True)
        self.btn_develop = AnimatedButton("Sviluppo")
        self.btn_develop.setCheckable(True)
        context.addWidget(self.btn_session)
        context.addWidget(self.btn_frames)
        context.addWidget(self.btn_log)
        head.addSpacing(10)
        self.lang_switch = LangSwitch(QSettings("AstroStack", "AstroStack").value("language", "it"))
        self.lang_switch.setToolTip(T.tip("Lingua", "Cambia la lingua dell'interfaccia in tempo reale: "
                                          "italiano o inglese."))
        self.lang_switch.changed.connect(self.set_language)
        head.addWidget(self.lang_switch)
        head.addWidget(self.btn_theme)
        context.addWidget(self.btn_develop)
        root.addLayout(head)
        rule = QFrame()
        rule.setFixedHeight(2)
        rule.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {TH.ACCENT}, stop:0.35 #6A5A32, stop:1 transparent); border: none;")
        root.addWidget(rule)
        root.addWidget(self.context_bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        # colonna sinistra
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.setSpacing(8)
        self.zones = {k: DropZone(k) for k in ("light", "dark", "flat", "bias")}
        for k, z in self.zones.items():
            z.changed.connect(lambda: self._update_ready(from_zones=True))
            z.manage.connect(lambda kind=k: self.manage_files(kind))
            ll.addWidget(z)
        self.settings_panel = SettingsPanel()
        self.settings_panel.post_changed.connect(self._post_changed)
        ll.addWidget(self.settings_panel)
        self.tools = ToolsPanel()
        self.tools.run_tool.connect(self._run_tool)
        self.tools.undo.connect(self._undo_tool)
        self.tools.labels_toggled.connect(lambda on: self.view.show_annotations(on))
        ll.addWidget(self.tools)
        ll.addStretch(1)
        # il contenuto si adatta SEMPRE alla larghezza disponibile (niente tagli a destra)
        left.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setMinimumWidth(370)
        scroll.setMaximumWidth(600)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack_sidebar_scroll = scroll
        split.addWidget(scroll)

        # colonna sinistra alternativa dell'Editor. Condividiamo lo stesso
        # splitter: in ogni modalità resta visibile una sola sidebar.
        self.editor_sidebar = EditorSidebar()
        self.editor_sidebar.preset_requested.connect(self._apply_editor_preset)
        self.editor_sidebar.snapshot_requested.connect(self._add_editor_snapshot)
        self.editor_sidebar.snapshot_restore_requested.connect(self._restore_editor_snapshot)
        split.addWidget(self.editor_sidebar)
        self.editor_sidebar.hide()

        # centro: anteprima
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(6, 0, 0, 0)
        cl.setSpacing(6)
        prow = QHBoxLayout()
        self.preview_label = TrLabel("Nessuna anteprima: carica i light e premi Stack.")
        self.preview_label.setProperty("role", "muted")
        prow.addWidget(self.preview_label)
        prow.addStretch(1)
        self.btn_stretch = AnimatedButton("Sviluppo", "link")
        self.btn_stretch.setCheckable(True)
        self.btn_stretch.setChecked(True)
        self.btn_stretch.toggled.connect(self._toggle_stretch)
        self.btn_compare = AnimatedButton("Prima / Dopo", "link")
        self.btn_compare.setCheckable(True)
        self.btn_compare.setToolTip(T.BUTTONS["compare"])
        self.btn_compare.toggled.connect(self._toggle_compare)
        self.compare_slider = QSlider(Qt.Orientation.Horizontal)
        self.compare_slider.setRange(0, 100)
        self.compare_slider.setValue(50)
        self.compare_slider.setFixedWidth(140)
        self.compare_slider.setVisible(False)
        self.compare_slider.valueChanged.connect(lambda *_: self._show_compare())
        prow.addWidget(self.btn_compare)
        prow.addWidget(self.compare_slider)
        self.btn_fit = AnimatedButton("Adatta", "link")
        self.btn_100 = AnimatedButton("100 %", "link")
        for b in (self.btn_stretch, self.btn_fit, self.btn_100):
            prow.addWidget(b)
        cl.addLayout(prow)
        self.view = ImageView()
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn_fit.clicked.connect(lambda: self.view.fit(animated=True))
        self.btn_100.clicked.connect(self._zoom_100)
        frame = QFrame()
        frame.setProperty("role", "preview")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.addWidget(self.view)
        cl.addWidget(frame, 1)
        self.toast = Toast(frame)

        # barra inferiore
        self.progress = SmoothProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        cl.addWidget(self.progress)
        brow = QHBoxLayout()
        self.status = TrLabel("Pronto.")
        self.status.setProperty("role", "muted")
        self.status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        brow.addWidget(self.status, 1)
        self.btn_stack = AnimatedButton("▶  Stack", "primary")
        self.btn_stack.setEnabled(False)
        self.btn_stack.clicked.connect(self.start_stack)
        self.btn_restack = AnimatedButton("Ricombina")
        self.btn_restack.setToolTip(T.tip("Ricombina", "Rifà solo la somma dei frame già calibrati e allineati "
                                          "(pochi secondi): serve per cambiare metodo, kappa o escludere frame "
                                          "senza rifare tutto. Richiede 'Tieni i frame in cache'."))
        self.btn_restack.setEnabled(False)
        self.btn_restack.clicked.connect(self.restack_now)
        self.btn_cancel = AnimatedButton("Annulla")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_stack)
        self.btn_save = AnimatedButton("Esporta…")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_result)
        brow.addWidget(self.btn_stack)
        brow.addWidget(self.btn_restack)
        brow.addWidget(self.btn_cancel)
        brow.addWidget(self.btn_save)
        cl.addLayout(brow)
        split.addWidget(center)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 0)
        split.setStretchFactor(2, 1)
        split.setSizes([420, 0, 1000])
        self.setCentralWidget(central)

        # dock: tabella frame + registro
        self.table = FramesTable()
        self.table.frame_toggled.connect(self.toggle_frame)
        self.table.frame_activated.connect(self.inspect_frame)
        self.dock_frames = QDockWidget("Frame", self)
        self.dock_frames.setWidget(self.table)
        self.dock_frames.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_frames)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.dock_log = QDockWidget("Registro", self)
        self.dock_log.setWidget(self.log_view)
        self.dock_log.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_log)
        self.tabifyDockWidget(self.dock_frames, self.dock_log)
        self.dock_frames.hide()
        self.dock_log.hide()
        # pannello di sviluppo (a destra, come in Lightroom)
        self.develop_panel = DevelopPanel()
        self.dev_params = self.develop_panel.params()
        self.develop_panel.params_changed.connect(self._on_dev_params)
        self.develop_panel.auto_requested.connect(self._auto_tone)
        self.develop_panel.assist_requested.connect(self._assist_develop)
        self.dock_develop = QDockWidget("Sviluppo", self)
        self.dock_develop.setWidget(self.develop_panel)
        self.dock_develop.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_develop.setMinimumWidth(360)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_develop)
        self.dock_develop.hide()
        self.btn_develop.toggled.connect(self.dock_develop.setVisible)
        self.dock_develop.visibilityChanged.connect(lambda v: self.btn_develop.setChecked(v))
        # livelli
        self.layers_panel = LayersPanel()
        self.dock_layers = QDockWidget("Livelli", self)
        self.dock_layers.setWidget(self.layers_panel)
        self.dock_layers.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_layers.setMinimumWidth(360)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_layers)
        self.tabifyDockWidget(self.dock_develop, self.dock_layers)
        self.dock_layers.hide()
        self.btn_layers = AnimatedButton("Livelli")
        self.btn_layers.setCheckable(True)
        self.btn_layers.setToolTip(T.tip("Livelli", "Fonde più foto: ad esempio il cielo stackato con uno scatto del primo "
                                         "piano, con maschere, opacità e metodi di fusione come in Photoshop."))
        self.btn_layers.toggled.connect(self.dock_layers.setVisible)
        self.dock_layers.visibilityChanged.connect(lambda v: self.btn_layers.setChecked(v))
        context.addWidget(self.btn_layers)
        context.addStretch(1)
        self.layers_panel.changed.connect(self._layers_changed)
        self.layers_panel.selection_changed.connect(self._layer_selected)
        self.layers_panel.add_requested.connect(self.add_layer)
        self.layers_panel.duplicate_requested.connect(self.duplicate_layer)
        self.layers_panel.delete_requested.connect(self.delete_layer)
        self.layers_panel.move_requested.connect(self.move_layer)
        self.layers_panel.paint_mode_changed.connect(self.view.set_paint_mode)
        self.layers_panel.show_mask_changed.connect(lambda *_: self._refresh_preview(full=False))
        self.layers_panel.clear_brush_requested.connect(self.clear_brush)
        self.layers_panel.load_mask_requested.connect(self.load_mask_file)
        self.view.paint_at.connect(self._paint_at)
        self.view.sampled.connect(self._sample_point)
        self.develop_panel.btn_pick.toggled.connect(self.view.set_sample_mode)
        self.view.paint_done.connect(lambda: self._refresh_preview(full=False))
        self.btn_develop.setToolTip(T.tip("Sviluppo", "Apre il pannello con le regolazioni stile Lightroom "
                                          "(tono, colore, dettaglio, curva, geometria). Ctrl+D."))
        act_dev = QAction("Sviluppo", self)
        act_dev.setShortcut(QKeySequence("Ctrl+D"))
        act_dev.triggered.connect(lambda: self.btn_develop.setChecked(not self.btn_develop.isChecked()))
        self.addAction(act_dev)
        self.btn_frames.toggled.connect(self.dock_frames.setVisible)
        self.btn_log.toggled.connect(self.dock_log.setVisible)
        self.dock_frames.visibilityChanged.connect(lambda v: self.btn_frames.setChecked(v))
        self.dock_log.visibilityChanged.connect(lambda v: self.btn_log.setChecked(v))

        # popup di spiegazione sui pulsanti
        for btn, key in ((self.btn_stack, "stack"), (self.btn_cancel, "cancel"), (self.btn_save, "save"),
                         (self.btn_stretch, "stretch"), (self.btn_fit, "fit"), (self.btn_100, "zoom100"),
                         (self.btn_session, "session"), (self.btn_frames, "frames"), (self.btn_log, "log")):
            btn.setToolTip(T.BUTTONS[key])
            btn.setToolTipDuration(60000)

        # scorciatoie
        act = QAction("Stack", self)
        act.setShortcut(QKeySequence("Ctrl+Return"))
        act.triggered.connect(lambda: self.btn_stack.isEnabled() and self.start_stack())
        self.addAction(act)
        act_undo = QAction("Annulla sviluppo", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self.undo_develop)
        self.addAction(act_undo)
        act_redo = QAction("Ripeti sviluppo", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self.redo_develop)
        self.addAction(act_redo)
        act_cmp = QAction("Prima/Dopo", self)
        act_cmp.setShortcut(QKeySequence(Qt.Key.Key_Space))
        act_cmp.triggered.connect(lambda: self.btn_compare.setChecked(not self.btn_compare.isChecked()))
        self.addAction(act_cmp)
        act2 = QAction("Salva", self)
        act2.setShortcut(QKeySequence.StandardKey.Save)
        act2.triggered.connect(lambda: self.btn_save.isEnabled() and self.save_result())
        self.addAction(act2)
        self.setAcceptDrops(True)
        self._set_workspace("stack")

    def _enter_editor(self):
        """Entra nell'editor; se non c'è un'immagine propone di aprirne una."""
        self._set_workspace("editor")
        if self.current_image is None:
            self.open_image()

    def _set_workspace(self, mode: str):
        """Commuta tra il banco di stacking e l'editor standalone.

        I due ambienti condividono l'anteprima e il motore di sviluppo, ma
        mostrano solo i controlli pertinenti. Questo mantiene l'interfaccia
        leggibile anche a 1366x768 e rende esplicito che l'Editor può vivere
        senza alcuno stack.
        """
        mode = "editor" if mode == "editor" else "stack"
        self.workspace = mode
        editor = mode == "editor"
        if hasattr(self, "btn_mode_stack"):
            self.btn_mode_stack.setChecked(not editor)
            self.btn_mode_editor.setChecked(editor)
        if hasattr(self, "stack_sidebar_scroll"):
            self.stack_sidebar_scroll.setVisible(not editor)
        if hasattr(self, "editor_sidebar"):
            self.editor_sidebar.setVisible(editor)
        # azioni specifiche dello stacking
        for w in (getattr(self, "btn_stack", None), getattr(self, "btn_restack", None),
                  getattr(self, "btn_cancel", None)):
            if w is not None:
                w.setVisible(not editor)
        for w in (getattr(self, "btn_session", None), getattr(self, "btn_sort", None),
                  getattr(self, "btn_live", None), getattr(self, "btn_batch", None),
                  getattr(self, "btn_frames", None), getattr(self, "btn_log", None),
                  getattr(self, "btn_report", None)):
            if w is not None:
                w.setVisible(not editor)
        # nell'Editor l'apertura immagine è un'azione primaria e il pannello
        # Sviluppo rimane disponibile; nello Stack basta il tab Editor.
        if hasattr(self, "btn_open"):
            self.btn_open.setVisible(editor)
        if hasattr(self, "progress"):
            self.progress.setVisible(not editor)
        if editor:
            if hasattr(self, "dock_frames"):
                self.dock_frames.hide()
            if hasattr(self, "dock_log"):
                self.dock_log.hide()
            if self.current_image is not None:
                self.dock_develop.show()
                self.editor_sidebar.set_source(self.opened_path if self.result is None else None,
                                               self.current_image.shape, is_linear=not self.nonlinear)
            if self.opened_path and self.result is None:
                self.preview_label.setText(os.path.basename(self.opened_path) + "  ·  Editor standalone")
        else:
            if self.result is not None:
                self.preview_label.setText(f"Risultato stack  ·  {self.result.n_used} frame")
            elif self.current_image is None:
                self.preview_label.setText("Nessuna anteprima: carica i light e premi Stack.")

    def _apply_editor_preset(self, key: str):
        """Preset rapidi non distruttivi dell'Editor."""
        p = DevelopParams()
        linear = not self.nonlinear
        if linear:
            p.stretch_type = "arcsinh"
            p.stretch_bg = 23.0
        if key == "natural":
            p.vibrance, p.clarity = 8.0, 5.0
        elif key == "contrast":
            p.contrast, p.blacks, p.clarity, p.dehaze = 20.0, -10.0, 15.0, 8.0
        elif key == "nebula":
            p.contrast, p.vibrance, p.saturation = 12.0, 28.0, 10.0
            p.clarity, p.dehaze, p.nr_luminance = 12.0, 16.0, 10.0
        elif key == "detail":
            p.clarity, p.sharpen, p.wavelet_small = 25.0, 45.0, 20.0
            p.nr_luminance, p.deconv = 15.0, 15.0
        elif key == "soft":
            p.contrast, p.highlights, p.clarity = -8.0, -15.0, -8.0
            p.nr_luminance, p.nr_color, p.sharpen = 22.0, 18.0, 8.0
        elif key == "mono":
            p.saturation, p.contrast, p.clarity, p.dehaze = -100.0, 18.0, 18.0, 12.0
        self.develop_panel.set_params(p, emit=True)
        labels = dict(EditorSidebar.PRESETS)
        self.editor_sidebar.add_history("Preset: " + labels.get(key, key))
        self.toast.show_message("Preset applicato: " + labels.get(key, key))

    def _add_editor_snapshot(self):
        if self.current_image is None:
            return
        self.editor_sidebar.add_snapshot(self.dev_params.to_json())
        self.editor_sidebar.add_history("Creato snapshot")
        self.toast.show_message("Snapshot creato")

    def _restore_editor_snapshot(self, params_json: str):
        try:
            p = DevelopParams.from_json(params_json)
        except Exception:
            return
        self.develop_panel.set_params(p, emit=True)
        self.editor_sidebar.add_history("Ripristinato snapshot")
        self.toast.show_message("Snapshot ripristinato")

    def _queue_editor_history(self, previous: DevelopParams, current: DevelopParams):
        if not hasattr(self, "editor_sidebar") or self.workspace != "editor":
            return
        try:
            import json
            a, b = json.loads(previous.to_json()), json.loads(current.to_json())
            changed = [k for k in b if a.get(k) != b.get(k)]
        except Exception:
            changed = []
        names = {
            "exposure": "Esposizione", "contrast": "Contrasto", "highlights": "Alte luci",
            "shadows": "Ombre", "whites": "Bianchi", "blacks": "Neri", "temperature": "Temperatura",
            "tint": "Tinta", "vibrance": "Vividezza", "saturation": "Saturazione", "clarity": "Chiarezza",
            "dehaze": "Riduci velatura", "sharpen": "Nitidezza", "nr_luminance": "Riduzione rumore",
            "star_reduce": "Riduzione stelle", "deconv": "Deconvoluzione", "rotation": "Rotazione",
            "crop": "Ritaglio", "curve": "Curva dei toni", "stretch_type": "Tipo di stretch",
            "stretch_bg": "Stretch", "hsl_h": "HSL tonalità", "hsl_s": "HSL saturazione", "hsl_l": "HSL luminanza",
        }
        if changed:
            self._pending_history = names.get(changed[0], changed[0].replace("_", " ").title())
            self._history_timer.start()

    def _commit_editor_history(self):
        if self._pending_history and hasattr(self, "editor_sidebar"):
            self.editor_sidebar.add_history(self._pending_history)
        self._pending_history = ""

    # ------------------------------------------------------------ lingua
    def set_language(self, code: str):
        set_language(code)
        QSettings("AstroStack", "AstroStack").setValue("language", i18n.language())
        retranslate(self)
        for dock, it_title in ((self.dock_frames, "Frame"), (self.dock_log, "Registro"),
                               (self.dock_develop, "Sviluppo"), (self.dock_layers, "Livelli")):
            dock.setWindowTitle(tr(it_title))
        self.setWindowTitle(f"AstroStack {__version__}")
        self.layers_panel.set_layers(self.layers, select=self.layers_panel.current_index()) if self.layers else None
        self.toast.show_message("Lingua: italiano" if i18n.language() == "it" else "Language: English")

    # ------------------------------------------------------------ drag&drop globale
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if self.workspace == "editor" and len(paths) == 1 and os.path.isfile(paths[0]):
            self.open_image_path(paths[0])
            e.acceptProposedAction()
            return
        dirs = [p for p in paths if os.path.isdir(p)]
        if len(dirs) == 1 and len(paths) == 1 and self._looks_like_session(dirs[0]):
            self.import_session(dirs[0])
        else:
            self.sort_files(paths)          # smistamento automatico in light / dark / flat / bias

    # ------------------------------------------------------------ sessione
    @staticmethod
    def _looks_like_session(folder: str) -> bool:
        try:
            names = [n for n in os.listdir(folder) if os.path.isdir(os.path.join(folder, n))]
        except OSError:
            return False
        return any(SESSION_DIRS[k].match(n) for n in names for k in SESSION_DIRS)

    def import_session(self, folder: Optional[str] = None):
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, tr("Cartella della sessione (con light / dark / flat / bias)"))
            if not folder:
                return
        found = {k: [] for k in self.zones}
        for name in sorted(os.listdir(folder)):
            p = os.path.join(folder, name)
            if not os.path.isdir(p):
                continue
            for k, rx in SESSION_DIRS.items():
                if rx.match(name):
                    found[k].append(p)
        if not any(found.values()):
            self.zones["light"].set_files([folder])
            self._log(f"Sessione: nessuna sottocartella light/dark/flat/bias in {folder}: tutti i file usati come light")
            return
        for k, dirs in found.items():
            if dirs:
                self.zones[k].set_files(dirs)
        self._log("Sessione importata: " + ", ".join(f"{k} {len(self.zones[k].files)}" for k in self.zones))

    # ------------------------------------------------------------ stato
    def _update_ready(self, from_zones: bool = False):
        n = len(self.zones["light"].files)
        running = self.worker is not None and self.worker.isRunning()
        self.btn_stack.setEnabled(n > 0 or running)   # durante il lavoro resta acceso (con bagliore)
        if not running and (from_zones or self.result is None and not self.status.text().startswith(("Annullato", "Stacking non"))):
            self.status.setText(f"{n} light pronti." if n else "Pronto: aggiungi almeno un light.")
            self.status.setStyleSheet(f"color: {TH.MUTED};")

    def _set_running(self, running: bool):
        for z in self.zones.values():
            z.setEnabled(not running)
        self.settings_panel.setEnabled(not running)
        self.btn_session.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.btn_save.setEnabled(self.current_image is not None and not running)
        self.tools.set_ready(self.current_image is not None and not running, busy=self._tool_busy())
        self.btn_stack.set_busy(running)
        self.btn_stack.setText("In elaborazione…" if running else "▶  Stack")
        if running:
            self.btn_stack.setEnabled(True)
        else:
            self._update_ready()

    def _log(self, msg: str):
        self.log_view.appendPlainText(tr(msg))

    # ------------------------------------------------------------ stacking
    def start_stack(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self._set_workspace("stack")
        lights = list(self.zones["light"].files)
        if not lights:
            return
        settings = self.settings_panel.to_settings()
        settings.excluded = tuple(self.excluded)
        if not getattr(self, "_batch_folder", ""):
            warnings = self._coherence_warnings()
            if warnings:
                text = tr("Controlla questi punti prima di continuare:") + "\n\n· " + "\n· ".join(tr(x) for x in warnings)
                r = QMessageBox.question(self, tr("Controllo dei file"),
                                         text + "\n\n" + tr("Vuoi procedere lo stesso?"),
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if r != QMessageBox.StandardButton.Yes:
                    return
        self.settings_panel.save()
        if self.result is not None:
            self.result.cleanup()
        self.result = None
        self.current_image = None
        self.nonlinear = False
        self.stars_image = None
        self.annotations = []
        self._undo = []
        self.layers = []
        self.layer_proxies = []
        if hasattr(self, "editor_sidebar"):
            self.editor_sidebar.set_snapshots([])
            self.editor_sidebar.clear_history()
        self.view.clear_annotations()
        self.tools.set_ready(False)
        self.tools.set_undo(False)
        self.table.reset_frames(lights)
        self.dock_frames.show()
        self.dock_frames.raise_()
        self.log_view.clear()
        self._log(f"Avvio: {len(lights)} light, {len(self.zones['dark'].files)} dark, "
                  f"{len(self.zones['flat'].files)} flat, {len(self.zones['bias'].files)} bias")
        self.worker = StackWorker(lights, self.zones["dark"].files, self.zones["flat"].files,
                                  self.zones["bias"].files, settings, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.preview.connect(self._on_preview)
        self.worker.frame.connect(self.table.update_frame)
        self.worker.log.connect(self._log)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.finished.connect(self._on_thread_finished)   # il QThread è davvero terminato
        self.progress.setValue(0)
        self._eta_step, self._eta_start = "", time.time()
        self.btn_restack.setEnabled(False)
        self.btn_report.setEnabled(False)
        self.status.setText("Avvio…")
        self._set_running(True)
        self.worker.start()

    def cancel_stack(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Annullamento in corso…")
            self.btn_cancel.setEnabled(False)

    def _on_thread_finished(self):
        self._set_running(False)

    def _on_progress(self, step: str, done: int, total: int, msg: str):
        pct = int(100 * done / total) if total else 0
        self.progress.set_smooth(pct)
        text = f"{step}  {done}/{total}" if total > 1 else step
        if msg:
            text += f"  ·  {msg}"
        if step != self._eta_step:
            self._eta_step, self._eta_start = step, time.time()
        eta = self._estimate_eta(done, total)
        if eta:
            text += f"  ·  {eta}"
        self.status.setText(text)

    def _estimate_eta(self, done: int, total: int) -> str:
        """Tempo rimanente stimato per la fase in corso."""
        if total < 2 or done < 1 or done >= total:
            return ""
        elapsed = time.time() - getattr(self, "_eta_start", time.time())
        if elapsed < 2.0:
            return ""
        remaining = elapsed / done * (total - done)
        if remaining < 5:
            return ""
        return f"~{int(remaining)} s rimanenti" if remaining < 90 else f"~{remaining / 60:.0f} min rimanenti"

    def _on_preview(self, rgb8: np.ndarray, text: str):
        self.view.set_image(rgb8)
        self.preview_label.setText(text)

    def _on_finished(self, res: StackResult):
        self.result = res
        self.progress.setValue(100)
        g = res.gradient
        used = f"{res.n_used} frame su {len(res.frames)}"
        self.status.setText(f"Completato in {res.elapsed:.0f} s: {used}  ·  {g.describe()}"
                            + ("  ·  corretto" if g.applied else "")
                            + (f"  ·  {g.describe_color()}" if g.color_mult else ""))
        self.status.setStyleSheet(f"color: {TH.OK};")
        self.preview_label.setText("Risultato finale  ·  " + used)
        for f in res.frames:
            self.table.update_frame(f)
        self._set_current_image(res.image)
        self.dock_develop.show()
        self.btn_report.setEnabled(True)
        self.btn_restack.setEnabled(res.cache is not None)
        self.toast.show_message(f"Stack completato  ·  {used}")
        QApplication.beep()
        if not self.isActiveWindow():
            QApplication.alert(self, 3000)          # lampeggia nella barra delle applicazioni
        if getattr(self, "_batch_folder", ""):
            self._batch_finish_one()

    def _on_failed(self, msg: str):
        self.status.setText("Stacking non riuscito: " + msg.splitlines()[0])
        self.status.setStyleSheet(f"color: {TH.WARN};")
        self._log("ERRORE: " + msg)
        self.toast.show_message("Stacking non riuscito", accent=TH.WARN)
        QMessageBox.critical(self, tr("Stacking non riuscito"), msg.splitlines()[0]
                             + "\n\nControlla il registro per i dettagli.")

    def _on_cancelled(self):
        self.status.setText("Annullato.")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self.progress.set_smooth(0)
        self.toast.show_message("Elaborazione annullata", accent=TH.MUTED)

    # ------------------------------------------------------------ post-processing senza ri-stackare
    def _tool_busy(self) -> bool:
        return self.tool_worker is not None and self.tool_worker.isRunning()

    def _post_changed(self):
        if self.result is None or (self.worker is not None and self.worker.isRunning()):
            return
        if self._undo:
            self.status.setText("Gradiente e colori si regolano prima degli strumenti IA: usa 'Annulla ultima modifica'.")
            self.status.setStyleSheet(f"color: {TH.MUTED};")
            return
        if self.post_worker is not None and self.post_worker.isRunning():
            self._post_pending = True
            return
        self._post_pending = False
        s = self.settings_panel.to_settings()
        self.status.setText("Aggiorno gradiente e fondo cielo…")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self.post_worker = PostWorker(self.result.linear, s, parent=self)
        self.post_worker.done.connect(self._on_post_done)
        self.post_worker.failed.connect(lambda m: self.status.setText("Errore: " + m))
        self.post_worker.start()

    def _on_post_done(self, image, ginfo, preview):
        if self.result is not None:
            self.result.image = image
            self.result.gradient = ginfo
        self._set_current_image(image)
        self.status.setText(f"{ginfo.describe()}" + ("  ·  corretto" if ginfo.applied else "  ·  non applicato")
                            + (f"  ·  {ginfo.describe_color()}" if ginfo.color_mult else ""))
        self.status.setStyleSheet(f"color: {TH.OK};")
        if getattr(self, "_post_pending", False):
            self._post_changed()

    # ------------------------------------------------------------ anteprima
    def _toggle_stretch(self, on: bool):
        self.stretch = on
        self.btn_stretch.setText("Sviluppo" if on else "Lineare")
        if self.current_image is not None:
            self._refresh_preview(full=False)

    def _zoom_100(self):
        if self.current_image is not None and self.result is not None:
            self._refresh_preview(full=True)
        self.view.zoom_100()

    # ------------------------------------------------------------ anteprima / sviluppo
    @staticmethod
    def _make_proxy(image: np.ndarray, max_dim: int = 1400) -> np.ndarray:
        import cv2
        h, w = image.shape[:2]
        f = 1
        while max(h, w) / f > max_dim:
            f *= 2
        return image if f == 1 else np.ascontiguousarray(cv2.resize(image, (w // f, h // f), interpolation=cv2.INTER_AREA))

    def _set_current_image(self, image: np.ndarray):
        """Nuova immagine corrente (livello base): ricalcola l'anteprima ridotta e aggiorna la vista."""
        self.current_image = image
        self.proxy = self._make_proxy(image)
        name = "Stack" if self.result is not None else os.path.basename(self.opened_path or "Immagine")
        if not self.layers:
            self.layers = [Layer(name, image, is_linear=not self.nonlinear, params=self.dev_params)]
            self.layer_proxies = [self.proxy]
        else:
            self.layers[0].image = image
            self.layers[0].is_linear = not self.nonlinear
            self.layers[0].name = name
            self.layers[0].params = self.dev_params
            invalidate(self.layers[0])
            self.layer_proxies[0] = self.proxy
        self.layers_panel.set_layers(self.layers, select=self.layers_panel.current_index() if len(self.layers) > 1 else 0)
        self._refresh_preview(full=False)

    def _render(self, image: np.ndarray, full: bool):
        self._refresh_preview(full)

    def _on_dev_params(self, p: DevelopParams):
        if not self._dev_undo or self._dev_undo[-1] != p.to_json():
            self._push_dev_undo(p)
        idx = self.layers_panel.current_index() if self.layers else 0
        previous = self.layers[idx].params if self.layers and 0 <= idx < len(self.layers) else self.dev_params
        if self.layers and 0 <= idx < len(self.layers):
            self.layers[idx].params = p
            invalidate(self.layers[idx])
        if idx == 0:
            self._queue_editor_history(previous, p)
            self.dev_params = p
        if self.current_image is not None and self.stretch:
            self._dev_timer.start()          # attende che il cursore si fermi (110 ms)

    def _refresh_preview(self, full: bool = False):
        if self.current_image is None:
            return
        if not self.stretch:                 # vista lineare grezza
            if self.render_worker is not None and self.render_worker.isRunning():
                return
            self.render_worker = RenderWorker(self.current_image, 100000 if full else 2200, False, parent=self)
            self.render_worker.done.connect(self._on_rendered)
            self.render_worker.start()
            return
        if len(self.layers) > 1:
            self._refresh_composite()
            return
        if self.dev_worker is not None and self.dev_worker.isRunning():
            self._dev_pending = True
            self._dev_full = self._dev_full or full
            return
        src = self.current_image if full else self.proxy
        self._dev_full = False
        if full:
            self.status.setText("Sviluppo a piena risoluzione…")
            self.status.setStyleSheet(f"color: {TH.MUTED};")
        scale = src.shape[1] / float(self.current_image.shape[1])
        self.dev_worker = DevelopWorker(src, self.dev_params, is_linear=not self.nonlinear, scale=scale,
                                        compare=self.btn_compare.isChecked() and not full, parent=self)
        self.dev_worker.before_ready.connect(self._on_before)
        self.dev_worker.done.connect(self._on_developed)
        self.dev_worker.failed.connect(lambda m: self._log("Sviluppo: " + m))
        self.dev_worker.finished.connect(self._dev_finished)
        self.dev_worker.start()

    def _refresh_composite(self):
        if self.comp_worker is not None and self.comp_worker.isRunning():
            self._dev_pending = True
            return
        show = self.layers_panel.current_index() if self.layers_panel.show_mask.isChecked() else None
        self.comp_worker = CompositeWorker(self.layers, self.layer_proxies, show_mask_of=show, parent=self)
        self.comp_worker.done.connect(self._on_developed)
        self.comp_worker.failed.connect(lambda m: self._log("Livelli: " + m))
        self.comp_worker.finished.connect(self._dev_finished)
        self.comp_worker.start()

    def _dev_finished(self):
        if self._dev_pending:
            self._dev_pending = False
            full = self._dev_full
            self._dev_full = False
            self._refresh_preview(full=full)

    def _on_before(self, rgb8: np.ndarray):
        self.before_rgb8 = rgb8

    def _toggle_compare(self, on: bool):
        self.compare_slider.setVisible(on)
        if on:
            self._refresh_preview(full=False)
        else:
            self.before_rgb8 = None
            if self.after_rgb8 is not None:
                self.view.set_image(self.after_rgb8, keep_view=True)

    def _show_compare(self):
        if not self.btn_compare.isChecked() or self.before_rgb8 is None or self.after_rgb8 is None:
            return
        a, b = self.after_rgb8, self.before_rgb8
        if a.shape != b.shape:
            return
        x = int(a.shape[1] * self.compare_slider.value() / 100.0)
        mix = a.copy()
        mix[:, :x] = b[:, :x]
        x0, x1 = max(0, x - 1), min(a.shape[1], x + 2)
        mix[:, x0:x1] = (242, 180, 65)
        self.view.set_image(np.ascontiguousarray(mix), keep_view=True)

    def _on_developed(self, rgb8: np.ndarray, hist):
        self.after_rgb8 = rgb8
        if self.btn_compare.isChecked() and self.before_rgb8 is not None and self.before_rgb8.shape == rgb8.shape:
            self._show_compare()
            self.develop_panel.set_histogram(hist)
            if self.current_image is not None:
                self.preview_scale = rgb8.shape[1] / float(self.current_image.shape[1])
            return
        self._on_rendered(rgb8)
        self.develop_panel.set_histogram(hist)
        if self.status.text().startswith("Sviluppo a piena"):
            self.status.setText("Anteprima al 100 % con sviluppo applicato.")
            self.status.setStyleSheet(f"color: {TH.MUTED};")

    def _on_rendered(self, rgb8: np.ndarray):
        self.view.set_image(rgb8, keep_view=True)
        if self.current_image is not None:
            self.preview_scale = rgb8.shape[1] / float(self.current_image.shape[1])
        p = self.dev_params
        geometry_identity = (abs(p.rotation) < 1e-6 and not any(p.crop) and not p.flip_h and not p.flip_v)
        if self.annotations and (geometry_identity or not self.stretch):
            self.view.set_annotations(self.annotations, self.preview_scale)
        else:
            self.view.clear_annotations()

    def _auto_tone(self):
        if self.proxy is None:
            return
        try:
            q = auto_tone(self.proxy, self.dev_params, is_linear=not self.nonlinear)
            self.develop_panel.set_params(q, emit=True)
            self.toast.show_message("Auto: neri e bianchi regolati")
        except Exception as e:  # noqa: BLE001
            self._log("Auto: " + str(e))

    def _assist_develop(self):
        if self.proxy is None:
            return
        try:
            q, report = assisted_develop(self.proxy, self.dev_params, is_linear=not self.nonlinear)
            self.develop_panel.set_params(q, emit=True)
            parts = []
            if report.get("gradient_detected"):
                parts.append(f"gradiente {100.0 * float(report.get('gradient_strength', 0.0)):.0f}%")
            if report.get("stars"):
                parts.append(f"{int(report['stars'])} stelle")
            parts.append(f"rumore {100.0 * float(report.get('noise', 0.0)):.1f}%")
            msg = "Sviluppo assistito: " + ", ".join(parts)
            self.toast.show_message(msg)
            self._log(msg)
        except Exception as e:  # noqa: BLE001
            self._log("Sviluppo assistito: " + str(e))

    # ------------------------------------------------------------ strumenti IA
    def _run_tool(self, name: str, params: dict):
        if self.current_image is None or self._tool_busy():
            return
        image = self.current_image
        nonlinear = self.nonlinear

        def job(log):
            if name == "denoise":
                return ("image", ai_tools.run_graxpert(params["graxpert"], image, "denoise",
                                                        strength=params["strength"], gpu=params["gpu"], log=log))
            if name == "background":
                return ("image", ai_tools.run_graxpert(params["graxpert"], image, "background",
                                                        gpu=params["gpu"], log=log))
            if name == "starnet":
                return ("starnet", ai_tools.run_starnet(params["starnet"], image, already_stretched=nonlinear, log=log))
            if name == "annotate":
                return ("annotate", ai_tools.astrometry_annotate(params["api_key"], image, log=log))
            raise ValueError(name)

        labels = {"denoise": "Denoise IA", "background": "Gradiente IA", "starnet": "Rimozione stelle",
                  "annotate": "Riconoscimento oggetti"}
        self._tool_name = labels.get(name, name)
        self.status.setText(f"{self._tool_name} in corso… (può richiedere qualche minuto)")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self._log(f"--- {self._tool_name}")
        self.tools.set_ready(True, busy=True)
        self.tool_worker = ToolWorker(job, parent=self)
        self.tool_worker.log.connect(self._log)
        self.tool_worker.done.connect(self._on_tool_done)
        self.tool_worker.failed.connect(self._on_tool_failed)
        self.tool_worker.finished.connect(lambda: self.tools.set_ready(self.current_image is not None, busy=False))
        self.tool_worker.start()

    def _push_undo(self):
        self._undo.append((self.current_image, self.nonlinear, self.stars_image))
        self._undo = self._undo[-5:]
        self.tools.set_undo(True)

    def _on_tool_done(self, payload):
        kind, data = payload
        if kind == "live":
            self.result = data
            self.nonlinear = False
            self._set_current_image(data.image)
            for f in data.frames:
                self.table.update_frame(f)
            self._live_seen.update(getattr(self, "_live_pending", set()))
            self._live_pending.clear()
            self.status.setText(f"Live: {data.n_used} frame nello stack  ·  {data.gradient.describe()}")
            self.status.setStyleSheet(f"color: {TH.OK};")
            self.preview_label.setText(f"Live Stack  ·  {data.n_used} frame")
            self.btn_restack.setEnabled(data.cache is not None)
            self.toast.show_message(f"Live aggiornato  ·  {data.n_used} frame")
            return
        if kind == "restack":
            data.cache = self.result.cache if self.result is not None else None
            self.result = data
            self.nonlinear = False
            self._set_current_image(data.image)
            for f in data.frames:
                self.table.update_frame(f)
            self.status.setText(f"Ricombinati {data.n_used} frame in {data.elapsed:.0f} s  ·  {data.gradient.describe()}")
            self.status.setStyleSheet(f"color: {TH.OK};")
            self.toast.show_message(f"Ricombinati {data.n_used} frame")
            return
        if kind == "frame":
            name, rgb = data
            self.view.set_image(render_preview(rgb, 2200, True), keep_view=False)
            self.preview_label.setText(f"Frame: {name}")
            self.status.setText(f"Anteprima del singolo frame: {name}")
            self.status.setStyleSheet(f"color: {TH.OK};")
            return
        if kind == "image":
            self._push_undo()
            self._set_current_image(data)
            self.toast.show_message(f"{self._tool_name} applicato")
            self.status.setText(f"{self._tool_name} applicato. 'Annulla ultima modifica' per tornare indietro.")
        elif kind == "starnet":
            starless, stars = data
            self._push_undo()
            self.stars_image = stars
            self.nonlinear = True
            self._set_current_image(starless)
            self.toast.show_message("Stelle rimosse: salva per avere anche il file delle sole stelle")
            self.status.setText("Stelle rimosse (immagine stirata). Salvando, le sole stelle vanno in un file a parte.")
        elif kind == "annotate":
            self.annotations = data.get("annotations", [])
            objs = data.get("objects", [])
            cal = data.get("calibration", {}) or {}
            self.view.set_annotations(self.annotations, self.preview_scale)
            self.view.show_annotations(self.tools.show_labels.isChecked())
            names = ", ".join(objs[:12]) + (" …" if len(objs) > 12 else "")
            self._log("Oggetti nel campo: " + (names or "nessuno riconosciuto"))
            if cal:
                self._log(f"Campo: centro AR {cal.get('ra', 0):.2f}°, Dec {cal.get('dec', 0):.2f}°, "
                          f"raggio {cal.get('radius', 0):.1f}°, scala {cal.get('pixscale', 0):.1f}\"/px")
            self.toast.show_message(f"Riconosciuti {len(objs)} oggetti")
            self.status.setText("Oggetti riconosciuti: " + (names or "nessuno"))
        self.status.setStyleSheet(f"color: {TH.OK};")

    def _on_tool_failed(self, msg: str):
        if getattr(self, "_tool_name", "") == "Live incrementale":
            # Non marchiamo i file come visti: al prossimo polling verranno
            # riprovati, utile se il file era stato appena chiuso dalla camera.
            self._live_pending.clear()
        self._log("ERRORE: " + msg)
        self.status.setText(f"{self._tool_name} non riuscito: {msg}")
        self.status.setStyleSheet(f"color: {TH.WARN};")
        self.toast.show_message(f"{self._tool_name} non riuscito", accent=TH.WARN)

    def _undo_tool(self):
        if not self._undo or self._tool_busy():
            return
        image, self.nonlinear, self.stars_image = self._undo.pop()
        self.tools.set_undo(bool(self._undo))
        self._set_current_image(image)
        self.status.setText("Modifica annullata.")
        self.status.setStyleSheet(f"color: {TH.MUTED};")

    # ------------------------------------------------------------ livelli
    def _layers_changed(self):
        self._dev_timer.start()

    def _layer_selected(self, index: int):
        if 0 <= index < len(self.layers):
            self.develop_panel.set_params(self.layers[index].params, emit=False)
            if self.layers_panel.show_mask.isChecked():
                self._refresh_preview(full=False)

    def _load_layer_image(self, title: str):
        path, _ = QFileDialog.getOpenFileName(self, title, "",
                                              tr("Immagini (*.tif *.tiff *.png *.jpg *.jpeg *.fits *.fit *.fts);;Tutti (*)"))
        if not path:
            return None, None
        try:
            from ..core.loader import load_frame
            fr = load_frame(path)
            data = fr.data
            if fr.is_bayer:
                from ..core.calibration import to_rgb
                data = to_rgb(data, True, fr.pattern)
            if data.ndim == 2:
                data = np.repeat(data[:, :, None], 3, axis=2)
            data = np.ascontiguousarray(data[:, :, :3], dtype=np.float32)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("Apertura non riuscita"), str(e))
            return None, None
        return path, data

    def add_layer(self):
        if self.current_image is None:
            QMessageBox.information(self, tr("Livelli"), tr("Prima serve un'immagine base: fai lo stack o usa Apri immagine…"))
            return
        path, data = self._load_layer_image("Aggiungi un'immagine come livello")
        if data is None:
            return
        linear = os.path.splitext(path)[1].lower() in (".fits", ".fit", ".fts")
        lay = Layer(os.path.basename(path), data, is_linear=linear)
        lay.source_path = path
        self.layers.append(lay)
        self.layer_proxies.append(self._make_proxy(data))
        self.layers_panel.set_layers(self.layers, select=len(self.layers) - 1)
        self.develop_panel.set_params(lay.params, emit=False)
        self.dock_layers.show()
        self.dock_layers.raise_()
        self.toast.show_message(f"Livello aggiunto: {lay.name}")
        self._refresh_preview(full=False)

    def duplicate_layer(self):
        i = self.layers_panel.current_index()
        if not (0 <= i < len(self.layers)):
            return
        src = self.layers[i]
        lay = Layer(src.name + " (copia)", src.image, is_linear=src.is_linear,
                    params=DevelopParams.from_json(src.params.to_json()), visible=src.visible, opacity=src.opacity,
                    blend=src.blend, offset_x=src.offset_x, offset_y=src.offset_y, scale=src.scale,
                    mask_type=src.mask_type, mask_invert=src.mask_invert, mask_feather=src.mask_feather,
                    grad_start=src.grad_start, grad_end=src.grad_end, grad_horizontal=src.grad_horizontal,
                    lum_low=src.lum_low, lum_high=src.lum_high,
                    brush_mask=None if src.brush_mask is None else src.brush_mask.copy(), file_mask=src.file_mask)
        self.layers.insert(i + 1, lay)
        self.layer_proxies.insert(i + 1, self.layer_proxies[i])
        self.layers_panel.set_layers(self.layers, select=i + 1)
        self._refresh_preview(full=False)

    def delete_layer(self):
        i = self.layers_panel.current_index()
        if i <= 0 or i >= len(self.layers):
            return
        self.layers.pop(i)
        self.layer_proxies.pop(i)
        self.layers_panel.set_layers(self.layers, select=min(i, len(self.layers) - 1))
        self.develop_panel.set_params(self.layers[self.layers_panel.current_index()].params, emit=False)
        self._refresh_preview(full=False)

    def move_layer(self, direction: int):
        i = self.layers_panel.current_index()
        j = i + direction
        if i <= 0 or j <= 0 or j >= len(self.layers):
            return
        self.layers[i], self.layers[j] = self.layers[j], self.layers[i]
        self.layer_proxies[i], self.layer_proxies[j] = self.layer_proxies[j], self.layer_proxies[i]
        self.layers_panel.set_layers(self.layers, select=j)
        self._refresh_preview(full=False)

    def _paint_at(self, x: float, y: float, first: bool):
        i = self.layers_panel.current_index()
        if i <= 0 or i >= len(self.layers) or not self.layer_proxies:
            return
        lay = self.layers[i]
        H, W = self.layer_proxies[0].shape[:2]
        if lay.brush_mask is None or lay.brush_mask.shape != (H, W):
            lay.brush_mask = np.zeros((H, W), np.float32)
        size, hard, erase = self.layers_panel.brush()
        paint_brush(lay.brush_mask, x, y, size / 2.0, hard, 0.0 if erase else 1.0)
        if lay.mask_type != "brush":
            lay.mask_type = "brush"
            self.layers_panel.set_layers(self.layers, select=i)
        if first or not (self.comp_worker is not None and self.comp_worker.isRunning()):
            self._refresh_preview(full=False)

    def clear_brush(self):
        i = self.layers_panel.current_index()
        if 0 < i < len(self.layers):
            self.layers[i].brush_mask = None
            self._refresh_preview(full=False)

    def load_mask_file(self):
        i = self.layers_panel.current_index()
        if not (0 < i < len(self.layers)):
            return
        path, data = self._load_layer_image("Carica una maschera (bianco = visibile)")
        if data is None:
            return
        self.layers[i].file_mask = np.ascontiguousarray(data.mean(axis=2), dtype=np.float32)
        self.layers[i].mask_type = "file"
        self.layers_panel.set_layers(self.layers, select=i)
        self._refresh_preview(full=False)

    def _render_full_composite(self):
        return composite(self.layers, None, full=True)

    # ------------------------------------------------------------ gestione dei file
    def manage_files(self, kind: str):
        zone = self.zones.get(kind)
        if zone is None or not zone.files:
            self.toast.show_message("Questa zona è vuota", accent=TH.MUTED)
            return
        dlg = FileManagerDialog(kind, list(zone.files), self)
        retranslate(dlg)
        dlg.removed.connect(lambda z, files: self.zones[z].remove_files(files))
        dlg.moved.connect(self._move_files)
        dlg.exec()

    def _move_files(self, src: str, dest: str, files: list):
        self.zones[src].remove_files(files)
        self.zones[dest].add_paths(files)
        self.toast.show_message(f"Spostati {len(files)} file in {dest}")

    # ------------------------------------------------------------ controlli prima dello stack
    def _coherence_warnings(self) -> list:
        """Avvisi sulla coerenza dei file caricati (ISO, posa, doppioni, dimensioni)."""
        from ..core.loader import quick_meta
        warn = []
        meta = {}
        for kind, zone in self.zones.items():
            if not zone.files:
                continue
            sample = [quick_meta(p) for p in zone.files[:3]]
            iso = {m.get("iso") for m in sample if m.get("iso")}
            exp = {round(float(m["exposure"]), 3) for m in sample if m.get("exposure")}
            meta[kind] = {"iso": iso, "exp": exp}
        light = meta.get("light", {})
        if light:
            for kind, label in (("dark", "dark"), ("flat", "flat"), ("bias", "bias")):
                m = meta.get(kind)
                if not m:
                    continue
                if kind in ("dark", "bias") and light.get("iso") and m.get("iso") and light["iso"] != m["iso"]:
                    warn.append(f"Gli {label} hanno ISO {sorted(m['iso'])} mentre i light hanno {sorted(light['iso'])}.")
                if kind == "dark" and light.get("exp") and m.get("exp") and light["exp"] != m["exp"]:
                    warn.append(f"I dark hanno posa {sorted(m['exp'])} s e i light {sorted(light['exp'])} s: "
                                "attiva 'Riscala i dark' oppure usa dark della stessa posa.")
                if kind == "bias" and m.get("exp") and max(m["exp"]) > 0.05:
                    warn.append("I file nella zona Bias hanno pose lunghe: sicuro che siano bias?")
        names = {}
        for kind, zone in self.zones.items():
            for p in zone.files:
                names.setdefault(os.path.normcase(os.path.abspath(p)), []).append(kind)
        dup = [k for k, v in names.items() if len(v) > 1]
        if dup:
            warn.append(f"{len(dup)} file sono caricati in più zone contemporaneamente.")
        if len(self.zones["light"].files) < 3:
            warn.append("Con meno di 3 light il rigetto non è affidabile: il programma userà media o mediana.")
        return warn

    # ------------------------------------------------------------ ricombinazione veloce
    def restack_now(self):
        if self.result is None or self.result.cache is None or self._tool_busy():
            return
        settings = self.settings_panel.to_settings()
        self.status.setText("Ricombino i frame già calibrati…")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self.btn_restack.setEnabled(False)
        self.btn_restack.set_busy(True)
        result, excluded = self.result, set(self.excluded)

        def job(log):
            return ("restack", restack(result, settings, excluded=excluded,
                                       progress=lambda d, t, m: log(f"ricombinazione {d}/{t}")))

        self._tool_name = "Ricombinazione"
        self.tool_worker = ToolWorker(job, parent=self)
        self.tool_worker.log.connect(self._log)
        self.tool_worker.done.connect(self._on_tool_done)
        self.tool_worker.failed.connect(self._on_tool_failed)
        self.tool_worker.finished.connect(lambda: (self.btn_restack.set_busy(False),
                                                   self.btn_restack.setEnabled(self.result is not None
                                                                               and self.result.cache is not None)))
        self.tool_worker.start()

    def toggle_frame(self, path: str, excluded: bool):
        """Esclude o reinserisce un frame (poi basta Ricombina)."""
        if excluded:
            self.excluded.add(path)
        else:
            self.excluded.discard(path)
        if self.result is not None and self.result.cache is not None:
            self.btn_restack.setEnabled(True)
            self.status.setText(f"{len(self.excluded)} frame esclusi: premi Ricombina per aggiornare")
            self.status.setStyleSheet(f"color: {TH.MUTED};")

    def inspect_frame(self, path: str):
        """Doppio clic su una riga: mostra quel singolo scatto nell'anteprima."""
        if not os.path.isfile(path) or self._tool_busy():
            return
        settings = self.settings_panel.to_settings()
        self._tool_name = "Anteprima del frame"
        self.status.setText(f"Carico {os.path.basename(path)}…")
        self.status.setStyleSheet(f"color: {TH.MUTED};")

        def job(log):
            from ..core import calibration as cal
            from ..core.loader import load_frame
            fr = load_frame(path)
            data, _ = cal.calibrate_light(fr, cal.Masters(), auto_cosmetic=settings.auto_cosmetic,
                                          hot_sigma=settings.hot_sigma)
            rgb = cal.to_rgb(data, fr.is_bayer, fr.pattern, settings.debayer)
            return ("frame", (os.path.basename(path), np.ascontiguousarray(rgb, dtype=np.float32)))

        self.tool_worker = ToolWorker(job, parent=self)
        self.tool_worker.log.connect(self._log)
        self.tool_worker.done.connect(self._on_tool_done)
        self.tool_worker.failed.connect(self._on_tool_failed)
        self.tool_worker.start()

    # ------------------------------------------------------------ pipetta
    def _sample_point(self, x: float, y: float):
        """Clic con la pipetta: regola temperatura e tinta perché quel punto sia grigio."""
        img = self.current_image
        if img is None:
            return
        scale = self.preview_scale or 1.0
        px, py = int(round(x / scale)), int(round(y / scale))
        h, w = img.shape[:2]
        if not (0 <= px < w and 0 <= py < h):
            return
        r = max(3, int(0.004 * max(h, w)))
        patch = img[max(0, py - r):py + r + 1, max(0, px - r):px + r + 1].reshape(-1, 3)
        med = np.median(patch, axis=0)
        if float(med.mean()) <= 1e-5:
            self.toast.show_message("Punto troppo scuro: scegline uno sul fondo cielo", accent=TH.WARN)
            return
        p = DevelopParams.from_json(self.dev_params.to_json())
        # temperatura sposta R/B, tinta sposta il verde: risolviamo per riportare il punto a grigio
        rb = float(np.log(max(med[0], 1e-6) / max(med[2], 1e-6)))
        p.temperature = float(np.clip(p.temperature - rb * 120.0, -100, 100))
        g_ratio = float(med[1] / max((med[0] + med[2]) / 2.0, 1e-6))
        p.tint = float(np.clip(p.tint + (g_ratio - 1.0) * 200.0, -100, 100))
        self.develop_panel.set_params(p, emit=True)
        self.develop_panel.btn_pick.setChecked(False)
        self.toast.show_message(f"Fondo cielo neutralizzato (temp {p.temperature:+.0f}, tinta {p.tint:+.0f})")

    # ------------------------------------------------------------ sviluppo: annulla / ripeti
    def _push_dev_undo(self, params):
        self._dev_undo.append(params.to_json())
        self._dev_undo = self._dev_undo[-40:]
        self._dev_redo.clear()

    def undo_develop(self):
        if len(self._dev_undo) < 2:
            return
        self._dev_redo.append(self._dev_undo.pop())
        self._apply_dev_json(self._dev_undo[-1])
        self.toast.show_message("Sviluppo: modifica annullata")

    def redo_develop(self):
        if not self._dev_redo:
            return
        js = self._dev_redo.pop()
        self._dev_undo.append(js)
        self._apply_dev_json(js)
        self.toast.show_message("Sviluppo: modifica ripetuta")

    def _apply_dev_json(self, js: str):
        p = DevelopParams.from_json(js)
        idx = self.layers_panel.current_index() if self.layers else 0
        if self.layers and 0 <= idx < len(self.layers):
            self.layers[idx].params = p
            invalidate(self.layers[idx])
        if idx == 0:
            self.dev_params = p
        self.develop_panel.set_params(p, emit=False)
        self._refresh_preview(full=False)

    # ------------------------------------------------------------ tema
    def toggle_theme(self):
        TH.set_theme("scuro" if TH.THEME == "chiaro" else "chiaro")
        app = QApplication.instance()
        app.setPalette(TH.dark_palette())
        app.setStyleSheet(TH.build_stylesheet())
        self.btn_theme.setText("☀" if TH.THEME == "scuro" else "☾")
        QSettings("AstroStack", "AstroStack").setValue("theme", TH.THEME)
        for z in self.zones.values():
            z.color = TH.ZONE_COLORS[z.kind]
            z._apply_style()
        self.toast.show_message("Tema chiaro" if TH.THEME == "chiaro" else "Tema notturno")

    # ------------------------------------------------------------ report
    def save_report(self):
        if self.result is None:
            return
        base = os.path.dirname(self.zones["light"].files[0]) if self.zones["light"].files else ""
        path, _ = QFileDialog.getSaveFileName(self, tr("Salva il report"), os.path.join(base, "report.html"),
                                              "HTML (*.html)")
        if not path:
            return
        try:
            write_report(path, self.result, self.settings_panel.to_settings(), self.dev_params,
                         {k: len(z.files) for k, z in self.zones.items()}, self.current_image)
            self.status.setText(f"Report salvato: {path}")
            self.status.setStyleSheet(f"color: {TH.OK};")
            self.toast.show_message("Report salvato")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("Salvataggio non riuscito"), str(e))

    # ------------------------------------------------------------ elaborazione a lotti
    def run_batch(self):
        if self.worker is not None and self.worker.isRunning():
            return
        dlg = BatchDialog(self)
        retranslate(dlg)
        if dlg.exec() != BatchDialog.DialogCode.Accepted:
            return
        folders = dlg.folders()
        if not folders:
            return
        self._batch = list(folders)
        self._batch_opts = {"report": dlg.save_report.isChecked(), "jpg": dlg.autoexport.isChecked()}
        self._log(f"Lotti: {len(folders)} sessioni da elaborare")
        self._batch_next()

    def _batch_next(self):
        if not self._batch:
            self.toast.show_message("Lotti completati")
            self.status.setText("Elaborazione a lotti completata.")
            self.status.setStyleSheet(f"color: {TH.OK};")
            return
        folder = self._batch.pop(0)
        self.import_session(folder)
        if not self.zones["light"].files:
            self._log(f"Lotti: nessun light in {folder}, salto")
            self._batch_next()
            return
        self.status.setText(f"Lotti: elaboro {os.path.basename(folder)} ({len(self._batch)} rimanenti)")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self._batch_folder = folder
        self.start_stack()

    def _batch_finish_one(self):
        """Salvataggi automatici a fine stack, durante l'elaborazione a lotti."""
        folder = getattr(self, "_batch_folder", "")
        if not folder or self.result is None:
            return
        name = os.path.basename(folder.rstrip("/\\")) or "stack"
        try:
            from ..core.io_out import save_result
            save_result(os.path.join(folder, f"{name}_stack.tif"), self.result.linear, {"NFRAMES": self.result.n_used})
            if self._batch_opts.get("jpg"):
                save_result(os.path.join(folder, f"{name}_stack.jpg"), self.current_image, {})
            if self._batch_opts.get("report"):
                write_report(os.path.join(folder, f"{name}_report.html"), self.result,
                             self.settings_panel.to_settings(), self.dev_params, None, self.current_image)
            self._log(f"Lotti: salvato {name}_stack.tif in {folder}")
        except Exception as e:  # noqa: BLE001
            self._log(f"Lotti: salvataggio non riuscito ({e})")
        QTimer.singleShot(600, self._batch_next)

    # ------------------------------------------------------------ progetto
    def save_project(self):
        if self.current_image is None and not self.zones["light"].files:
            QMessageBox.information(self, tr("Progetto"), tr("Non c'è ancora nulla da salvare: carica i file o fai lo stack."))
            return
        if self.zones["light"].files:
            project_dir = os.path.dirname(self.zones["light"].files[0])
        elif self.opened_path:
            project_dir = os.path.dirname(self.opened_path)
        else:
            project_dir = self._last_dir()
        default = self.project_path or os.path.join(project_dir, ("sessione.astrostack" if i18n.language() == "it" else "session.astrostack"))
        path, _ = QFileDialog.getSaveFileName(self, tr("Salva progetto"), default, tr("Progetto AstroStack (*.astrostack)"))
        if not path:
            return
        if not path.lower().endswith(".astrostack"):
            path += ".astrostack"
        try:
            zones = {k: list(z.files) for k, z in self.zones.items()}
            settings = self.settings_panel.to_settings().__dict__
            # Salviamo la base effettivamente visibile/modificata, non solo lo
            # stack pre-postprocessing: alla riapertura il progetto torna così
            # nello stesso stato visivo in cui era stato lasciato.
            base = self.current_image
            project_io.save_project(path, zones, settings, self.layers, base, not self.nonlinear,
                                    self.opened_path, self.annotations,
                                    {"workspace": self.workspace,
                                     "snapshots": self.editor_sidebar.snapshots() if hasattr(self, "editor_sidebar") else []})
            self.project_path = path
            self.status.setText(f"Progetto salvato: {path}")
            self.status.setStyleSheet(f"color: {TH.OK};")
            self.toast.show_message("Progetto salvato")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("Salvataggio del progetto non riuscito"), str(e))

    def open_project(self):
        if self.worker is not None and self.worker.isRunning():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Apri progetto"), "", tr("Progetto AstroStack (*.astrostack)"))
        if not path:
            return
        try:
            data = project_io.load_project(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("Apertura del progetto non riuscita"), str(e))
            return
        self.project_path = path
        for k, z in self.zones.items():
            z.set_files([p for p in data["zones"].get(k, []) if os.path.exists(p)])
        try:
            from ..core.pipeline import Settings
            st = Settings(**{k: v for k, v in data["settings"].items() if k in Settings().__dict__})
            self.settings_panel.set_from_settings(st)
        except Exception as e:  # noqa: BLE001
            self._log("Impostazioni del progetto non applicate: " + str(e))
        self.result = None
        self.opened_path = data.get("opened_path")
        self.annotations = data.get("annotations", [])
        self._undo = []
        self.layers = []
        self.layer_proxies = []
        self.stars_image = None
        if hasattr(self, "editor_sidebar"):
            self.editor_sidebar.clear_history()
            self.editor_sidebar.set_snapshots(data.get("ui_state", {}).get("snapshots", []))
        if data.get("layers") and data["layers"][0].image is not None:
            base_layer = data["layers"][0]
            self.nonlinear = not base_layer.is_linear
            self.dev_params = base_layer.params
            self.develop_panel.set_params(self.dev_params, emit=False)
            self.layers = data["layers"]
            self.layer_proxies = [self._make_proxy(l.image) for l in self.layers]
            self.current_image = base_layer.image
            self.proxy = self.layer_proxies[0]
            self.layers_panel.set_layers(self.layers, select=0)
            self._set_running(False)
            self.dock_develop.show()
            if len(self.layers) > 1:
                self.dock_layers.show()
            self._refresh_preview(full=False)
            self.preview_label.setText("Progetto: " + os.path.basename(path))
        else:
            self.current_image = None
            self.view.clear()
            self._update_ready(from_zones=True)
        if data.get("missing"):
            self._log("File del progetto non trovati: " + ", ".join(str(m) for m in data["missing"]))
            self.toast.show_message("Alcuni file del progetto non sono stati trovati (vedi Registro)", accent=TH.WARN)
        else:
            self.toast.show_message("Progetto aperto")
        self.status.setText(f"Progetto aperto: {path}")
        self.status.setStyleSheet(f"color: {TH.OK};")
        preferred = str(data.get("ui_state", {}).get("workspace", ""))
        if preferred not in ("stack", "editor"):
            preferred = "editor" if (self.current_image is not None and not any(z.files for z in self.zones.values())) else "stack"
        self._set_workspace(preferred)

    # ------------------------------------------------------------ smistamento
    def sort_files(self, paths: Optional[list] = None):
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, tr("Scegli i file da smistare (light, dark, flat, bias insieme)"), self._last_dir(),
                                                    "Immagini (*.cr2 *.cr3 *.nef *.arw *.dng *.raf *.orf *.rw2 *.fits *.fit *.tif *.tiff *.png *.jpg);;Tutti (*)")
            if not paths:
                return
        from ..core.loader import collect_files
        files = collect_files(paths)
        if not files:
            return
        self.status.setText(f"Smistamento di {len(files)} file…")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        QApplication.processEvents()

        def job(log):
            return classify_files(files, progress=lambda d, t, n: log(f"smistamento {d}/{t}: {n}"))

        self._tool_name = "Smistamento"
        self.tool_worker = ToolWorker(job, parent=self)
        self.tool_worker.done.connect(self._on_sorted)
        self.tool_worker.failed.connect(self._on_tool_failed)
        self.tool_worker.start()

    def _on_sorted(self, res: dict):
        added = []
        for k in ("light", "dark", "flat", "bias"):
            if res.get(k):
                self.zones[k].add_paths(res[k])
                added.append(f"{k} {len(res[k])}")
        for p, (kind, why) in res.get("reasons", {}).items():
            self._log(f"{os.path.basename(p)} → {kind} ({why})")
        msg = "Smistati: " + ", ".join(added) if added else "Nessun file riconosciuto"
        self.status.setText(msg)
        self.status.setStyleSheet(f"color: {TH.OK};")
        self.toast.show_message(msg)

    # ------------------------------------------------------------ live stacking
    def _toggle_live(self, on: bool):
        if on:
            d = QFileDialog.getExistingDirectory(self, tr("Cartella da osservare (i light che arrivano)"))
            if not d:
                self.btn_live.setChecked(False)
                return
            self.live_dir = d
            self._live_seen = set()
            self._live_pending = set()
            self.live_timer.start()
            self.status.setText(f"Live: osservo {d} (controllo ogni 5 s)")
            self.status.setStyleSheet(f"color: {TH.OK};")
            self._live_poll()
        else:
            self.live_timer.stop()
            self.live_dir = None
            self.status.setText("Live disattivato.")
            self.status.setStyleSheet(f"color: {TH.MUTED};")

    def _live_poll(self):
        if not self.live_dir:
            return
        from ..core.loader import collect_files
        files = collect_files([self.live_dir])
        # ignora i file che stanno ancora arrivando (dimensione che cambia)
        stable = []
        sizes = getattr(self, "_live_sizes", {})
        for f in files:
            try:
                sz = os.path.getsize(f)
            except OSError:
                continue
            if sizes.get(f) == sz:
                stable.append(f)
            sizes[f] = sz
        self._live_sizes = sizes
        new = [f for f in stable if f not in self._live_seen]
        if not new:
            return
        if (self.worker is not None and self.worker.isRunning()) or self._tool_busy():
            return
        self.zones["light"].set_files(stable)
        # Dopo il primo stack riusiamo master, cache e trasformazioni già
        # calcolate. Se per qualsiasi motivo non sono disponibili, fallback
        # trasparente al comportamento completo originale.
        if self.result is not None and self.result.cache is not None and getattr(self.result, "masters", None) is not None:
            self._live_pending = set(new)
            settings = self.settings_panel.to_settings()
            settings.excluded = tuple(self.excluded)
            current = self.result
            self._log(f"Live: {len(new)} nuovi file, {len(stable)} in totale: elaborazione incrementale")
            self.toast.show_message(f"Live: +{len(new)} frame, aggiorno lo stack")
            self.status.setText(f"Live: calibro {len(new)} nuovi frame…")
            self.status.setStyleSheet(f"color: {TH.MUTED};")

            def job(log):
                return ("live", extend_live_stack(current, new, settings,
                                                  progress=lambda d, t, m: log(f"live {d}/{t}: {m}"),
                                                  log=log))

            self._tool_name = "Live incrementale"
            self.tool_worker = ToolWorker(job, parent=self)
            self.tool_worker.log.connect(self._log)
            self.tool_worker.done.connect(self._on_tool_done)
            self.tool_worker.failed.connect(self._on_tool_failed)
            self.tool_worker.start()
        else:
            self._live_seen.update(stable)
            self._log(f"Live: {len(new)} nuovi file, {len(stable)} in totale: primo stack completo")
            self.toast.show_message(f"Live: {len(stable)} frame, creo lo stack iniziale")
            self.start_stack()

    # ------------------------------------------------------------ apri immagine
    def open_image(self):
        if self.worker is not None and self.worker.isRunning():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Apri un'immagine da sviluppare"), self._last_dir(),
                                              tr("Immagini (*.tif *.tiff *.png *.jpg *.jpeg *.fits *.fit *.fts *.cr2 *.cr3 *.nef *.arw *.dng *.raf *.orf *.rw2);;Tutti (*)"))
        if not path:
            return
        self.open_image_path(path)

    def open_image_path(self, path: str):
        """Apre direttamente un'immagine nell'Editor (anche da drag&drop)."""
        if not path or not os.path.isfile(path):
            return
        try:
            from ..core.loader import load_frame
            fr = load_frame(path)
            data = fr.data
            if fr.is_bayer:
                from ..core.calibration import to_rgb
                data = to_rgb(data, True, fr.pattern)
            if data.ndim == 2:
                data = np.repeat(data[:, :, None], 3, axis=2)
            data = np.ascontiguousarray(data[:, :, :3], dtype=np.float32)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, tr("Apertura non riuscita"), str(e))
            return
        self.result = None
        self._set_workspace("editor")
        self.opened_path = path
        self._remember_dir(path)
        self.stars_image = None
        self.annotations = []
        self._undo = []
        self.layers = []
        self.layer_proxies = []
        if hasattr(self, "editor_sidebar"):
            self.editor_sidebar.set_snapshots([])
            self.editor_sidebar.clear_history()
        self.view.clear_annotations()
        self.tools.set_undo(False)
        # FITS/RAW = dati lineari (da stirare); TIFF/PNG/JPG = già sviluppati.
        self.nonlinear = os.path.splitext(path)[1].lower() not in (
            ".fits", ".fit", ".fts", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"
        )
        self.btn_stretch.setChecked(True)
        self._set_current_image(data)
        self.editor_sidebar.set_source(path, data.shape, is_linear=not self.nonlinear)
        self._set_running(False)
        self.dock_develop.show()
        self.preview_label.setText(os.path.basename(path) + ("  ·  lineare" if not self.nonlinear else ""))
        self.status.setText(f"Aperta: {path}")
        self.status.setStyleSheet(f"color: {TH.OK};")

    # ------------------------------------------------------------ esportazione
    def save_result(self):
        if self.current_image is None:
            return
        if self.export_worker is not None and self.export_worker.isRunning():
            return
        h, w = self.current_image.shape[:2]
        dlg = ExportDialog((w, h), has_develop=True, parent=self)
        retranslate(dlg)
        if dlg.exec() != ExportDialog.DialogCode.Accepted:
            return
        opt = dlg.options()
        ext = EXT_FOR_FMT.get(opt.fmt, ".tif")
        if self.result is not None:
            lights = self.zones["light"].files
            base_dir = os.path.dirname(lights[0]) if lights else ""
            default = os.path.join(base_dir, f"stack_{self.result.n_used}{'frame' if i18n.language() == 'it' else 'frames'}{ext}")
        else:
            root, _ = os.path.splitext(self.opened_path or ("immagine" if i18n.language() == "it" else "image"))
            default = root + ("_sviluppata" if i18n.language() == "it" else "_developed") + ext
        filt = {".tif": "TIFF (*.tif)", ".png": "PNG (*.png)", ".jpg": "JPEG (*.jpg)", ".fits": "FITS (*.fits)"}[ext]
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta il risultato"), default, filt)
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ext
        meta = ({"NFRAMES": self.result.n_used, "REFFRAME": self.result.reference,
                 "GRADIENT": f"{self.result.gradient.strength * 100:.1f}%",
                 "METHOD": self.settings_panel.to_settings().method} if self.result is not None
                else {"SOURCE": os.path.basename(self.opened_path or "")})
        self.status.setText("Esportazione in corso…")
        self.status.setStyleSheet(f"color: {TH.MUTED};")
        self.btn_save.setEnabled(False)
        render_fn = self._render_full_composite if (len(self.layers) > 1 and opt.apply_develop and opt.fmt != "fits") else None
        self.export_worker = ExportWorker(path, self.current_image, self.dev_params, not self.nonlinear, opt, meta,
                                          self.stars_image, render_fn=render_fn, parent=self)
        self.export_worker.progress.connect(lambda m: self.status.setText("Esportazione: " + m))
        self.export_worker.done.connect(lambda extra, p=path: self._on_exported(p, extra))
        self.export_worker.failed.connect(self._on_export_failed)
        self.export_worker.finished.connect(lambda: self.btn_save.setEnabled(self.current_image is not None))
        self.export_worker.start()

    def _on_exported(self, path: str, extra: str):
        msg = f"Salvato: {path}" + (f"  +  {os.path.basename(extra)}" if extra else "")
        self.status.setText(msg)
        self.status.setStyleSheet(f"color: {TH.OK};")
        self._log(msg)
        self.toast.show_message("Esportato  ·  " + os.path.basename(path))

    def _on_export_failed(self, msg: str):
        self.status.setText("Esportazione non riuscita: " + msg)
        self.status.setStyleSheet(f"color: {TH.WARN};")
        self._log("ERRORE esportazione: " + msg)
        QMessageBox.critical(self, tr("Esportazione non riuscita"), msg)

    # ------------------------------------------------------------ chiusura
    def _restore_geometry(self):
        qs = QSettings("AstroStack", "AstroStack")
        geo = qs.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def closeEvent(self, e):
        if self.worker is not None and self.worker.isRunning():
            r = QMessageBox.question(self, tr("Stacking in corso"), tr("Vuoi interrompere lo stacking e uscire?"))
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(15000)
        self.settings_panel.save()
        qs = QSettings("AstroStack", "AstroStack")
        qs.setValue("geometry", self.saveGeometry())
        if self.project_path and self.current_image is not None:
            try:                         # salvataggio automatico del progetto aperto
                project_io.save_project(self.project_path, {k: list(z.files) for k, z in self.zones.items()},
                                        self.settings_panel.to_settings().__dict__, self.layers,
                                        self.current_image, not self.nonlinear, self.opened_path, self.annotations,
                                        {"workspace": self.workspace,
                                         "snapshots": self.editor_sidebar.snapshots() if hasattr(self, "editor_sidebar") else []})
            except Exception:
                pass
        if self.result is not None:
            self.result.cleanup()
        e.accept()
