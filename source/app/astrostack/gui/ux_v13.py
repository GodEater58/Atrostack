"""UX aggiuntiva AstroStack 1.3.

Mantiene il core 1.2 stabile e aggiunge Home, modalitÃ  semplice,
recovery, riepilogo stack e preset astronomici.
"""
from __future__ import annotations

import os
import time
import types

from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
)

from ..core import project as project_io
from ..core.develop import DevelopParams
from ..core.pipeline import Settings, StackResult
from . import theme as TH
from .i18n import tr
from .widgets import AnimatedButton
from .about_dialog import AboutDiagnosticsDialog


PRESETS = (
    ("natural", "Naturale"),
    ("galaxy", "Galassia"),
    ("nebula", "Nebulosa"),
    ("cluster", "Ammasso stellare"),
    ("milkyway", "Via Lattea"),
    ("moon", "Luna"),
    ("contrast", "PiÃ¹ contrasto"),
    ("detail", "Dettaglio massimo"),
    ("soft", "Versione morbida"),
    ("mono", "Mono / Ha"),
)


def install(window):
    if getattr(window, "_ux_v13_installed", False):
        return

    window._ux_v13_installed = True

    qs = QSettings("AstroStack", "AstroStack")

    window.ui_mode = str(
        qs.value("ui_mode", "simple")
    )

    if window.ui_mode not in (
        "simple",
        "advanced",
    ):
        window.ui_mode = "simple"

    base = (
        os.environ.get("LOCALAPPDATA")
        or os.path.expanduser("~")
    )

    window._recovery_path = os.path.join(
        base,
        "AstroStack",
        "recovery.astrostack",
    )

    _install_home(window)
    _install_mode_button(window)
    _install_about_button(window)
    _wrap_workspace(window)
    _install_presets(window)
    _install_projects(window)
    _install_stack_summary(window)

    window._autosave_v13 = QTimer(window)
    window._autosave_v13.setInterval(120000)
    window._autosave_v13.timeout.connect(
        lambda: _autosave_recovery(window)
    )
    window._autosave_v13.start()

    app = QApplication.instance()

    if app is not None:
        app.aboutToQuit.connect(
            lambda: _cleanup_recovery(window)
        )

    _apply_ui_mode(window)
    _show_home(window)

    QTimer.singleShot(
        300,
        lambda: _maybe_offer_recovery(window),
    )

    QTimer.singleShot(
        15000,
        lambda: _autosave_recovery(window),
    )


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

def _main_layout(window):
    return window.centralWidget().layout()


def _find_splitter(window):
    root = _main_layout(window)

    for i in range(root.count()):
        widget = root.itemAt(i).widget()

        if isinstance(widget, QSplitter):
            return widget

    return None


def _install_home(window):
    root = _main_layout(window)

    splitter = _find_splitter(window)

    if splitter is None:
        return

    window.main_splitter = splitter

    panel = QFrame()
    panel.setProperty("role", "panel")

    layout = QVBoxLayout(panel)

    layout.setContentsMargins(
        44,
        40,
        44,
        40,
    )

    layout.setSpacing(14)
    layout.addStretch(1)

    title = QLabel(
        "Benvenuto in AstroStack"
    )

    title.setProperty(
        "role",
        "title",
    )

    layout.addWidget(title)

    subtitle = QLabel(
        "Scegli cosa vuoi fare. "
        "Puoi creare uno stack oppure "
        "aprire direttamente una fotografia "
        "nell'Editor."
    )

    subtitle.setProperty(
        "role",
        "muted",
    )

    subtitle.setWordWrap(True)

    layout.addWidget(subtitle)
    layout.addSpacing(10)

    row = QHBoxLayout()
    row.setSpacing(10)

    window.btn_home_stack = AnimatedButton(
        "âœ¦  Nuovo stack",
        "primary",
    )

    window.btn_home_editor = AnimatedButton(
        "Apri nell'Editorâ€¦"
    )

    window.btn_home_project = AnimatedButton(
        "Apri progettoâ€¦"
    )

    window.btn_home_stack.clicked.connect(
        lambda:
            window._set_workspace("stack")
    )

    window.btn_home_editor.clicked.connect(
        window._enter_editor
    )

    window.btn_home_project.clicked.connect(
        lambda:
            window.open_project()
    )

    row.addWidget(
        window.btn_home_stack
    )

    row.addWidget(
        window.btn_home_editor
    )

    row.addWidget(
        window.btn_home_project
    )

    layout.addLayout(row)

    window.btn_home_recent = AnimatedButton(
        "Continua ultimo progetto"
    )

    window.btn_home_recent.clicked.connect(
        lambda:
            _open_recent(window)
    )

    layout.addWidget(
        window.btn_home_recent
    )

    hint = QLabel(
        "Puoi anche trascinare immagini o "
        "cartelle direttamente dentro AstroStack."
    )

    hint.setProperty(
        "role",
        "muted",
    )

    hint.setWordWrap(True)

    layout.addWidget(hint)
    layout.addStretch(2)

    window.home_panel = panel

    index = root.indexOf(splitter)

    root.insertWidget(
        index,
        panel,
        1,
    )

    _refresh_recent_button(window)


