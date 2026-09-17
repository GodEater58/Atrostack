import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from PySide6.QtWidgets import QApplication

from astrostack.gui.main_window import MainWindow
from astrostack.gui.ux_v13 import install
from astrostack.core import project as project_io
from astrostack.core.pipeline import Settings


app = QApplication([])

win = MainWindow()

install(win)

# Home
assert hasattr(
    win,
    "home_panel",
)

# ModalitÃ  semplice/avanzata
assert hasattr(
    win,
    "btn_ui_mode",
)

# Editor standalone
assert hasattr(
    win,
    "editor_sidebar",
)

win._set_workspace(
    "editor"
)

assert (
    win.workspace
    == "editor"
)

win._set_workspace(
    "stack"
)

assert (
    win.workspace
    == "stack"
)

# Preset Galassia
win._apply_editor_preset(
    "galaxy"
)

params = (
    win.develop_panel.params()
)

assert abs(
    params.contrast - 18.0
) < 0.01

assert abs(
    params.star_reduce - 8.0
) < 0.01

# Progetto .astrostack
with tempfile.TemporaryDirectory() as td:

    project = os.path.join(
        td,
        "test.astrostack",
    )

    project_io.save_project(
        project,
        {
            "light": [],
            "dark": [],
            "flat": [],
            "bias": [],
        },
        Settings().__dict__,
        [],
        None,
        True,
        None,
        [],
        {
            "workspace": "stack",
            "ui_mode": "simple",
        },
    )

    win.open_project(
        path=project
    )

    assert (
        win.project_path
        == project
    )

print(
    "ASTROSTACK_GUI_SMOKE_TEST_OK"
)

win.close()

app.processEvents()

