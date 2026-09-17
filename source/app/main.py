"""AstroStack — avvio dell'applicazione.

    python main.py
"""
from __future__ import annotations

import os
import sys

# esegui anche da una cartella diversa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from PySide6.QtGui import QIcon

    from astrostack.gui.main_window import MainWindow
    from astrostack.gui.ux_v13 import install as install_ux_v13
    from astrostack.gui.theme import build_stylesheet, dark_palette, load_fonts

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("AstroStack")
    app.setOrganizationName("AstroStack")
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    family = load_fonts()
    app.setFont(QFont(family, 10))
    app.setStyleSheet(build_stylesheet())
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "astrostack", "assets", "astrostack.ico")
    if os.path.isfile(icon):
        app.setWindowIcon(QIcon(icon))
    win = MainWindow()
    install_ux_v13(win)

    startup_project = None
    if len(sys.argv) > 1:
        candidate = os.path.abspath(sys.argv[1])
        if candidate.lower().endswith('.astrostack') and os.path.isfile(candidate):
            startup_project = candidate

    win.setWindowOpacity(0.0)
    win.show()
    from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
    fade = QPropertyAnimation(win, b"windowOpacity", win)
    fade.setDuration(350)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.start()
    if startup_project:
        QTimer.singleShot(
            0,
            lambda p=startup_project: win.open_project(path=p),
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
