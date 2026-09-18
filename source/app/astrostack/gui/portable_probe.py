"""Explicit --self-test-report probe for a packaged GUI on an isolated Windows runner."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time
import traceback


def attach(window, report_path):
    import cv2
    import numpy as np
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    state = {'stage': 0, 'started': time.monotonic()}
    timer = QTimer(window)
    timer.setInterval(150)

    def finish(error=None):
        timer.stop()
        from astrostack import __version__
        console = None
        if sys.platform == 'win32':
            import ctypes
            console = int(ctypes.windll.kernel32.GetConsoleWindow())
        result = {'ok': error is None, 'version': __version__, 'platform': app.platformName(),
                  'python': sys.executable, 'pid': os.getpid(), 'console_window': console,
                  'isolated_runtime': bool(sys.flags.isolated), 'error': error}
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        # Let workers finish before destroying the window, including failure paths.
        for attr in ('worker', 'dev_worker', 'render_worker', 'comp_worker', 'export_worker'):
            worker = getattr(window, attr, None)
            if worker is not None and worker.isRunning():
                worker.wait(10000)
        window.close()
        app.exit(0 if error is None else 1)

    def tick():
        try:
            assert time.monotonic() - state['started'] < 45, 'GUI probe timed out'
            busy = any(getattr(window, key, None) and getattr(window, key).isRunning()
                       for key in ('dev_worker', 'render_worker', 'comp_worker'))
            if busy or window._dev_timer.isActive():
                return
            stage = state['stage']
            if stage == 0:
                assert app.platformName() == 'windows', 'Native Windows Qt plugin required'
                assert window.v14_nav_home.isChecked()
                window.resize(1366, 768)
                state['stage'] = 1
            elif stage == 1:
                window.grab().save(str(report.parent / 'windows-home.png'))
                y, x = np.mgrid[:480, :800]
                r = ((x-400)/250)**2 + ((y-240)/90)**2
                galaxy = np.exp(-r*2)[..., None] * np.array([.7, .4, .3])
                image = np.clip(.015 + galaxy, 0, 1)
                fixture = report.parent / 'galassia-test.png'
                cv2.imwrite(str(fixture), (image[:, :, ::-1]*255).astype('uint8'))
                window.open_image_path(str(fixture))
                state['stage'] = 2
            elif stage == 2:
                assert window.current_image is not None and window.after_rgb8 is not None
                assert window.workspace == 'editor' and window.render_workspace.inspector.isVisible()
                window._add_editor_snapshot()
                window.develop_panel.sliders['exposure'].spin.setValue(.25)
                window.btn_compare.setChecked(True)
                state['stage'] = 3
            elif stage == 3:
                assert window.before_rgb8 is not None and window.after_rgb8 is not None
                window.render_workspace.position_overlay()
                assert window.render_workspace.handle.isVisible()
                window.toast.hide()
                window.grab().save(str(report.parent / 'windows-editor.png'))
                window._set_workspace('stack')
                state['stage'] = 4
            elif stage == 4:
                assert window.render_workspace.steps.isVisible()
                window.grab().save(str(report.parent / 'windows-stack.png'))
                import ctypes
                assert ctypes.windll.kernel32.GetConsoleWindow() == 0, 'Unexpected console window'
                finish()
        except Exception:
            finish(traceback.format_exc())

    window._portable_probe = timer
    timer.timeout.connect(tick)
    timer.start()
