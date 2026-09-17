"""Smoke test della finestra Informazioni/Diagnostica."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from PySide6.QtWidgets import QApplication

from astrostack.gui.about_dialog import AboutDiagnosticsDialog


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["ASTROSTACK_DATA_DIR"] = td
        app = QApplication.instance() or QApplication([])
        dialog = AboutDiagnosticsDialog()
        assert "AstroStack" in dialog.windowTitle()
        assert dialog.btn_logs.isEnabled()
        assert not dialog.btn_crash.isEnabled()
        assert "Version: 1.3.3-preview" in dialog.info.toPlainText()
        dialog.close()
        app.processEvents()

    print("ASTROSTACK_133_ABOUT_DIALOG_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