def _show_home(window):
    if not hasattr(
        window,
        "home_panel",
    ):
        return

    window.home_panel.show()

    if hasattr(
        window,
        "main_splitter",
    ):
        window.main_splitter.hide()

    if hasattr(
        window,
        "context_bar",
    ):
        window.context_bar.hide()


def _leave_home(window):
    if hasattr(
        window,
        "home_panel",
    ):
        window.home_panel.hide()

    if hasattr(
        window,
        "main_splitter",
    ):
        window.main_splitter.show()

    if hasattr(
        window,
        "context_bar",
    ):
        window.context_bar.show()


# ---------------------------------------------------------
# MODALITÃ€ SEMPLICE / AVANZATA
# ---------------------------------------------------------

def _install_mode_button(window):
    root = _main_layout(window)

    head = root.itemAt(0).layout()

    if head is None:
        return

    button = AnimatedButton(
        "Semplice"
    )

    button.setToolTip(
        "Alterna tra i controlli essenziali "
        "e tutti gli strumenti avanzati."
    )

    button.clicked.connect(
        lambda:
            _toggle_ui_mode(window)
    )

    window.btn_ui_mode = button

    index = head.indexOf(
        window.lang_switch
    )

    if index < 0:
        head.addWidget(button)

    else:
        head.insertWidget(
            index,
            button,
        )


def _install_about_button(window):
    """Aggiunge l'accesso a Informazioni/Diagnostica nella barra superiore."""
    root = _main_layout(window)
    head = root.itemAt(0).layout()
    if head is None:
        return

    button = AnimatedButton("Info")
    button.setToolTip(
        "Informazioni su AstroStack e strumenti di diagnostica."
    )

    def show_about():
        dialog = AboutDiagnosticsDialog(window)
        dialog.exec()

    button.clicked.connect(show_about)
    window.btn_about = button

    index = head.indexOf(window.lang_switch)
    if index < 0:
        head.addWidget(button)
    else:
        head.insertWidget(index, button)


def _toggle_ui_mode(window):
    window.ui_mode = (
        "advanced"
        if window.ui_mode == "simple"
        else "simple"
    )

    QSettings(
        "AstroStack",
        "AstroStack",
    ).setValue(
        "ui_mode",
        window.ui_mode,
    )

    _apply_ui_mode(window)

    window.toast.show_message(
        "ModalitÃ  avanzata"
        if window.ui_mode == "advanced"
        else "ModalitÃ  semplice"
    )


def _apply_ui_mode(window):
    advanced = (
        window.ui_mode == "advanced"
    )

    if hasattr(
        window,
        "btn_ui_mode",
    ):
        window.btn_ui_mode.setText(
            "Avanzata"
            if advanced
            else "Semplice"
        )

    if hasattr(
        window,
        "settings_panel",
    ):
        window.settings_panel.adv_btn.setVisible(
            advanced
        )

        if hasattr(
            window.settings_panel,
            "_collapser",
        ):
            window.settings_panel \
                ._collapser \
                .setVisible(
                    advanced
                )

    if hasattr(
        window,
        "tools",
    ):
        window.tools.setVisible(
            advanced
        )

    editor = (
        window.workspace == "editor"
    )

    for name in (
        "btn_sort",
        "btn_live",
        "btn_batch",
        "btn_report",
        "btn_frames",
        "btn_log",
    ):
        widget = getattr(
            window,
            name,
            None,
        )

        if widget is not None:
            widget.setVisible(
                advanced
                and not editor
            )

    if hasattr(
        window,
        "btn_restack",
    ):
        window.btn_restack.setVisible(
            advanced
            and not editor
        )

    if hasattr(
        window,
        "btn_layers",
    ):
        window.btn_layers.setVisible(
            advanced
        )

    if not advanced:
        for name in (
            "dock_layers",
            "dock_log",
            "dock_frames",
        ):
            dock = getattr(
                window,
                name,
                None,
            )

            if dock is not None:
                dock.hide()


