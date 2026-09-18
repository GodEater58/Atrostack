"""Desktop composition matching the approved reference; existing processing stays wired."""
from __future__ import annotations

import types
from PySide6.QtCore import QObject, QEvent, QPoint, QSize, Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget,
)
from . import theme as TH
from .i18n import tr, skip
from .preview import numpy_to_qimage
from .widgets import AnimatedButton


def preset_icon(key):
    """Small procedural symbols, not previews of the applied result."""
    import math
    from PySide6.QtCore import QPointF, QRectF
    pix = QPixmap(84, 38)
    pix.fill(QColor("#09121d"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#7994b0"))
    for x, y in ((6, 7), (16, 30), (26, 5), (58, 7), (73, 27), (65, 33)):
        painter.drawPoint(x, y)
    if key == "moon":
        painter.setPen(QColor("#b9c4ce"))
        painter.setBrush(QColor("#9aaab6"))
        painter.drawEllipse(QRectF(29, 5, 27, 27))
        painter.setBrush(QColor("#6f808d"))
        painter.drawEllipse(QRectF(33, 12, 8, 8))
        painter.drawEllipse(QRectF(43, 20, 6, 6))
    elif key in ("galaxy", "milkyway", "natural"):
        painter.translate(42, 19)
        painter.rotate(-18)
        painter.setPen(QPen(QColor("#ac9cb2"), 1.5))
        for radius in (8, 16, 25, 33):
            painter.drawEllipse(QRectF(-radius, -radius/3, radius*2, radius*2/3))
        painter.setBrush(QColor("#efd9b6"))
        painter.drawEllipse(QRectF(-3, -2, 6, 4))
    else:
        color = "#bc718a" if key == "nebula" else "#839dc6"
        painter.setPen(QPen(QColor(color), 1.4))
        for i in range(12):
            angle = i * math.pi / 6
            painter.drawEllipse(QPointF(42 + 13*math.cos(angle), 19 + 8*math.sin(angle)), 5, 4)
        painter.setPen(QColor("#edca77"))
        painter.drawLine(39, 19, 45, 19)
        painter.drawLine(42, 16, 42, 22)
    painter.end()
    return QIcon(pix)


class CompareHandle(QPushButton):
    """Drag in image coordinates, including when the canvas is zoomed or panned."""
    def __init__(self, workspace):
        super().__init__("↔", workspace.window.view.viewport())
        self.workspace = workspace
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip("Trascina per confrontare prima e dopo")
        self.dragging = False
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return
        w = self.workspace.window
        point = w.view.viewport().mapFromGlobal(event.globalPosition().toPoint())
        scene = w.view.mapToScene(point)
        width = w.view.sceneRect().width()
        if width:
            w.compare_slider.setValue(round(max(0, min(100, scene.x() / width * 100))))
        self.workspace.position_overlay()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()


class RenderWorkspace(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.current_route = "home"
        self.panel_sizes = {}
        self.split = window.main_splitter
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(6)
        self.center = self.split.widget(2)
        self.center.layout().setContentsMargins(0, 0, 0, 0)
        self.inspector = QStackedWidget()
        self.inspector.setMinimumWidth(330)
        self.inspector.setMaximumWidth(510)
        self.inspector.setObjectName("renderInspector")
        for dock in (window.dock_develop, window.dock_layers):
            window.removeDockWidget(dock)
            dock.setMinimumWidth(0)
            dock.setTitleBarWidget(QWidget())
            dock.setFeatures(dock.DockWidgetFeature.NoDockWidgetFeatures)
            self.inspector.addWidget(dock)
        self.split.addWidget(self.inspector)
        self.split.setStretchFactor(2, 1)
        self.split.setStretchFactor(3, 0)
        self.split.splitterMoved.connect(self.remember_sizes)
        self.build_toolbar()
        self.build_sidebar()
        self.build_filmstrip()
        self.build_stack_steps()
        self.build_overlay()
        self.install_callbacks()
        window.develop_panel.show_section("base")
        self.refresh_theme()

    def build_toolbar(self):
        w = self.window
        self.toolbar = QFrame()
        self.toolbar.setObjectName("renderToolbar")
        row = QHBoxLayout(self.toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.open_button = AnimatedButton("Apri immagine…")
        self.open_button.clicked.connect(lambda: w.open_image())
        row.addWidget(self.open_button)
        # Reuse the save-project button, including v13's latest-path callback.
        row.addWidget(w.btn_proj_save)
        self.undo_button = AnimatedButton("Annulla")
        self.undo_button.clicked.connect(w.undo_develop)
        self.redo_button = AnimatedButton("Ripristina")
        self.redo_button.clicked.connect(w.redo_develop)
        row.addWidget(self.undo_button)
        row.addWidget(self.redo_button)
        row.addWidget(w.btn_compare)
        row.addWidget(w.compare_slider)
        w.compare_slider.setFixedWidth(75)
        w.compare_slider.setToolTip("Posizione del confronto prima / dopo")
        row.addStretch(1)
        row.addWidget(w.btn_fit)
        row.addWidget(w.btn_100)
        self.focus_button = AnimatedButton("Pannelli")
        self.focus_button.setCheckable(True)
        self.focus_button.setToolTip("Nascondi i pannelli per dare spazio all'immagine (Tab)")
        self.focus_button.toggled.connect(self.toggle_focus)
        row.addWidget(self.focus_button)
        w.btn_save.variant = "primary"
        w.btn_save.setText("Esporta…")
        w.btn_save.setMinimumSize(115, 34)
        row.addWidget(w.btn_save)
        root = w._v14_legacy_content.layout()
        root.insertWidget(root.indexOf(self.split), self.toolbar)
        # Clear unused spacers in the old preview action row.
        oldrow = self.center.layout().itemAt(0).layout()
        while oldrow.count():
            item = oldrow.takeAt(0)
            if item.widget():
                item.widget().hide()
        oldrow.addWidget(w.preview_label, 1)
        w.preview_label.show()
        self.zoom_label = QLabel("Adatta")
        self.zoom_label.setProperty("role", "muted")
        oldrow.addWidget(self.zoom_label)
        w.view.zoom_changed.connect(lambda value: self.zoom_label.setText(f"{value * 100:.0f}%"))
        # A compact mode control is always reachable, including in Stack.
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(10, 4, 10, 4)
        mode_row.addWidget(QLabel("Modalità"), 1)
        mode_row.addWidget(w.btn_ui_mode)
        w.develop_panel.layout().insertLayout(0, mode_row)
        w.btn_ui_mode.show()
        self.stack_mode = AnimatedButton("Avanzata" if w.ui_mode == "advanced" else "Semplice")
        self.stack_mode.clicked.connect(w.btn_ui_mode.click)
        w.v14_topbar.layout().addWidget(self.stack_mode)
        w.btn_ui_mode.clicked.connect(self.sync_mode)
        w.v14_context_secondary.setText("Altre azioni ▾")
        w.v14_context_secondary.clicked.disconnect()
        w.v14_context_secondary.clicked.connect(self.show_menu)
        for key, callback in (("Ctrl+O", w.open_image), ("Ctrl+Shift+S", w.save_project),
                              ("Ctrl+Shift+E", lambda: w.btn_save.click()),
                              ("Tab", self.focus_button.click)):
            action = QAction(w)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(callback)
            w.addAction(action)

    def build_sidebar(self):
        w = self.window
        side = w.editor_sidebar
        side.setMinimumWidth(210)
        side.setMaximumWidth(290)
        layout = side.layout()
        # Retain source, presets, snapshots and history with their original signals.
        self.source_card = layout.itemAt(0).widget()
        self.preset_card = layout.itemAt(1).widget()
        self.snapshot_card = layout.itemAt(2).widget()
        self.history_card = layout.itemAt(3).widget()
        self.nav = QListWidget()
        self.nav.setObjectName("editorCategories")
        self.nav.setSpacing(1)
        self.nav.setMinimumHeight(240)
        self.nav.setMaximumHeight(265)
        self.categories = (("base", "Regolazioni di base"), ("astro", "Strumenti astro"),
                           ("colore", "Colore / HSL"), ("dettaglio", "Dettaglio"),
                           ("curve", "Curva dei toni"), ("geometria", "Geometria / effetti"),
                           ("layers", "Livelli e maschere"))
        for key, name in self.categories:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(item)
        def translate_categories():
            for index, (_, name) in enumerate(self.categories):
                self.nav.item(index).setText(tr(name))
        self.nav.retranslate_i18n = translate_categories
        self.nav.currentItemChanged.connect(self.select_category)
        layout.insertWidget(1, self.nav)
        side.preset_list.setViewMode(QListView.ViewMode.IconMode)
        side.preset_list.setFlow(QListView.Flow.LeftToRight)
        side.preset_list.setWrapping(True)
        side.preset_list.setResizeMode(QListView.ResizeMode.Adjust)
        side.preset_list.setGridSize(QSize(86, 66))
        side.preset_list.setIconSize(QSize(78, 35))
        side.preset_list.setUniformItemSizes(True)
        side.preset_list.setSpacing(0)
        for index in range(side.preset_list.count()):
            item = side.preset_list.item(index)
            item.setIcon(preset_icon(item.data(Qt.ItemDataRole.UserRole)))
            item.setToolTip(item.text() + " · applica una ricetta modificabile")
        side.preset_list.setMinimumHeight(100)
        side.preset_list.setMaximumHeight(190)
        side.preset_list.setWordWrap(True)
        side.preset_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setCurrentRow(0)
        # Wrap the entire sidebar: smaller displays can scroll, never clip controls.
        self.side_scroll = QScrollArea()
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setMinimumWidth(220)
        self.side_scroll.setMaximumWidth(300)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setWidget(side)
        self.split.insertWidget(1, self.side_scroll)

    def build_filmstrip(self):
        side = self.window.editor_sidebar
        self.filmstrip = QTabWidget()
        self.filmstrip.setObjectName("snapshotFilmstrip")
        self.filmstrip.setMinimumHeight(125)
        self.filmstrip.setMaximumHeight(150)
        self.filmstrip.addTab(self.snapshot_card, "Snapshot")
        self.filmstrip.addTab(self.history_card, "Cronologia")
        self.center.layout().insertWidget(2, self.filmstrip)
        side.snapshot_list.setViewMode(QListView.ViewMode.IconMode)
        side.snapshot_list.setFlow(QListView.Flow.LeftToRight)
        side.snapshot_list.setWrapping(False)
        side.snapshot_list.setIconSize(QSize(94, 46))
        side.snapshot_list.setGridSize(QSize(150, 76))
        side.snapshot_list.setResizeMode(QListView.ResizeMode.Adjust)
        side.snapshot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        side.snapshot_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.snapshot_list.setMinimumHeight(80)
        self.snapshot_card.layout().setContentsMargins(8, 2, 8, 2)
        side.btn_snapshot.setText("+ Snapshot")
        side.btn_snapshot.setFixedWidth(110)
        side.snapshot_list.model().rowsInserted.connect(self.decorate_snapshot)
        self.snapshot_card.layout().itemAt(0).layout().itemAt(0).widget().hide()
        self.history_card.layout().itemAt(0).widget().hide()
        side.history.setToolTip("Registro delle modifiche. Usa Annulla/Ripristina o un precedente snapshot per tornare indietro.")

    def decorate_snapshot(self, parent, first, last):
        w = self.window
        if getattr(w.editor_sidebar, "_restoring_snapshots", False):
            return
        image = w.after_rgb8
        if image is None:
            return
        icon = QIcon(QPixmap.fromImage(numpy_to_qimage(image)).scaled(
            110, 65, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        for i in range(first, last + 1):
            item = w.editor_sidebar.snapshot_list.item(i)
            item.setIcon(icon)
            item.setToolTip("Doppio clic per ripristinare " + item.text())

    def build_stack_steps(self):
        self.steps = QFrame()
        row = QHBoxLayout(self.steps)
        row.setContentsMargins(2, 0, 2, 4)
        self.step_buttons = []
        for index, (title, callback) in enumerate((
                ("Importa", lambda: self.window.stack_sidebar_scroll.verticalScrollBar().setValue(0)),
                ("Controlla", lambda: self.show_dock(self.window.dock_frames)),
                ("Stack", lambda: self.window.btn_stack.click()),
                ("Risultato", lambda: self.window._set_workspace("editor")))):
            button = AnimatedButton(f"0{index + 1}   {title}")
            button.setCheckable(True)
            button.clicked.connect(callback)
            row.addWidget(button, 1)
            self.step_buttons.append(button)
        root = self.window._v14_legacy_content.layout()
        root.insertWidget(root.indexOf(self.split), self.steps)
        self.window.stack_sidebar_scroll.setMinimumWidth(330)
        self.window.stack_sidebar_scroll.setMaximumWidth(490)

    def show_dock(self, dock):
        dock.show()
        dock.raise_()

    def build_overlay(self):
        w = self.window
        self.empty = QFrame(w.view.viewport())
        self.empty.setObjectName("emptyCanvas")
        row = QVBoxLayout(self.empty)
        row.setContentsMargins(28, 20, 28, 20)
        self.empty_title = QLabel("Il tuo prossimo cielo inizia qui")
        self.empty_title.setProperty("role", "v14PageTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.empty_title)
        self.empty_body = QLabel("Apri un'immagine per iniziare lo sviluppo.\nRAW · FITS · TIFF · PNG · JPEG")
        self.empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_body.setWordWrap(True)
        self.empty_body.setProperty("role", "muted")
        row.addWidget(self.empty_body)
        self.empty_open = AnimatedButton("Apri immagine…")
        self.empty_open.clicked.connect(lambda: w.open_image() if self.current_route == "editor" else w.import_session())
        row.addWidget(self.empty_open, alignment=Qt.AlignmentFlag.AlignCenter)
        self.handle = CompareHandle(self)
        self.before = QLabel("Prima", w.view.viewport())
        self.after = QLabel("Dopo", w.view.viewport())
        for label in (self.before, self.after):
            label.setObjectName("compareBadge")
            label.setFixedSize(62, 28)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.view.viewport().installEventFilter(self)
        w.compare_slider.valueChanged.connect(self.position_overlay)
        w.btn_compare.toggled.connect(self.position_overlay)
        w.view.zoom_changed.connect(self.position_overlay)
        w.view.horizontalScrollBar().valueChanged.connect(self.position_overlay)
        w.view.verticalScrollBar().valueChanged.connect(self.position_overlay)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_state)
        self.timer.start()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.position_overlay()
        return super().eventFilter(obj, event)

    def position_overlay(self, *_):
        w = self.window
        viewport = w.view.viewport()
        width, height = viewport.width(), viewport.height()
        self.empty.resize(min(440, max(260, width - 30)), 175)
        self.empty.move((width - self.empty.width()) // 2, (height - 175) // 2)
        compare = (self.current_route == "editor" and w.btn_compare.isChecked() and w.before_rgb8 is not None and w.after_rgb8 is not None)
        for widget in (self.handle, self.before, self.after):
            widget.setVisible(compare)
        if compare:
            from PySide6.QtCore import QPointF
            x = w.view.sceneRect().width() * w.compare_slider.value() / 100
            point = w.view.mapFromScene(QPointF(x, 0))
            self.handle.move(max(0, min(width - 32, point.x() - 16)), height // 2 - 16)
            self.before.move(12, 12)
            self.after.move(width - 74, 12)
            self.handle.raise_()

    def select_category(self, item, previous=None):
        if item is None:
            return
        w = self.window
        key = item.data(Qt.ItemDataRole.UserRole)
        if key == "layers":
            self.inspector.setCurrentWidget(w.dock_layers)
            w.dock_layers.show()
        else:
            self.inspector.setCurrentWidget(w.dock_develop)
            w.dock_develop.show()
            w.develop_panel.show_section(key)

    def sync_mode(self):
        w = self.window
        advanced = w.ui_mode == "advanced"
        # Simple mode keeps the essentials in view; switching back preserves every value.
        for index in (4, 5, 6):
            self.nav.item(index).setHidden(not advanced)
        if not advanced and self.nav.currentRow() >= 4:
            self.nav.setCurrentRow(0)
        self.stack_mode.setText(tr("Avanzata" if advanced else "Semplice"))
        self.select_category(self.nav.currentItem())

    def show_menu(self):
        w = self.window
        menu = QMenu(w)
        for text, callback, enabled in (
            ("Apri progetto…", lambda: w.open_project(), True),
            ("Salva progetto…", lambda: w.save_project(), True),
            ("Frame", lambda: self.show_dock(w.dock_frames), self.current_route == "stack"),
            ("Registro", lambda: self.show_dock(w.dock_log), self.current_route == "stack"),
            ("Smista file…", w.sort_files, self.current_route == "stack"),
            ("Elaborazione a lotti…", w.run_batch, self.current_route == "stack"),
            ("Report…", w.save_report, w.btn_report.isEnabled())):
            action = menu.addAction(text)
            action.setEnabled(enabled)
            action.triggered.connect(lambda checked=False, cb=callback: cb())
        if self.current_route == "stack":
            live = menu.addAction("Live stacking")
            live.setCheckable(True)
            live.setChecked(w.btn_live.isChecked())
            live.toggled.connect(w.btn_live.setChecked)
        menu.exec(w.v14_context_secondary.mapToGlobal(QPoint(0, w.v14_context_secondary.height())))

    def remember_sizes(self, *_):
        if self.current_route in ("editor", "stack") and not self.focus_button.isChecked():
            sizes = self.split.sizes()
            if sizes[2] > 0:
                self.panel_sizes[self.current_route] = sizes
                QSettings("AstroStack", "AstroStack").setValue("render_sizes_" + self.current_route, sizes)

    def toggle_focus(self, checked):
        if self.current_route != "editor":
            return
        self.side_scroll.setVisible(not checked)
        self.inspector.setVisible(not checked)
        self.filmstrip.setVisible(not checked)
        QTimer.singleShot(0, self.position_overlay)

    def route(self, mode):
        w = self.window
        self.current_route = mode
        editor = mode == "editor"
        self.toolbar.setVisible(editor)
        w.context_bar.hide()
        w.v14_topbar.setVisible(not editor)
        self.stack_mode.setVisible(mode == "stack")
        self.steps.setVisible(mode == "stack")
        self.side_scroll.setVisible(editor)
        self.inspector.setVisible(editor)
        self.filmstrip.setVisible(editor)
        w.btn_proj_save.setVisible(editor)
        w.btn_ui_mode.setVisible(mode in ("editor", "stack"))
        self.sync_mode()
        if editor:
            self.focus_button.setChecked(False)
            self.select_category(self.nav.currentItem())
            self.empty_body.setText(tr("Apri un'immagine per iniziare lo sviluppo.\nRAW · FITS · TIFF · PNG · JPEG"))
            self.empty_open.setText(tr("Apri immagine…"))
        else:
            w.dock_develop.hide()
            w.dock_layers.hide()
            self.empty_body.setText("Aggiungi Light e frame di calibrazione dal pannello a sinistra.\nControlla la selezione, poi avvia lo stack.")
            self.empty_open.setText(tr("Importa sessione…"))
        # Old workspace handlers can reveal this legacy button; keep a single Open action.
        w.btn_open.hide()
        w.preview_label.show()
        sizes = self.panel_sizes.get(mode)
        if sizes is None:
            saved = QSettings("AstroStack", "AstroStack").value("render_sizes_" + mode)
            if isinstance(saved, list) and len(saved) == 4:
                try:
                    sizes = [int(x) for x in saved]
                except (TypeError, ValueError):
                    pass
        if mode in ("editor", "stack"):
            self.split.setSizes(sizes or ([0, 225, max(450, w.width() - 600), 350] if editor else [375, 0, 900, 0]))
        self.update_state()

    def update_state(self):
        w = self.window
        has_image = w.current_image is not None
        self.empty.setVisible(not w.view._has_image and self.current_route in ("editor", "stack"))
        self.undo_button.setEnabled(len(w._dev_undo) > 1)
        self.redo_button.setEnabled(bool(w._dev_redo))
        w.editor_sidebar.btn_snapshot.setEnabled(has_image)
        w.editor_sidebar.preset_list.setEnabled(has_image)
        w.btn_compare.setEnabled(has_image)
        for widget in (w.develop_panel.scroll, w.develop_panel.btn_pick, w.develop_panel.btn_auto,
                       w.develop_panel.btn_assist, w.develop_panel.btn_reset):
            widget.setEnabled(has_image)
        self.step_buttons[2].setEnabled(w.btn_stack.isEnabled())
        self.step_buttons[3].setEnabled(w.result is not None)
        running = w.worker is not None and w.worker.isRunning()
        active = 3 if w.result is not None and not running else 2 if running else 0
        for i, button in enumerate(self.step_buttons):
            button.setChecked(i == active)
        self.position_overlay()

    def install_callbacks(self):
        w = self.window
        for action in w.actions():
            if action.shortcut().toString() == "Ctrl+D":
                action.triggered.disconnect()
                action.triggered.connect(lambda: self.focus_button.setChecked(False))
        # Layer operations keep their established .show/.raise_ behavior on embedded docks.
        w.dock_layers.visibilityChanged.connect(
            lambda visible: self.inspector.setCurrentWidget(w.dock_layers) if visible and self.current_route == "editor" else None)
        original = w._on_rendered
        def rendered(this, rgb8):
            original(rgb8)
            self.update_state()
        w._on_rendered = types.MethodType(rendered, w)

    def refresh_theme(self):
        w = self.window
        w.view.setStyleSheet(f"QGraphicsView {{ background: {TH.BG}; border: none; }}")
        self.handle.setStyleSheet(f"background: {TH.PANEL}; color: {TH.TEXT}; border: 1px solid {TH.ACCENT}; border-radius: 16px; padding: 0;")
        for label in (self.before, self.after):
            label.setStyleSheet(f"background: {TH.PANEL}; color: {TH.TEXT}; border: 1px solid {TH.BORDER}; border-radius: 5px;")


def install(window):
    window.render_workspace = RenderWorkspace(window)
