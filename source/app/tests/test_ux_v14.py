"""Smoke test della shell AstroStack 1.4."""
from __future__ import annotations
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from astrostack import __version__
from astrostack.gui.main_window import MainWindow
from astrostack.gui.ux_v13 import install as install_v13
from astrostack.gui.ux_v14 import _show_projects, install as install_v14

def main():
    assert __version__ == "1.4.0-preview"
    with tempfile.TemporaryDirectory() as td:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, td)
        s = QSettings("AstroStack", "AstroStack")
        s.setValue("guide_seen", "1")
        s.setValue("ui_mode", "simple")
        s.sync()
        app = QApplication.instance() or QApplication([])
        win = MainWindow()
        install_v13(win)
        install_v14(win)
        win.show()
        app.processEvents()
        assert hasattr(win, "v14_shell")
        assert win.v14_nav_home.isChecked()
        assert "Stack, sviluppa" in win.v14_home_title.text()
        assert win.v14_page_title.text() == "Home"
        win._set_workspace("stack")
        app.processEvents()
        assert win.v14_nav_stack.isChecked()
        assert win.v14_page_title.text() == "Stack"
        assert win.main_splitter.isVisible()
        _show_projects(win)
        app.processEvents()
        assert win.v14_nav_projects.isChecked()
        assert win.v14_projects_panel.isVisible()
        assert not win.main_splitter.isVisible()
        win.close()
        app.processEvents()
    print("ASTROSTACK_140_UI_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
