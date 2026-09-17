"""AstroStack 1.4 UI refresh.

Ridisegna la shell dell'app senza toccare il motore di stacking.
"""
from __future__ import annotations

import os
import types

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget,
)

from astrostack import __version__
from . import i18n
from . import theme as TH
from .about_dialog import AboutDiagnosticsDialog
from .widgets import AnimatedButton


def _clear_layout(layout):
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        widget = item.widget()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _hide_layout_widgets(layout):
    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
        if child_layout is not None:
            _hide_layout_widgets(child_layout)


def _v14_qss():
    return f"""
QFrame[role="v14Rail"] {{ background: {TH.PANEL}; border-right: 1px solid {TH.BORDER}; }}
QFrame[role="v14Topbar"] {{ background: transparent; border-bottom: 1px solid {TH.BORDER}; }}
QFrame[role="v14Card"] {{ background: {TH.PANEL2}; border: 1px solid {TH.BORDER}; border-radius: 14px; }}
QFrame[role="v14Recent"] {{ background: {TH.PANEL}; border: 1px solid {TH.BORDER}; border-radius: 12px; }}
QLabel[role="v14Brand"] {{ color: {TH.TEXT}; font-size: 18px; font-weight: 700; }}
QLabel[role="v14Hero"] {{ color: {TH.TEXT}; font-size: 30px; font-weight: 700; }}
QLabel[role="v14PageTitle"] {{ color: {TH.TEXT}; font-size: 18px; font-weight: 650; }}
QLabel[role="v14CardTitle"] {{ color: {TH.TEXT}; font-size: 16px; font-weight: 650; }}
QLabel[role="v14Eyebrow"] {{ color: {TH.ACCENT}; font-size: 11px; font-weight: 700; }}
"""


def _apply_v14_style():
    app = QApplication.instance()
    if app is None:
        return
    base = app.styleSheet()
    marker = "/* ASTROSTACK_V14 */"
    if marker in base:
        base = base.split(marker, 1)[0].rstrip()
    app.setStyleSheet(base + "\n" + marker + "\n" + _v14_qss())


def _legacy_content(window):
    return getattr(window, "_v14_legacy_content", None)


def _legacy_root(window):
    content = _legacy_content(window)
    return content.layout() if content is not None else None


def _find_splitter(window):
    return getattr(window, "main_splitter", None)


def _hide_legacy_chrome(window):
    content = window.centralWidget()
    root = content.layout()
    if root is None:
        return
    first_layout = root.itemAt(0).layout() if root.count() else None
    _hide_layout_widgets(first_layout)
    if root.count() > 1:
        rule = root.itemAt(1).widget()
        if rule is not None:
            rule.hide()
    if hasattr(window, "context_bar"):
        window.context_bar.hide()
    root.setContentsMargins(18, 10, 18, 14)
    root.setSpacing(10)


def _make_nav_button(text):
    button = AnimatedButton(text)
    button.setCheckable(True)
    button.setMinimumHeight(42)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return button


