"""Smoke test Home AstroStack 1.3.3."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from astrostack.gui.main_window import MainWindow
from astrostack.gui.ux_v13 import _refresh_recent_button, install


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            td,
        )

        settings = QSettings("AstroStack", "AstroStack")
        settings.setValue("ui_mode", "simple")
        settings.remove("recent_project")
        settings.sync()

        app = QApplication.instance() or QApplication([])

        win = MainWindow()
        install(win)
        win.show()
        app.processEvents()

        assert hasattr(win, "home_panel")
        assert hasattr(win, "home_version_label")
        assert win.home_version_label.text() == "v1.3.3-preview"
        assert win.btn_home_stack.text() == "Nuovo stack"
        assert win.btn_home_editor.text() == "Apri nell'Editor…"
        assert win.btn_home_project.text() == "Apri progetto…"
        assert not win.btn_home_recent.isEnabled()
        assert win.home_recent_name.text() == "Nessun progetto recente"

        project = os.path.join(td, "M31.astrostack")
        with open(project, "w", encoding="utf-8") as handle:
            handle.write("{}")

        settings.setValue("recent_project", project)
        settings.sync()

        _refresh_recent_button(win)

        assert win.btn_home_recent.isEnabled()
        assert win.home_recent_name.text() == "M31.astrostack"
        assert win.home_recent_path.text() == project

        win._set_workspace("stack")
        app.processEvents()
        assert win.home_panel.isHidden()

        win.close()
        app.processEvents()

    print("ASTROSTACK_133_HOME_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
