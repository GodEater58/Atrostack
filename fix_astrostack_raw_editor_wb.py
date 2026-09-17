from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "source" / "app" / "astrostack" / "gui" / "main_window.py"

REPLACEMENT = '    def open_image_path(self, path: str):\n        """Apre direttamente un\'immagine nell\'Editor (anche da drag&drop)."""\n        if not path or not os.path.isfile(path):\n            return\n        try:\n            from ..core.loader import load_frame\n\n            fr = load_frame(path)\n            data = fr.data.astype(np.float32, copy=True)\n\n            if fr.is_bayer:\n                from ..core import calibration as cal\n\n                # Per l\'apertura diretta dei RAW nell\'Editor applichiamo\n                # prima del debayer il bilanciamento del bianco registrato\n                # dalla fotocamera. In fallback usiamo quello daylight.\n                wb = (\n                    fr.meta.get("wb_camera")\n                    or fr.meta.get("wb_daylight")\n                )\n\n                if wb is not None:\n                    data = cal.apply_white_balance(\n                        data,\n                        True,\n                        fr.pattern,\n                        wb,\n                    )\n\n                data = cal.to_rgb(\n                    data,\n                    True,\n                    fr.pattern,\n                )\n\n            if data.ndim == 2:\n                data = np.repeat(\n                    data[:, :, None],\n                    3,\n                    axis=2,\n                )\n\n            data = np.ascontiguousarray(\n                data[:, :, :3],\n                dtype=np.float32,\n            )\n\n        except Exception as e:  # noqa: BLE001\n            QMessageBox.critical(\n                self,\n                tr("Apertura non riuscita"),\n                str(e),\n            )\n            return\n\n        self.result = None\n        self._set_workspace("editor")\n        self.opened_path = path\n        self._remember_dir(path)\n        self.stars_image = None\n        self.annotations = []\n        self._undo = []\n        self.layers = []\n        self.layer_proxies = []\n\n        if hasattr(self, "editor_sidebar"):\n            self.editor_sidebar.set_snapshots([])\n            self.editor_sidebar.clear_history()\n\n        self.view.clear_annotations()\n        self.tools.set_undo(False)\n\n        # FITS/RAW = dati lineari (da stirare); TIFF/PNG/JPG = già sviluppati.\n        self.nonlinear = os.path.splitext(path)[1].lower() not in (\n            ".fits",\n            ".fit",\n            ".fts",\n            ".cr2",\n            ".cr3",\n            ".nef",\n            ".arw",\n            ".dng",\n            ".raf",\n            ".orf",\n            ".rw2",\n        )\n\n        self.btn_stretch.setChecked(True)\n        self._set_current_image(data)\n        self.editor_sidebar.set_source(\n            path,\n            data.shape,\n            is_linear=not self.nonlinear,\n        )\n        self._set_running(False)\n        self.dock_develop.show()\n        self.preview_label.setText(\n            os.path.basename(path)\n            + ("  ·  lineare" if not self.nonlinear else "")\n        )\n        self.status.setText(f"Aperta: {path}")\n        self.status.setStyleSheet(f"color: {TH.OK};")\n\n'

START = "    def open_image_path(self, path: str):\n"
END = "    # ------------------------------------------------------------ esportazione\n"


def main() -> int:
    if not TARGET.is_file():
        print("ERRORE: file non trovato:", TARGET)
        return 2

    text = TARGET.read_text(encoding="utf-8-sig")

    a = text.find(START)
    if a < 0:
        print("ERRORE: open_image_path non trovato")
        return 3

    b = text.find(END, a)
    if b < 0:
        print("ERRORE: marcatore esportazione non trovato")
        return 4

    backup = TARGET.with_suffix(".py.before_raw_wb_fix.bak")
    backup.write_text(text, encoding="utf-8")

    updated = text[:a] + REPLACEMENT + text[b:]
    TARGET.write_text(updated, encoding="utf-8")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "py_compile", str(TARGET)],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        print("ERRORE: il file corretto non compila.")
        print("Ripristino automatico del backup.")
        TARGET.write_text(text, encoding="utf-8")
        return 5

    print("ASTROSTACK_RAW_EDITOR_WB_FIX_OK")
    print("Backup:", backup)
    print("File corretto:", TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