def _build_shell(window):
    old = window.takeCentralWidget()
    window._v14_legacy_content = old

    shell = QWidget()
    outer = QHBoxLayout(shell)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    rail = QFrame()
    rail.setProperty("role", "v14Rail")
    rail.setFixedWidth(214)
    rail_layout = QVBoxLayout(rail)
    rail_layout.setContentsMargins(16, 18, 16, 16)
    rail_layout.setSpacing(10)

    brand_row = QHBoxLayout()
    brand_row.setSpacing(9)
    icon_label = QLabel()
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "astrostack.ico")
    if os.path.isfile(icon_path):
        icon_label.setPixmap(QIcon(icon_path).pixmap(30, 30))
    brand_row.addWidget(icon_label)
    brand = QLabel("AstroStack")
    brand.setProperty("role", "v14Brand")
    brand_row.addWidget(brand, 1)
    rail_layout.addLayout(brand_row)

    tagline = QLabel("Astrofotografia, senza rumore.")
    tagline.setProperty("role", "muted")
    tagline.setWordWrap(True)
    rail_layout.addWidget(tagline)
    rail_layout.addSpacing(12)

    nav_group = QButtonGroup(window)
    nav_group.setExclusive(True)
    window.v14_nav_home = _make_nav_button("Home")
    window.v14_nav_stack = _make_nav_button("Stack")
    window.v14_nav_editor = _make_nav_button("Editor")
    window.v14_nav_projects = _make_nav_button("Progetti")
    for button in (window.v14_nav_home, window.v14_nav_stack, window.v14_nav_editor, window.v14_nav_projects):
        nav_group.addButton(button)
        rail_layout.addWidget(button)
    window.v14_nav_group = nav_group
    rail_layout.addStretch(1)

    version = QLabel(f"AstroStack {__version__}")
    version.setProperty("role", "muted")
    version.setWordWrap(True)
    rail_layout.addWidget(version)

    utility = QHBoxLayout()
    utility.setSpacing(6)
    window.v14_btn_info = AnimatedButton("Info", "link")
    window.v14_btn_lang = AnimatedButton("EN" if i18n.language() == "it" else "IT", "link")
    window.v14_btn_theme = AnimatedButton("Tema", "link")
    utility.addWidget(window.v14_btn_info)
    utility.addWidget(window.v14_btn_lang)
    utility.addWidget(window.v14_btn_theme)
    rail_layout.addLayout(utility)

    content_host = QFrame()
    content_layout = QVBoxLayout(content_host)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(0)
    content_layout.addWidget(old)

    outer.addWidget(rail)
    outer.addWidget(content_host, 1)
    window.v14_shell = shell
    window.v14_rail = rail
    window.v14_content_host = content_host
    window.setCentralWidget(shell)


def _build_topbar(window):
    root = _legacy_root(window)
    if root is None:
        return
    top = QFrame()
    top.setProperty("role", "v14Topbar")
    top_layout = QHBoxLayout(top)
    top_layout.setContentsMargins(4, 2, 4, 10)
    top_layout.setSpacing(10)
    titles = QVBoxLayout()
    titles.setSpacing(1)
    window.v14_page_title = QLabel("Home")
    window.v14_page_title.setProperty("role", "v14PageTitle")
    titles.addWidget(window.v14_page_title)
    window.v14_page_subtitle = QLabel("Scegli un flusso di lavoro.")
    window.v14_page_subtitle.setProperty("role", "muted")
    titles.addWidget(window.v14_page_subtitle)
    top_layout.addLayout(titles, 1)
    window.v14_context_action = AnimatedButton("Apri immagine…")
    window.v14_context_action.hide()
    top_layout.addWidget(window.v14_context_action)
    window.v14_context_secondary = AnimatedButton("Apri progetto…")
    window.v14_context_secondary.clicked.connect(lambda: window.open_project())
    top_layout.addWidget(window.v14_context_secondary)
    root.insertWidget(0, top)
    window.v14_topbar = top