def _wrap_workspace(window):
    original = window._set_workspace

    def wrapped(self, mode):
        _leave_home(self)

        original(mode)

        _apply_ui_mode(self)

    window._set_workspace = types.MethodType(
        wrapped,
        window,
    )


# ---------------------------------------------------------
# PRESET EDITOR
# ---------------------------------------------------------

def _install_presets(window):
    sidebar = window.editor_sidebar

    sidebar.PRESETS = PRESETS

    sidebar.preset_list.clear()

    for key, label in PRESETS:
        item = QListWidgetItem(
            label
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            key,
        )

        sidebar.preset_list.addItem(
            item
        )

    try:
        sidebar.preset_requested.disconnect()
    except Exception:
        pass

    def apply_preset(self, key):
        p = DevelopParams()

        if not self.nonlinear:
            p.stretch_type = "arcsinh"
            p.stretch_bg = 23.0

        if key == "natural":
            p.vibrance = 8.0
            p.clarity = 5.0

        elif key == "galaxy":
            p.contrast = 18.0
            p.blacks = -12.0
            p.vibrance = 18.0
            p.saturation = 4.0
            p.clarity = 18.0
            p.dehaze = 12.0
            p.nr_luminance = 10.0
            p.star_reduce = 8.0

        elif key == "nebula":
            p.contrast = 12.0
            p.vibrance = 28.0
            p.saturation = 10.0
            p.clarity = 12.0
            p.dehaze = 16.0
            p.nr_luminance = 10.0

        elif key == "cluster":
            p.contrast = 10.0
            p.highlights = -15.0
            p.vibrance = 10.0
            p.clarity = 12.0
            p.sharpen = 35.0
            p.nr_luminance = 8.0

        elif key == "milkyway":
            p.exposure = 0.15
            p.contrast = 16.0
            p.vibrance = 24.0
            p.saturation = 8.0
            p.clarity = 12.0
            p.dehaze = 20.0
            p.nr_luminance = 18.0

        elif key == "moon":
            p.saturation = -70.0
            p.highlights = -25.0
            p.contrast = 25.0
            p.clarity = 30.0
            p.sharpen = 45.0
            p.dehaze = 10.0

        elif key == "contrast":
            p.contrast = 20.0
            p.blacks = -10.0
            p.clarity = 15.0
            p.dehaze = 8.0

        elif key == "detail":
            p.clarity = 25.0
            p.sharpen = 45.0
            p.wavelet_small = 20.0
            p.nr_luminance = 15.0
            p.deconv = 15.0

        elif key == "soft":
            p.contrast = -8.0
            p.highlights = -15.0
            p.clarity = -8.0
            p.nr_luminance = 22.0
            p.nr_color = 18.0
            p.sharpen = 8.0

        elif key == "mono":
            p.saturation = -100.0
            p.contrast = 18.0
            p.clarity = 18.0
            p.dehaze = 12.0

        self.develop_panel.set_params(
            p,
            emit=True,
        )

        labels = dict(PRESETS)

        self.editor_sidebar.add_history(
            "Preset: "
            + labels.get(key, key)
        )

        self.toast.show_message(
            "Preset applicato: "
            + labels.get(key, key)
        )

    window._apply_editor_preset = types.MethodType(
        apply_preset,
        window,
    )

    sidebar.preset_requested.connect(
        window._apply_editor_preset
    )


# ---------------------------------------------------------
# PROGETTI / RECOVERY
# ---------------------------------------------------------

def _install_projects(window):
    original_save = window.save_project
    original_open = window.open_project

    def save_project(
        self,
        checked=False,
    ):
        original_save()

        if self.project_path:
            QSettings(
                "AstroStack",
                "AstroStack",
            ).setValue(
                "recent_project",
                self.project_path,
            )

        _refresh_recent_button(self)

    def open_project(
        self,
        checked=False,
        path=None,
        recovery=False,
    ):
        if not path:
            original_open()

            if self.project_path:
                QSettings(
                    "AstroStack",
                    "AstroStack",
                ).setValue(
                    "recent_project",
                    self.project_path,
                )

            _refresh_recent_button(self)
            _apply_ui_mode(self)

            return

        _open_project_path(
            self,
            path,
            recovery,
        )

    window.save_project = types.MethodType(
        save_project,
        window,
    )

    window.open_project = types.MethodType(
        open_project,
        window,
    )

    try:
        window.btn_proj_save.clicked.disconnect()
    except Exception:
        pass

    try:
        window.btn_proj_open.clicked.disconnect()
    except Exception:
        pass

    window.btn_proj_save.clicked.connect(
        window.save_project
    )

    window.btn_proj_open.clicked.connect(
        window.open_project
    )


