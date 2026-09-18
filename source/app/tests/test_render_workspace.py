"""Exercise real UI routes, editing, snapshots and project reopen with isolated settings."""
from __future__ import annotations
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import cv2
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from astrostack.gui.main_window import MainWindow
from astrostack.gui.ux_v13 import install as install_v13
from astrostack.gui.ux_v14 import install as install_v14, _show_home, _show_projects
from astrostack.gui import theme
from astrostack.gui.export_dialog import ExportDialog
from astrostack.core.develop import ExportOptions


def main():
    with tempfile.TemporaryDirectory() as td:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, td)
        QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, td)
        settings = QSettings('AstroStack', 'AstroStack')
        settings.setValue('guide_seen', '1')
        settings.setValue('ui_mode', 'advanced')
        app = QApplication.instance() or QApplication([])
        app.setStyle('Fusion')
        app.setStyleSheet(theme.build_stylesheet())
        w = MainWindow()
        install_v13(w)
        install_v14(w)
        ui = w.render_workspace
        w._autosave_v13.stop()
        w._recovery_path = os.path.join(td, 'recovery.astrostack')
        def pump(duration=.08):
            end = time.monotonic() + duration
            while time.monotonic() < end:
                app.processEvents()
                time.sleep(.005)
        def idle():
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                pump()
                if not any(getattr(w, key, None) and getattr(w, key).isRunning()
                           for key in ('dev_worker', 'render_worker', 'comp_worker', 'export_worker')) and not w._dev_timer.isActive():
                    pump()
                    return
            raise AssertionError('Preview worker did not finish')
        w.resize(1366, 768)
        w.show()
        pump()
        # Force deferred deletes from the replaced Home before saving a project.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        w._set_workspace('editor')
        pump()
        assert ui.empty.isVisible()
        assert ui.side_scroll.isVisible() and ui.inspector.isVisible()
        assert not w.context_bar.isVisible()
        assert not w.btn_save.isEnabled()
        assert w.btn_ui_mode.isEnabled()
        y, x = np.mgrid[:100, :160]
        image = np.clip(.04 + .65 * np.exp(-((x-80)**2+(y-50)**2)/500), 0, 1)
        image = np.repeat(image[..., None], 3, axis=2)
        path = os.path.join(td, 'fixture.png')
        cv2.imwrite(path, (image * 255).astype('uint8'))
        w.open_image_path(path)
        idle()
        assert w.result is None and w.workspace == 'editor'
        assert not ui.empty.isVisible() and w.btn_save.isEnabled()
        original = w.after_rgb8.copy()
        original_exposure = w.dev_params.exposure
        original_contrast = w.dev_params.contrast
        w.develop_panel.sliders['exposure'].spin.setValue(.55)
        idle()
        assert not np.array_equal(original, w.after_rgb8)
        w.undo_develop()
        idle()
        assert abs(w.dev_params.exposure - original_exposure) < 1e-6
        w.redo_develop()
        idle()
        assert abs(w.dev_params.exposure - .55) < 1e-6
        w._add_editor_snapshot()
        w.develop_panel.sliders['contrast'].spin.setValue(20)
        idle()
        w._add_editor_snapshot()
        saved = w.editor_sidebar.snapshots()
        assert len(saved) == 2 and all(row.get('thumbnail') for row in saved)
        w.editor_sidebar.set_snapshots(saved)
        assert w.editor_sidebar.snapshots() == saved
        w.editor_sidebar._snapshot(w.editor_sidebar.snapshot_list.item(1))
        idle()
        assert w.dev_params.contrast == original_contrast
        for index, (key, _) in enumerate(ui.categories):
            ui.nav.setCurrentRow(index)
            pump()
            if key == 'layers':
                assert ui.inspector.currentWidget() is w.dock_layers
            else:
                assert w.develop_panel.active_section == key
                assert ui.inspector.currentWidget() is w.dock_develop
        w.btn_ui_mode.click()
        pump()
        assert ui.nav.item(6).isHidden()
        w.btn_ui_mode.click()
        pump()
        assert not ui.nav.item(6).isHidden()
        ui.nav.setCurrentRow(0)
        w.btn_compare.setChecked(True)
        idle()
        assert ui.handle.isVisible()
        old = w.compare_slider.value()
        QTest.mousePress(ui.handle, Qt.MouseButton.LeftButton, pos=QPoint(16, 16))
        QTest.mouseMove(ui.handle, QPoint(70, 16), delay=20)
        QTest.mouseRelease(ui.handle, Qt.MouseButton.LeftButton, pos=QPoint(16, 16))
        assert w.compare_slider.value() != old
        ui.focus_button.click()
        pump()
        assert not ui.side_scroll.isVisible() and not ui.inspector.isVisible()
        ui.focus_button.click()
        pump()
        assert ui.inspector.isVisible()
        for width, height in ((1120, 680), (1366, 768), (1920, 1080), (2560, 1440)):
            w.resize(width, height)
            pump()
            assert w.width() == width and w.height() == height
            assert ui.inspector.width() >= 330
            assert w.view.viewport().width() >= 300
            for button in (ui.open_button, ui.undo_button, ui.redo_button, w.btn_save):
                assert button.width() > 40 and button.isVisible()
                assert ui.toolbar.rect().contains(button.geometry())
        # Export through the actual toolbar callback, replacing only file dialogs.
        output = os.path.join(td, 'export.tif')
        with patch.object(ExportDialog, 'exec', return_value=ExportDialog.DialogCode.Accepted), \
             patch.object(ExportDialog, 'options', return_value=ExportOptions(fmt='tif16')), \
             patch.object(QFileDialog, 'getSaveFileName', return_value=(output, '')):
            w.btn_save.click()
        idle()
        import tifffile
        exported = tifffile.imread(output)
        assert exported.dtype == np.uint16 and exported.shape == image.shape
        w.v14_btn_lang.click()
        pump()
        assert ui.nav.item(0).text() == 'Basic adjustments'
        w.v14_btn_lang.click()
        pump()
        assert ui.nav.item(0).text() == 'Regolazioni di base'
        project = os.path.join(td, 'test.astrostack')
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(project, '')):
            w.save_project()
        assert os.path.exists(project)
        assert w.v14_recent_name.text() == 'test.astrostack'
        _show_home(w)
        pump()
        assert not ui.inspector.isVisible() and w.home_panel.isVisible()
        _show_projects(w)
        pump()
        assert w.v14_projects_panel.isVisible()
        w.open_project(path=project)
        idle()
        assert w.workspace == 'editor' and ui.inspector.isVisible()
        assert w.editor_sidebar.snapshots() == saved
        w._set_workspace('stack')
        pump()
        assert w.stack_sidebar_scroll.isVisible()
        assert ui.steps.isVisible() and not ui.inspector.isVisible()
        assert not ui.handle.isVisible()
        w.v14_btn_theme.click()
        pump()
        w.v14_btn_theme.click()
        w._set_workspace('editor')
        idle()
        assert ui.inspector.isVisible()
        w.close()
        pump()
    print('ASTROSTACK_RENDER_WORKSPACE_OK: routes, responsive layout, edit/undo/redo, compare drag, snapshots, project round-trip, TIFF export, theme, language')


if __name__ == '__main__':
    main()
