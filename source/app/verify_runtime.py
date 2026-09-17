"""Check the shipped private runtime without relying on the host Python."""
import pathlib
import sys
import numpy, scipy, cv2, rawpy, tifffile, astropy, exifread, PySide6, requests
from astrostack import __version__

root = pathlib.Path(__file__).resolve().parent.parent
assert pathlib.Path(sys.executable).resolve().parent == root / "runtime"
assert sys.flags.isolated and sys.flags.ignore_environment
for module in (numpy, scipy, cv2, rawpy, tifffile, astropy, exifread, PySide6, requests):
    assert pathlib.Path(module.__file__).resolve().is_relative_to(root / "runtime"), module.__name__
assert __version__ == "1.4.0-preview"
print("ASTROSTACK_PRIVATE_RUNTIME_OK")