def _open_recent(window):
    path = str(
        QSettings(
            "AstroStack",
            "AstroStack",
        ).value(
            "recent_project",
            "",
        ) or ""
    )

    if path and os.path.isfile(path):
        window.open_project(
            path=path
        )


def _refresh_recent_button(window):
    if not hasattr(
        window,
        "btn_home_recent",
    ):
        return

    path = str(
        QSettings(
            "AstroStack",
            "AstroStack",
        ).value(
            "recent_project",
            "",
        ) or ""
    )

    window.btn_home_recent.setEnabled(
        bool(
            path
            and os.path.isfile(path)
        )
    )


def _open_project_path(
    window,
    path,
    recovery=False,
):
    if (
        window.worker is not None
        and window.worker.isRunning()
    ):
        return

    try:
        data = project_io.load_project(
            path
        )

    except Exception as exc:
        QMessageBox.critical(
            window,
            tr(
                "Apertura del progetto "
                "non riuscita"
            ),
            str(exc),
        )
        return

    window.project_path = (
        None
        if recovery
        else path
    )

    for key, zone in window.zones.items():
        zone.set_files(
            [
                p
                for p
                in data["zones"].get(
                    key,
                    [],
                )
                if os.path.exists(p)
            ]
        )

    try:
        settings = Settings(
            **{
                key: value
                for key, value
                in data[
                    "settings"
                ].items()
                if key
                in Settings().__dict__
            }
        )

        window.settings_panel \
            .set_from_settings(
                settings
            )

    except Exception as exc:
        window._log(
            "Impostazioni del progetto "
            "non applicate: "
            + str(exc)
        )

    window.result = None

    window.opened_path = data.get(
        "opened_path"
    )

    window.annotations = data.get(
        "annotations",
        [],
    )

    window._undo = []
    window.layers = []
    window.layer_proxies = []
    window.stars_image = None

    if hasattr(
        window,
        "editor_sidebar",
    ):
        window.editor_sidebar \
            .clear_history()

        window.editor_sidebar \
            .set_snapshots(
                data.get(
                    "ui_state",
                    {},
                ).get(
                    "snapshots",
                    [],
                )
            )

    layers = data.get(
        "layers",
        [],
    )

    if (
        layers
        and layers[0].image
        is not None
    ):
        base_layer = layers[0]

        window.nonlinear = (
            not base_layer.is_linear
        )

        window.dev_params = (
            base_layer.params
        )

        window.develop_panel \
            .set_params(
                window.dev_params,
                emit=False,
            )

        window.layers = layers

        window.layer_proxies = [
            window._make_proxy(
                layer.image
            )
            for layer in layers
        ]

        window.current_image = (
            base_layer.image
        )

        window.proxy = (
            window.layer_proxies[0]
        )

        window.layers_panel \
            .set_layers(
                window.layers,
                select=0,
            )

        window._set_running(False)

        window.dock_develop.show()

        if len(window.layers) > 1:
            window.dock_layers.show()

        window._refresh_preview(
            full=False
        )

        window.preview_label.setText(
            "Progetto: "
            + os.path.basename(path)
        )

    else:
        window.current_image = None
        window.view.clear()

        window._update_ready(
            from_zones=True
        )

    if data.get("missing"):
        window._log(
            "File del progetto non trovati: "
            + ", ".join(
                str(item)
                for item
                in data["missing"]
            )
        )

        window.toast.show_message(
            "Alcuni file del progetto "
            "non sono stati trovati "
            "(vedi Registro)",
            accent=TH.WARN,
        )

    else:
        window.toast.show_message(
            "Progetto aperto"
        )

    preferred = str(
        data.get(
            "ui_state",
            {},
        ).get(
            "workspace",
            "",
        )
    )

    if preferred not in (
        "stack",
        "editor",
    ):
        preferred = (
            "editor"
            if (
                window.current_image
                is not None
                and not any(
                    zone.files
                    for zone
                    in window.zones.values()
                )
            )
            else "stack"
        )

    saved_mode = str(
        data.get(
            "ui_state",
            {},
        ).get(
            "ui_mode",
            "",
        )
    )

    if saved_mode in (
        "simple",
        "advanced",
    ):
        window.ui_mode = saved_mode

    window._set_workspace(
        preferred
    )

    if recovery:
        window.status.setText(
            "Sessione ripristinata "
            "automaticamente."
        )

        window.status.setStyleSheet(
            f"color: {TH.OK};"
        )

        window.toast.show_message(
            "Sessione precedente "
            "ripristinata"
        )

    else:
        QSettings(
            "AstroStack",
            "AstroStack",
        ).setValue(
            "recent_project",
            path,
        )

        window.status.setText(
            f"Progetto aperto: {path}"
        )

        window.status.setStyleSheet(
            f"color: {TH.OK};"
        )

    _refresh_recent_button(
        window
    )


