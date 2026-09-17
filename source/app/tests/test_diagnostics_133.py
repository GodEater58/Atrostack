"""Test del supporto Informazioni/Diagnostica AstroStack 1.3.3."""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from astrostack import __version__
from astrostack.diagnostics import (
    latest_crash_report,
    logs_dir,
    system_info_text,
)


def main() -> int:
    assert __version__ == "1.3.3-preview"

    with tempfile.TemporaryDirectory() as td:
        os.environ["ASTROSTACK_DATA_DIR"] = td

        assert latest_crash_report() is None

        first = logs_dir() / "crash_20260101_000000_000000.txt"
        first.write_text("first", encoding="utf-8")
        time.sleep(0.02)
        second = logs_dir() / "crash_20260101_000001_000000.txt"
        second.write_text("second", encoding="utf-8")

        assert latest_crash_report() == second

        info = system_info_text()
        assert "AstroStack diagnostics" in info
        assert "Version: 1.3.3-preview" in info
        assert "OS:" in info
        assert "Python:" in info
        assert "Log directory:" in info

    print("ASTROSTACK_133_DIAGNOSTICS_SUPPORT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
