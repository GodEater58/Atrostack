"""Diagnostica locale e crash reporting per AstroStack.

Nessun dato viene inviato in rete: i report restano sul PC dell'utente.
"""
from __future__ import annotations

import datetime as _dt
import os
import platform
import sys
import threading
import traceback
from pathlib import Path

_HANDLING = False
_APP = None


def data_root() -> Path:
    """Cartella dati utente usata da AstroStack."""
    override = os.environ.get("ASTROSTACK_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "AstroStack"

    # Fallback utile anche su macOS/Linux durante lo sviluppo.
    return Path.home() / ".astrostack"


def logs_dir() -> Path:
    path = data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_version() -> str:
    try:
        from astrostack import __version__
        return str(__version__)
    except Exception:
        return "unknown"


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _prune_reports(max_reports: int = 20) -> None:
    try:
        files = sorted(
            logs_dir().glob("crash_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[max_reports:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def record_startup() -> Path | None:
    """Registra informazioni minime sull'ultimo avvio.

    Serve per capire, in caso di problemi di startup, quale runtime e
    versione stavano venendo usati. Il file viene sovrascritto a ogni avvio.
    """
    try:
        path = logs_dir() / "last_startup.txt"
        now = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
        text = "\n".join(
            [
                f"time={now}",
                f"version={_safe_version()}",
                f"python={sys.version.replace(chr(10), ' ')}",
                f"executable={sys.executable}",
                f"platform={platform.platform()}",
                f"cwd={os.getcwd()}",
                f"argv={sys.argv!r}",
                "",
            ]
        )
        path.write_text(text, encoding="utf-8")
        return path
    except Exception:
        return None


def write_crash_report(exc_type, exc_value, exc_tb) -> Path | None:
    """Scrive un report testuale dell'eccezione non gestita."""
    try:
        _prune_reports()
        path = logs_dir() / f"crash_{_stamp()}.txt"
        now = _dt.datetime.now().astimezone().isoformat(timespec="seconds")

        header = [
            "AstroStack crash report",
            "=" * 72,
            f"Time: {now}",
            f"Version: {_safe_version()}",
            f"Python: {sys.version.replace(chr(10), ' ')}",
            f"Executable: {sys.executable}",
            f"Platform: {platform.platform()}",
            f"Working directory: {os.getcwd()}",
            f"Arguments: {sys.argv!r}",
            "",
            "Unhandled exception",
            "-" * 72,
        ]

        body = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )

        path.write_text(
            "\n".join(header) + "\n" + body,
            encoding="utf-8",
        )
        return path
    except Exception:
        return None



def latest_crash_report() -> Path | None:
    """Restituisce il crash report più recente, se presente."""
    try:
        reports = sorted(
            logs_dir().glob("crash_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return reports[0] if reports else None
    except OSError:
        return None


def system_info_text() -> str:
    """Informazioni tecniche pronte da copiare in una segnalazione."""
    now = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "AstroStack diagnostics",
        f"Version: {_safe_version()}",
        f"Time: {now}",
        f"OS: {platform.platform()}",
        f"Machine: {platform.machine()}",
        f"Python: {sys.version.replace(chr(10), ' ')}",
        f"Executable: {sys.executable}",
        f"Data directory: {data_root()}",
        f"Log directory: {logs_dir()}",
    ]

    try:
        from PySide6 import __version__ as qt_version
        lines.append(f"PySide6: {qt_version}")
    except Exception:
        lines.append("PySide6: unavailable")

    return "\n".join(lines) + "\n"

def _show_crash_dialog(path: Path | None, exc_value) -> None:
    # Non importare PySide6 a livello modulo: il logger deve funzionare anche
    # se proprio Qt è la causa del mancato avvio.
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return

        detail = str(exc_value).strip() or exc_value.__class__.__name__
        location = str(path) if path is not None else "report non disponibile"

        QMessageBox.critical(
            None,
            "AstroStack — errore inatteso",
            "AstroStack ha incontrato un errore inatteso.\n\n"
            f"{detail}\n\n"
            "È stato salvato un report locale qui:\n"
            f"{location}\n\n"
            "Il report non viene inviato automaticamente a nessuno.",
        )
    except Exception:
        pass


def handle_unhandled_exception(exc_type, exc_value, exc_tb) -> Path | None:
    """Gestisce una singola eccezione non catturata senza creare loop."""
    global _HANDLING
    if _HANDLING:
        return None

    _HANDLING = True
    try:
        path = write_crash_report(exc_type, exc_value, exc_tb)
        _show_crash_dialog(path, exc_value)
        return path
    finally:
        _HANDLING = False


def install_exception_handler(app=None) -> None:
    """Installa i gestori globali per thread principale e thread Python."""
    global _APP
    if app is not None:
        _APP = app

    # Evita di re-wrappare lo stesso hook quando main() richiama la funzione
    # dopo la creazione della QApplication.
    if getattr(sys.excepthook, "_astrostack_handler", False):
        return

    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        handle_unhandled_exception(exc_type, exc_value, exc_tb)
        # Mantiene il comportamento standard in console/sviluppo.
        if previous not in (None, sys.__excepthook__):
            try:
                previous(exc_type, exc_value, exc_tb)
            except Exception:
                pass

    hook._astrostack_handler = True
    sys.excepthook = hook

    if hasattr(threading, "excepthook"):
        previous_thread = threading.excepthook

        def thread_hook(args):
            handle_unhandled_exception(
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
            )
            if previous_thread is not None:
                try:
                    previous_thread(args)
                except Exception:
                    pass

        threading.excepthook = thread_hook