def _card(kicker, title, body, button):
    card = QFrame()
    card.setProperty("role", "v14Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(8)
    tag = QLabel(kicker)
    tag.setProperty("role", "v14Eyebrow")
    layout.addWidget(tag)
    heading = QLabel(title)
    heading.setProperty("role", "v14CardTitle")
    heading.setWordWrap(True)
    layout.addWidget(heading)
    desc = QLabel(body)
    desc.setProperty("role", "muted")
    desc.setWordWrap(True)
    layout.addWidget(desc)
    layout.addStretch(1)
    layout.addWidget(button)
    return card


def _rebuild_home(window):
    panel = getattr(window, "home_panel", None)
    if panel is None:
        return
    layout = panel.layout()
    _clear_layout(layout)
    panel.setProperty("role", "panel")
    layout.setContentsMargins(34, 28, 34, 28)
    layout.setSpacing(18)

    hero = QHBoxLayout()
    hero.setSpacing(30)
    hero_text = QVBoxLayout()
    hero_text.setSpacing(6)
    eyebrow = QLabel("ASTROSTACK 1.4")
    eyebrow.setProperty("role", "v14Eyebrow")
    hero_text.addWidget(eyebrow)
    window.v14_home_title = QLabel("Stack, sviluppa e rifinisci il cielo\nin un unico spazio di lavoro.")
    window.v14_home_title.setProperty("role", "v14Hero")
    window.v14_home_title.setWordWrap(True)
    hero_text.addWidget(window.v14_home_title)
    subtitle = QLabel("Un flusso chiaro per calibrazione, stacking e post-produzione, più un Editor indipendente per RAW e immagini già pronte.")
    subtitle.setProperty("role", "muted")
    subtitle.setWordWrap(True)
    hero_text.addWidget(subtitle)
    hero.addLayout(hero_text, 1)
    meta = QVBoxLayout()
    meta.setSpacing(4)
    version = QLabel(f"v{__version__}")
    version.setProperty("role", "sectionTitle")
    version.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    meta.addWidget(version)
    local = QLabel("Offline-first • elaborazione locale")
    local.setProperty("role", "muted")
    local.setAlignment(Qt.AlignmentFlag.AlignRight)
    meta.addWidget(local)
    meta.addStretch(1)
    hero.addLayout(meta)
    layout.addLayout(hero)

    cards = QHBoxLayout()
    cards.setSpacing(12)
    stack_btn = AnimatedButton("Nuovo stack", "primary")
    editor_btn = AnimatedButton("Apri Editor")
    project_btn = AnimatedButton("Apri progetto")
    stack_btn.clicked.connect(lambda: window._set_workspace("stack"))
    editor_btn.clicked.connect(window._enter_editor)
    project_btn.clicked.connect(lambda: window.open_project())
    cards.addWidget(_card("STACK", "Dai frame al master", "Importa Light, Dark, Flat e Bias. AstroStack calibra, valuta, allinea e combina i frame.", stack_btn), 1)
    cards.addWidget(_card("EDITOR", "Sviluppo standalone", "Apri RAW, FITS, TIFF, PNG o JPG direttamente nell'Editor con colore, dettaglio, preset, livelli e snapshot.", editor_btn), 1)
    cards.addWidget(_card("PROGETTI", "Riprendi il lavoro", "Riapri un file .astrostack e continua con immagini, impostazioni, livelli e cronologia.", project_btn), 1)
    layout.addLayout(cards)

    recent = QFrame()
    recent.setProperty("role", "v14Recent")
    recent_layout = QHBoxLayout(recent)
    recent_layout.setContentsMargins(18, 14, 18, 14)
    recent_layout.setSpacing(14)
    recent_text = QVBoxLayout()
    recent_text.setSpacing(3)
    label = QLabel("ULTIMO PROGETTO")
    label.setProperty("role", "v14Eyebrow")
    recent_text.addWidget(label)
    window.v14_recent_name = QLabel("Nessun progetto recente")
    window.v14_recent_name.setProperty("role", "v14CardTitle")
    recent_text.addWidget(window.v14_recent_name)
    window.v14_recent_path = QLabel("I progetti salvati compariranno qui.")
    window.v14_recent_path.setProperty("role", "muted")
    window.v14_recent_path.setWordWrap(True)
    recent_text.addWidget(window.v14_recent_path)
    recent_layout.addLayout(recent_text, 1)
    window.v14_recent_open = AnimatedButton("Continua")
    window.v14_recent_open.clicked.connect(lambda: _open_recent(window))
    recent_layout.addWidget(window.v14_recent_open)
    layout.addWidget(recent)

    tips = QHBoxLayout()
    tips.setSpacing(20)
    left_tip = QLabel("Modalità Semplice per partire subito; Avanzata quando vuoi controllare ogni fase.")
    left_tip.setProperty("role", "muted")
    left_tip.setWordWrap(True)
    tips.addWidget(left_tip, 1)
    right_tip = QLabel("Puoi trascinare file o cartelle direttamente dentro AstroStack.")
    right_tip.setProperty("role", "muted")
    right_tip.setWordWrap(True)
    right_tip.setAlignment(Qt.AlignmentFlag.AlignRight)
    tips.addWidget(right_tip, 1)
    layout.addLayout(tips)
    layout.addStretch(1)
    _update_recent(window)


def _build_projects_page(window):
    root = _legacy_root(window)
    splitter = _find_splitter(window)
    if root is None or splitter is None:
        return
    panel = QFrame()
    panel.setProperty("role", "panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(34, 28, 34, 28)
    layout.setSpacing(18)
    eyebrow = QLabel("PROGETTI")
    eyebrow.setProperty("role", "v14Eyebrow")
    layout.addWidget(eyebrow)
    title = QLabel("Il tuo lavoro, sempre riprendibile.")
    title.setProperty("role", "v14Hero")
    title.setWordWrap(True)
    layout.addWidget(title)
    subtitle = QLabel("Apri un progetto esistente oppure salva lo stato corrente con impostazioni, livelli e snapshot.")
    subtitle.setProperty("role", "muted")
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)
    row = QHBoxLayout()
    row.setSpacing(12)
    open_btn = AnimatedButton("Apri progetto…", "primary")
    save_btn = AnimatedButton("Salva progetto…")
    open_btn.clicked.connect(lambda: window.open_project())
    save_btn.clicked.connect(lambda: window.save_project())
    row.addWidget(open_btn)
    row.addWidget(save_btn)
    row.addStretch(1)
    layout.addLayout(row)
    recent = QFrame()
    recent.setProperty("role", "v14Card")
    recent_layout = QVBoxLayout(recent)
    recent_layout.setContentsMargins(20, 18, 20, 18)
    recent_layout.setSpacing(6)
    tag = QLabel("RECENTE")
    tag.setProperty("role", "v14Eyebrow")
    recent_layout.addWidget(tag)
    window.v14_projects_recent_name = QLabel("Nessun progetto recente")
    window.v14_projects_recent_name.setProperty("role", "v14CardTitle")
    recent_layout.addWidget(window.v14_projects_recent_name)
    window.v14_projects_recent_path = QLabel("")
    window.v14_projects_recent_path.setProperty("role", "muted")
    window.v14_projects_recent_path.setWordWrap(True)
    recent_layout.addWidget(window.v14_projects_recent_path)
    window.v14_projects_recent_open = AnimatedButton("Apri ultimo progetto")
    window.v14_projects_recent_open.clicked.connect(lambda: _open_recent(window))
    recent_layout.addWidget(window.v14_projects_recent_open)
    layout.addWidget(recent)
    layout.addStretch(1)
    index = root.indexOf(splitter)
    root.insertWidget(index, panel, 1)
    panel.hide()
    window.v14_projects_panel = panel
    _update_recent(window)


def _recent_path():
    return str(QSettings("AstroStack", "AstroStack").value("recent_project", "") or "")


def _update_recent(window):
    path = _recent_path()
    exists = bool(path and os.path.isfile(path))
    name = os.path.basename(path) if path else "Nessun progetto recente"
    if path and not exists:
        name = "Progetto recente non trovato"
    for attr in ("v14_recent_name", "v14_projects_recent_name"):
        widget = getattr(window, attr, None)
        if widget is not None:
            widget.setText(name)
    for attr in ("v14_recent_path", "v14_projects_recent_path"):
        widget = getattr(window, attr, None)
        if widget is not None:
            widget.setText(path if path else "I progetti salvati compariranno qui.")
    for attr in ("v14_recent_open", "v14_projects_recent_open"):
        button = getattr(window, attr, None)
        if button is not None:
            button.setEnabled(exists)
            button.setToolTip(path if path else "")


def _open_recent(window):
    path = _recent_path()
    if path and os.path.isfile(path):
        window.open_project(path=path)


def _hide_aux_docks(window):
    for name in ("dock_develop", "dock_layers", "dock_frames", "dock_log"):
        dock = getattr(window, name, None)
        if dock is not None:
            dock.hide()


def _set_nav(window, key):
    mapping = {"home": "v14_nav_home", "stack": "v14_nav_stack", "editor": "v14_nav_editor", "projects": "v14_nav_projects"}
    for route, attr in mapping.items():
        button = getattr(window, attr, None)
        if button is not None:
            button.setChecked(route == key)


def _set_topbar(window, title, subtitle, action=None):
    if hasattr(window, "v14_page_title"):
        window.v14_page_title.setText(title)
    if hasattr(window, "v14_page_subtitle"):
        window.v14_page_subtitle.setText(subtitle)
    button = getattr(window, "v14_context_action", None)
    if button is None:
        return
    try:
        button.clicked.disconnect()
    except Exception:
        pass
    if action is None:
        button.hide()
    else:
        text, callback = action
        button.setText(text)
        button.clicked.connect(callback)
        button.show()


def _show_home(window):
    projects = getattr(window, "v14_projects_panel", None)
    if projects is not None:
        projects.hide()
    if hasattr(window, "home_panel"):
        window.home_panel.show()
    splitter = _find_splitter(window)
    if splitter is not None:
        splitter.hide()
    _hide_aux_docks(window)
    _set_nav(window, "home")
    _set_topbar(window, "Home", "Scegli il flusso di lavoro da cui partire.", None)
    _update_recent(window)


def _show_projects(window):
    if hasattr(window, "home_panel"):
        window.home_panel.hide()
    splitter = _find_splitter(window)
    if splitter is not None:
        splitter.hide()
    panel = getattr(window, "v14_projects_panel", None)
    if panel is not None:
        panel.show()
    _hide_aux_docks(window)
    _set_nav(window, "projects")
    _set_topbar(window, "Progetti", "Apri, salva e riprendi le tue sessioni AstroStack.", ("Apri progetto…", lambda: window.open_project()))
    _update_recent(window)


def _sync_workspace(window, mode):
    if hasattr(window, "home_panel"):
        window.home_panel.hide()
    projects = getattr(window, "v14_projects_panel", None)
    if projects is not None:
        projects.hide()
    splitter = _find_splitter(window)
    if splitter is not None:
        splitter.show()
    if mode == "editor":
        _set_nav(window, "editor")
        _set_topbar(window, "Editor", "Sviluppo standalone per RAW, FITS e immagini finite.", ("Apri immagine…", window.open_image))
    else:
        _set_nav(window, "stack")
        _set_topbar(window, "Stack", "Calibra, analizza, allinea e combina i tuoi frame.", ("Importa sessione…", window.import_session))


def _wrap_workspace(window):
    original = window._set_workspace
    def wrapped(self, mode):
        original(mode)
        _sync_workspace(self, mode)
    window._set_workspace = types.MethodType(wrapped, window)


def _wire_navigation(window):
    window.v14_nav_home.clicked.connect(lambda: _show_home(window))
    window.v14_nav_stack.clicked.connect(lambda: window._set_workspace("stack"))
    window.v14_nav_editor.clicked.connect(window._enter_editor)
    window.v14_nav_projects.clicked.connect(lambda: _show_projects(window))
    window.v14_btn_info.clicked.connect(lambda: AboutDiagnosticsDialog(window).exec())

    def toggle_language():
        new_lang = "en" if i18n.language() == "it" else "it"
        window.set_language(new_lang)
        window.v14_btn_lang.setText("IT" if new_lang == "en" else "EN")
    window.v14_btn_lang.clicked.connect(toggle_language)

    def toggle_theme():
        window.toggle_theme()
        _apply_v14_style()
    window.v14_btn_theme.clicked.connect(toggle_theme)


def install(window):
    if getattr(window, "_ux_v14_installed", False):
        return
    window._ux_v14_installed = True
    window.setMinimumSize(1120, 700)
    _hide_legacy_chrome(window)
    _build_shell(window)
    _build_topbar(window)
    _rebuild_home(window)
    _build_projects_page(window)
    _wrap_workspace(window)
    _wire_navigation(window)
    _apply_v14_style()
    _show_home(window)
