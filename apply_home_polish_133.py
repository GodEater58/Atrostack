from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "source" / "app" / "astrostack" / "gui" / "ux_v13.py"
TEST = ROOT / "source" / "app" / "tests" / "test_home_133.py"

NEW_HOME = 'def _install_home(window):\n    """Home 1.3.3: azioni principali, progetto recente e guida rapida."""\n    from astrostack import __version__\n\n    root = _main_layout(window)\n    splitter = _find_splitter(window)\n\n    if splitter is None:\n        return\n\n    window.main_splitter = splitter\n\n    panel = QFrame()\n    panel.setProperty("role", "panel")\n\n    layout = QVBoxLayout(panel)\n    layout.setContentsMargins(48, 36, 48, 36)\n    layout.setSpacing(18)\n\n    hero = QHBoxLayout()\n    hero.setSpacing(24)\n\n    hero_text = QVBoxLayout()\n    hero_text.setSpacing(6)\n\n    eyebrow = QLabel("ASTROSTACK")\n    eyebrow.setProperty("role", "section")\n    hero_text.addWidget(eyebrow)\n\n    title = QLabel(\n        "Dal RAW al cielo finito,\\n"\n        "con un flusso più semplice."\n    )\n    title.setProperty("role", "title")\n    title.setWordWrap(True)\n    hero_text.addWidget(title)\n\n    subtitle = QLabel(\n        "Stacking, calibrazione e sviluppo fotografico "\n        "in un\'unica applicazione. Scegli da dove vuoi iniziare."\n    )\n    subtitle.setProperty("role", "muted")\n    subtitle.setWordWrap(True)\n    hero_text.addWidget(subtitle)\n\n    hero.addLayout(hero_text, 1)\n\n    hero_meta = QVBoxLayout()\n    hero_meta.setSpacing(4)\n\n    window.home_version_label = QLabel(f"v{__version__}")\n    window.home_version_label.setProperty("role", "sectionTitle")\n    window.home_version_label.setAlignment(\n        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop\n    )\n    hero_meta.addWidget(window.home_version_label)\n\n    local_label = QLabel("Elaborazione locale • progetto offline-first")\n    local_label.setProperty("role", "muted")\n    local_label.setAlignment(Qt.AlignmentFlag.AlignRight)\n    hero_meta.addWidget(local_label)\n    hero_meta.addStretch(1)\n\n    hero.addLayout(hero_meta)\n    layout.addLayout(hero)\n\n    section = QLabel("INIZIA")\n    section.setProperty("role", "section")\n    layout.addWidget(section)\n\n    cards = QHBoxLayout()\n    cards.setSpacing(12)\n\n    window.btn_home_stack = AnimatedButton("Nuovo stack", "primary")\n    window.btn_home_editor = AnimatedButton("Apri nell\'Editor…")\n    window.btn_home_project = AnimatedButton("Apri progetto…")\n\n    window.btn_home_stack.clicked.connect(\n        lambda: window._set_workspace("stack")\n    )\n    window.btn_home_editor.clicked.connect(window._enter_editor)\n    window.btn_home_project.clicked.connect(lambda: window.open_project())\n\n    def add_card(kicker, heading, description, button):\n        card = QFrame()\n        card.setProperty("role", "panel")\n\n        card_layout = QVBoxLayout(card)\n        card_layout.setContentsMargins(18, 16, 18, 16)\n        card_layout.setSpacing(7)\n\n        tag = QLabel(kicker)\n        tag.setProperty("role", "section")\n        card_layout.addWidget(tag)\n\n        heading_label = QLabel(heading)\n        heading_label.setProperty("role", "sectionTitle")\n        heading_label.setWordWrap(True)\n        card_layout.addWidget(heading_label)\n\n        description_label = QLabel(description)\n        description_label.setProperty("role", "muted")\n        description_label.setWordWrap(True)\n        card_layout.addWidget(description_label)\n\n        card_layout.addStretch(1)\n        card_layout.addWidget(button)\n\n        cards.addWidget(card, 1)\n\n    add_card(\n        "STACK",\n        "Combina i tuoi scatti",\n        "Importa Light, Dark, Flat e Bias. "\n        "AstroStack calibra, allinea, valuta e combina i frame.",\n        window.btn_home_stack,\n    )\n    add_card(\n        "EDITOR",\n        "Sviluppa una foto",\n        "Apri direttamente RAW, FITS, TIFF, PNG o JPG "\n        "senza dover creare prima uno stack.",\n        window.btn_home_editor,\n    )\n    add_card(\n        "PROGETTI",\n        "Riprendi il lavoro",\n        "Apri un progetto .astrostack con sviluppo, "\n        "livelli, snapshot e impostazioni già salvati.",\n        window.btn_home_project,\n    )\n\n    layout.addLayout(cards)\n\n    recent = QFrame()\n    recent.setProperty("role", "panel")\n\n    recent_layout = QHBoxLayout(recent)\n    recent_layout.setContentsMargins(18, 14, 18, 14)\n    recent_layout.setSpacing(16)\n\n    recent_text = QVBoxLayout()\n    recent_text.setSpacing(3)\n\n    recent_title = QLabel("CONTINUA DA DOVE ERI RIMASTO")\n    recent_title.setProperty("role", "section")\n    recent_text.addWidget(recent_title)\n\n    window.home_recent_name = QLabel("Nessun progetto recente")\n    window.home_recent_name.setProperty("role", "sectionTitle")\n    recent_text.addWidget(window.home_recent_name)\n\n    window.home_recent_path = QLabel("Salva un progetto per ritrovarlo qui.")\n    window.home_recent_path.setProperty("role", "muted")\n    window.home_recent_path.setWordWrap(True)\n    recent_text.addWidget(window.home_recent_path)\n\n    recent_layout.addLayout(recent_text, 1)\n\n    window.btn_home_recent = AnimatedButton("Continua")\n    window.btn_home_recent.clicked.connect(lambda: _open_recent(window))\n    recent_layout.addWidget(window.btn_home_recent)\n\n    layout.addWidget(recent)\n\n    footer = QHBoxLayout()\n    footer.setSpacing(12)\n\n    window.home_mode_hint = QLabel(\n        "Parti in modalità Semplice; passa ad Avanzata "\n        "quando vuoi tutti i controlli."\n    )\n    window.home_mode_hint.setProperty("role", "muted")\n    window.home_mode_hint.setWordWrap(True)\n    footer.addWidget(window.home_mode_hint, 1)\n\n    drag_hint = QLabel(\n        "Suggerimento: puoi trascinare file e cartelle "\n        "direttamente dentro AstroStack."\n    )\n    drag_hint.setProperty("role", "muted")\n    drag_hint.setWordWrap(True)\n    drag_hint.setAlignment(Qt.AlignmentFlag.AlignRight)\n    footer.addWidget(drag_hint, 1)\n\n    layout.addLayout(footer)\n    layout.addStretch(1)\n\n    window.home_panel = panel\n\n    index = root.indexOf(splitter)\n    root.insertWidget(index, panel, 1)\n\n    _refresh_recent_button(window)\n'
NEW_RECENT = 'def _refresh_recent_button(window):\n    if not hasattr(window, "btn_home_recent"):\n        return\n\n    path = str(\n        QSettings("AstroStack", "AstroStack").value("recent_project", "") or ""\n    )\n\n    available = bool(path and os.path.isfile(path))\n    window.btn_home_recent.setEnabled(available)\n\n    if available:\n        window.btn_home_recent.setText("Continua")\n        window.btn_home_recent.setToolTip(path)\n\n        if hasattr(window, "home_recent_name"):\n            window.home_recent_name.setText(os.path.basename(path))\n\n        if hasattr(window, "home_recent_path"):\n            window.home_recent_path.setText(path)\n\n    elif path:\n        window.btn_home_recent.setText("Non disponibile")\n        window.btn_home_recent.setToolTip(\n            "Il progetto recente non è più nel percorso salvato."\n        )\n\n        if hasattr(window, "home_recent_name"):\n            window.home_recent_name.setText("Progetto recente non trovato")\n\n        if hasattr(window, "home_recent_path"):\n            window.home_recent_path.setText(path)\n\n    else:\n        window.btn_home_recent.setText("Continua")\n        window.btn_home_recent.setToolTip("")\n\n        if hasattr(window, "home_recent_name"):\n            window.home_recent_name.setText("Nessun progetto recente")\n\n        if hasattr(window, "home_recent_path"):\n            window.home_recent_path.setText(\n                "Salva un progetto per ritrovarlo qui."\n            )\n'
TEST_CONTENT = '"""Smoke test Home AstroStack 1.3.3."""\nfrom __future__ import annotations\n\nimport os\nimport sys\nimport tempfile\n\nos.environ.setdefault("QT_QPA_PLATFORM", "offscreen")\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\nfrom PySide6.QtCore import QSettings\nfrom PySide6.QtWidgets import QApplication\n\nfrom astrostack.gui.main_window import MainWindow\nfrom astrostack.gui.ux_v13 import _refresh_recent_button, install\n\n\ndef main() -> int:\n    with tempfile.TemporaryDirectory() as td:\n        QSettings.setDefaultFormat(QSettings.Format.IniFormat)\n        QSettings.setPath(\n            QSettings.Format.IniFormat,\n            QSettings.Scope.UserScope,\n            td,\n        )\n\n        settings = QSettings("AstroStack", "AstroStack")\n        settings.setValue("ui_mode", "simple")\n        settings.remove("recent_project")\n        settings.sync()\n\n        app = QApplication.instance() or QApplication([])\n\n        win = MainWindow()\n        install(win)\n        win.show()\n        app.processEvents()\n\n        assert hasattr(win, "home_panel")\n        assert hasattr(win, "home_version_label")\n        assert win.home_version_label.text() == "v1.3.3-preview"\n        assert win.btn_home_stack.text() == "Nuovo stack"\n        assert win.btn_home_editor.text() == "Apri nell\'Editor…"\n        assert win.btn_home_project.text() == "Apri progetto…"\n        assert not win.btn_home_recent.isEnabled()\n        assert win.home_recent_name.text() == "Nessun progetto recente"\n\n        project = os.path.join(td, "M31.astrostack")\n        with open(project, "w", encoding="utf-8") as handle:\n            handle.write("{}")\n\n        settings.setValue("recent_project", project)\n        settings.sync()\n\n        _refresh_recent_button(win)\n\n        assert win.btn_home_recent.isEnabled()\n        assert win.home_recent_name.text() == "M31.astrostack"\n        assert win.home_recent_path.text() == project\n\n        win._set_workspace("stack")\n        app.processEvents()\n        assert win.home_panel.isHidden()\n\n        win.close()\n        app.processEvents()\n\n    print("ASTROSTACK_133_HOME_OK")\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'