def _autosave_recovery(window):
    if (
        window.worker is not None
        and window.worker.isRunning()
    ):
        return

    has_files = any(
        zone.files
        for zone
        in window.zones.values()
    )

    if (
        window.current_image is None
        and not has_files
    ):
        return

    try:
        os.makedirs(
            os.path.dirname(
                window._recovery_path
            ),
            exist_ok=True,
        )

        project_io.save_project(
            window._recovery_path,
            {
                key: list(
                    zone.files
                )
                for key, zone
                in window.zones.items()
            },
            window.settings_panel
                .to_settings()
                .__dict__,
            window.layers,
            window.current_image,
            not window.nonlinear,
            window.opened_path,
            window.annotations,
            {
                "workspace":
                    window.workspace,

                "ui_mode":
                    window.ui_mode,

                "recovery":
                    True,

                "snapshots":
                    window.editor_sidebar
                        .snapshots()
                    if hasattr(
                        window,
                        "editor_sidebar",
                    )
                    else [],
            },
        )

    except Exception as exc:
        window._log(
            "Autosave recovery "
            "non riuscito: "
            + str(exc)
        )


def _maybe_offer_recovery(window):
    path = getattr(
        window,
        "_recovery_path",
        "",
    )

    if (
        not path
        or not os.path.isfile(path)
    ):
        return

    try:
        age = (
            time.time()
            - os.path.getmtime(path)
        )

        if age > 7 * 24 * 3600:
            os.remove(path)
            return

    except OSError:
        return

    answer = QMessageBox.question(
        window,
        "Ripristino sessione",
        "AstroStack ha trovato una "
        "sessione non chiusa "
        "correttamente.\n\n"
        "Vuoi ripristinarla?",
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No,
    )

    if (
        answer
        == QMessageBox.StandardButton.Yes
    ):
        window.open_project(
            path=path,
            recovery=True,
        )

    else:
        _cleanup_recovery(
            window
        )


def _cleanup_recovery(window):
    path = getattr(
        window,
        "_recovery_path",
        "",
    )

    try:
        if (
            path
            and os.path.isfile(path)
        ):
            os.remove(path)

    except OSError:
        pass


# ---------------------------------------------------------
# RIEPILOGO FINALE
# ---------------------------------------------------------

def _install_stack_summary(window):
    original = window._on_finished

    def finished(
        self,
        result: StackResult,
    ):
        original(result)

        if getattr(
            self,
            "_batch_folder",
            "",
        ):
            return

        if (
            hasattr(
                self,
                "btn_live",
            )
            and self.btn_live.isChecked()
        ):
            return

        _show_stack_summary(
            self,
            result,
        )

    window._on_finished = types.MethodType(
        finished,
        window,
    )


def _show_stack_summary(
    window,
    result,
):
    total = len(
        result.frames
    )

    used = int(
        result.n_used
    )

    rejected = max(
        0,
        total - used,
    )

    settings = (
        window.settings_panel
            .to_settings()
    )

    methods = {
        "auto":
            "Automatico",

        "sigma":
            "Kappa-sigma",

        "winsor":
            "Sigma winsorizzato",

        "linearfit":
            "Linear-fit clipping",

        "mediana":
            "Mediana",

        "media":
            "Media",

        "scie":
            "Scie stellari",
    }

    text = (
        f"Frame analizzati: {total}\n"
        f"Frame utilizzati: {used}\n"
        f"Frame esclusi: {rejected}\n"
        f"Tempo: {result.elapsed:.0f} s\n"
        f"Metodo: "
        f"{methods.get(settings.method, settings.method)}\n"
        f"Drizzle: {settings.drizzle}Ã—\n"
        f"{result.gradient.describe()}"
    )

    box = QMessageBox(
        window
    )

    box.setWindowTitle(
        "Stack completato"
    )

    box.setIcon(
        QMessageBox.Icon.Information
    )

    box.setText(
        "Stack completato con successo"
    )

    box.setInformativeText(
        text
    )

    btn_editor = box.addButton(
        "Apri nell'Editor",
        QMessageBox.ButtonRole.ActionRole,
    )

    btn_export = box.addButton(
        "Esportaâ€¦",
        QMessageBox.ButtonRole.ActionRole,
    )

    box.addButton(
        QMessageBox.StandardButton.Close
    )

    box.exec()

    clicked = box.clickedButton()

    if clicked is btn_editor:
        window._set_workspace(
            "editor"
        )

    elif clicked is btn_export:
        window.save_result()
