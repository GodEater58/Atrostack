"""Smoke test diagnostica AstroStack.

Eseguire:
    python tests/test_diagnostics.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from astrostack.diagnostics import record_startup, write_crash_report


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["ASTROSTACK_DATA_DIR"] = td

        startup = record_startup()
        assert startup is not None
        assert startup.is_file()
        text = startup.read_text(encoding="utf-8")
        assert "version=" in text
        assert "python=" in text

        try:
            raise RuntimeError("diagnostics smoke test")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = write_crash_report(exc_type, exc_value, exc_tb)

        assert report is not None
        assert report.is_file()
        crash = report.read_text(encoding="utf-8")
        assert "RuntimeError: diagnostics smoke test" in crash
        assert "AstroStack crash report" in crash

        # Windows can expose the temporary directory through an alias/short path
        # while Path.resolve() returns its canonical form. Compare canonical paths
        # so the test validates the destination rather than the string spelling.
        log_dir = (Path(td) / "logs").resolve()
        assert startup.parent.resolve() == log_dir
        assert report.parent.resolve() == log_dir

    print("ASTROSTACK_DIAGNOSTICS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