def current_branch():
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        return ""


def replace_between(text, start, end, replacement):
    a = text.find(start)
    if a < 0:
        raise RuntimeError("Marcatore iniziale non trovato: " + start)
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError("Marcatore finale non trovato: " + end)
    return text[:a] + replacement.rstrip() + "\n\n\n" + text[b:]


def main():
    if not TARGET.is_file():
        print("ERRORE: file non trovato:", TARGET)
        return 2

    branch = current_branch()
    if branch and branch != "astrostack-1.3.3":
        print("ERRORE: sei sul branch", branch)
        print("Passa prima ad astrostack-1.3.3")
        return 3

    original = TARGET.read_text(encoding="utf-8-sig")

    if "Dal RAW al cielo finito" in original:
        print("La Home 1.3.3 risulta già applicata.")
        if not TEST.exists():
            TEST.write_text(TEST_CONTENT, encoding="utf-8")
        return 0

    updated = replace_between(
        original,
        "def _install_home(window):",
        "def _show_home(window):",
        NEW_HOME,
    )
    updated = replace_between(
        updated,
        "def _refresh_recent_button(window):",
        "def _open_project_path(",
        NEW_RECENT,
    )

    for marker in (
        "Dal RAW al cielo finito",
        "home_version_label",
        "home_recent_name",
        'AnimatedButton("Nuovo stack"',
    ):
        if marker not in updated:
            raise RuntimeError("Controllo interno fallito: " + marker)

    backup = TARGET.with_suffix(".py.home133.bak")
    backup.write_text(original, encoding="utf-8")
    TARGET.write_text(updated, encoding="utf-8")
    TEST.write_text(TEST_CONTENT, encoding="utf-8")

    subprocess.check_call(
        [sys.executable, "-m", "py_compile", str(TARGET), str(TEST)],
        cwd=ROOT,
    )

    print("ASTROSTACK_HOME_133_APPLIED")
    print("Backup:", backup)
    print("Test:", TEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
