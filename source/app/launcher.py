"""Avvio di AstroStack senza finestra nera (usato da AstroStack.exe).

Controlla che le librerie siano installate (la prima volta le installa mostrando
una finestra di avanzamento), poi apre il programma. Gli errori vengono mostrati
in una finestra di messaggio, visto che non c'è la console.
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

MB_OK, MB_OKCANCEL, MB_ICONERROR, MB_ICONINFORMATION = 0x0, 0x1, 0x10, 0x40
IDCANCEL = 2


def msgbox(text: str, flags: int = MB_OK | MB_ICONERROR, title: str = "AstroStack") -> int:
    if sys.platform.startswith("win"):
        import ctypes
        return int(ctypes.windll.user32.MessageBoxW(None, text, title, flags))
    print(text)
    return 1


def missing_dependency() -> str:
    try:
        import PySide6  # noqa: F401
        import rawpy  # noqa: F401
        import cv2  # noqa: F401
        import scipy  # noqa: F401
        import astropy  # noqa: F401
        import tifffile  # noqa: F401
        import exifread  # noqa: F401
        import requests  # noqa: F401
        return ""
    except ImportError as e:
        return str(e)


def install_dependencies() -> bool:
    python = sys.executable
    if python.lower().endswith("pythonw.exe"):
        python = python[:-len("pythonw.exe")] + "python.exe"
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)   # finestra visibile con l'avanzamento
    req = os.path.join(HERE, "requirements.txt")
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip"], creationflags=flags)
    r = subprocess.run([python, "-m", "pip", "install", "-r", req], creationflags=flags)
    return r.returncode == 0


def main() -> int:
    if missing_dependency():
        r = msgbox("Prima esecuzione: AstroStack deve scaricare le librerie necessarie "
                   "(qualche minuto, circa 300 MB).\n\nPremi OK per iniziare.",
                   MB_OKCANCEL | MB_ICONINFORMATION)
        if r == IDCANCEL:
            return 0
        if not install_dependencies() or missing_dependency():
            msgbox("Installazione non riuscita: controlla la connessione a internet.\n\n"
                   "Per vedere l'errore completo avvia AvviaAstroStack.bat.")
            return 1
    try:
        from main import main as run_app
        return int(run_app() or 0)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception:
        msgbox("AstroStack si è chiuso per un errore:\n\n" + traceback.format_exc()[-1800:])
        return 1


if __name__ == "__main__":
    sys.exit(main())
