"""Tema scuro "cielo notturno" per l'interfaccia."""

# tema corrente: "scuro" (notturno) oppure "chiaro"
THEME = "scuro"

BG = "#141A2A"
PANEL = "#1B2336"
PANEL2 = "#222B42"
BORDER = "#2E3A57"
TEXT = "#E8ECF5"
MUTED = "#94A0BE"
ACCENT = "#F2B441"        # oro: il pulsante Stack e gli elementi attivi
ACCENT_TEXT = "#1A1405"
OK = "#5FD39B"
WARN = "#F07E6E"

ZONE_COLORS = {
    "light": "#74B4FF",
    "dark": "#7E8799",
    "flat": "#F0A35E",
    "bias": "#B592F5",
}

STYLESHEET_TEMPLATE = """
QMainWindow, QDialog, QWidget {{ background: {BG}; color: {TEXT}; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; font-size: 13px; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px; }}
QLabel {{ background: transparent; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="title"] {{ font-size: 20px; font-weight: 600; letter-spacing: 0.5px; }}
QLabel[role="section"] {{ color: {MUTED}; font-size: 11px; font-weight: 600; }}
QLabel[role="sectionTitle"] {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
QFrame[role="panel"] {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PANEL2}, stop:1 {PANEL}); border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame[role="preview"] {{ background: {PREVIEWBG}; border: 1px solid {BORDER}; border-radius: 10px; }}
QGroupBox {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {GROUPTOP}, stop:1 {PANEL}); border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding: 10px 8px 6px 8px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {ACCENT}; font-size: 12px; font-weight: 600; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 7px; padding: 6px 12px; color: {TEXT}; }}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {PANEL2}; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: {INPUT}; border: 1px solid {BORDER}; border-radius: 7px; padding: 4px 8px; color: {TEXT}; min-height: 24px; selection-background-color: {ACCENT}; selection-color: {ACCENT_TEXT}; }}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {{ border-color: {FIELDHOVER}; }}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; color: {TEXT}; selection-background-color: {BORDER}; border: 1px solid {BORDER}; padding: 4px; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 32px; border-left: 1px solid {BORDER}; border-top-right-radius: 7px; border-bottom-right-radius: 7px; background: {PANEL2}; }}
QComboBox::drop-down:hover {{ background: {BORDER}; }}
QComboBox::down-arrow {{ image: url("__DOWN__"); width: 14px; height: 9px; }}
QComboBox::down-arrow:disabled {{ image: url("__DOWN_DIM__"); }}
QSpinBox, QDoubleSpinBox {{ padding-right: 36px; min-height: 30px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 34px; border-left: 1px solid {BORDER}; border-bottom: 1px solid {BORDER}; border-top-right-radius: 7px; background: {PANEL2}; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 34px; border-left: 1px solid {BORDER}; border-bottom-right-radius: 7px; background: {PANEL2}; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {BORDER}; }}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed, QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{ background: {ACCENT}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("__UP__"); width: 14px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("__DOWN__"); width: 14px; height: 9px; }}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off {{ image: url("__UP_DIM__"); }}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off {{ image: url("__DOWN_DIM__"); }}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 1px solid {MUTED}; background: {INPUT}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {ACCENTHI}, stop:1 {ACCENT}); border-color: {ACCENT}; image: url("__CHECK__"); }}
QCheckBox::indicator:disabled {{ border-color: {PANEL2}; background: {PANEL}; }}
QSlider::groove:horizontal {{ height: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2E3A57, stop:1 #3A4868); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENTLO2}, stop:1 {ACCENT}); border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 20px; height: 20px; margin: -7px 0; border-radius: 10px; background: qradialgradient(cx:0.5, cy:0.4, radius:0.7, fx:0.5, fy:0.4, stop:0 {ACCENTGLOW}, stop:1 {ACCENT}); border: 1px solid {ACCENTLO}; }}
QSlider::handle:horizontal:hover {{ background: {ACCENTHI2}; }}
QSlider::handle:horizontal:disabled {{ background: {BORDER}; border-color: {BORDER}; }}
QProgressBar {{ background: {INPUT}; border: 1px solid {BORDER}; border-radius: 7px; height: 14px; text-align: center; color: {TEXT}; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENTLO}, stop:1 {ACCENTHI2}); border-radius: 6px; }}
QTableWidget {{ background: {PANEL}; alternate-background-color: {ROWALT}; gridline-color: {BORDER}; border: 1px solid {BORDER}; border-radius: 8px; }}
QHeaderView::section {{ background: {PANEL2}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px 8px; font-weight: 600; }}
QTableWidget::item {{ padding: 2px 6px; }}
QTableWidget::item:selected {{ background: {BORDER}; }}
QTableWidget::item:hover {{ background: {HOVER}; }}
QListWidget {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {SELBG}, stop:1 {PANEL2}); color: {ACCENT}; border: 1px solid {ACCENTDIM}; }}
QListWidget::item:hover {{ background: {HOVER}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: {PANEL}; color: {MUTED}; padding: 6px 14px; border: 1px solid {BORDER}; border-bottom: none; border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {PANEL2}; color: {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QDockWidget {{ color: {MUTED}; font-weight: 600; titlebar-close-icon: none; }}
QDockWidget::title {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PANEL2}, stop:1 {PANEL}); padding: 8px 12px; border-bottom: 1px solid {BORDER}; }}
QSplitter::handle {{ background: {BG}; }}
QPlainTextEdit {{ background: {LOGBG}; border: 1px solid {BORDER}; border-radius: 8px; color: {MUTED}; font-family: "IBM Plex Mono", Consolas, monospace; font-size: 12px; padding: 6px; }}
QStatusBar {{ color: {MUTED}; }}
QMessageBox {{ background: {PANEL}; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {BORDER}; }}
"""


def _arrow_png(path: str, up: bool, color: str, w: int = 28, h: int = 18):
    """Disegna una freccetta (triangolo) e la salva come PNG per le regole del foglio di stile."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    if up:
        poly = QPolygonF([QPointF(1, h - 1), QPointF(w - 1, h - 1), QPointF(w / 2, 1)])
    else:
        poly = QPolygonF([QPointF(1, 1), QPointF(w - 1, 1), QPointF(w / 2, h - 1)])
    p.drawPolygon(poly)
    p.end()
    img.save(path)


def _check_png(path: str, color: str, w: int = 20, h: int = 20):
    """Segno di spunta per le caselle."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline([QPointF(w * 0.25, h * 0.52), QPointF(w * 0.43, h * 0.70), QPointF(w * 0.76, h * 0.32)])
    p.end()
    img.save(path)


def load_fonts() -> str:
    """Carica i caratteri IBM Plex inclusi nel programma; restituisce la famiglia da usare."""
    import glob
    import os
    from PySide6.QtGui import QFontDatabase
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
    ok = False
    for f in glob.glob(os.path.join(here, "*.ttf")):
        if QFontDatabase.addApplicationFont(f) >= 0:
            ok = True
    return "IBM Plex Sans" if ok else "Segoe UI"


LIGHT = {"BG": "#F2F4F9", "PANEL": "#FFFFFF", "PANEL2": "#E9EDF6", "BORDER": "#C8D0E2", "TEXT": "#1B2336",
         "MUTED": "#5C6684", "ACCENT": "#C8891A", "ACCENT_TEXT": "#FFFFFF", "OK": "#2E9E6B", "WARN": "#C6493A"}
DARK = {"BG": "#141A2A", "PANEL": "#1B2336", "PANEL2": "#222B42", "BORDER": "#2E3A57", "TEXT": "#E8ECF5",
        "MUTED": "#94A0BE", "ACCENT": "#F2B441", "ACCENT_TEXT": "#1A1405", "OK": "#5FD39B", "WARN": "#F07E6E"}


def set_theme(name: str):
    """Cambia la tavolozza (scuro/chiaro). Poi va riapplicato build_stylesheet()."""
    global THEME, BG, PANEL, PANEL2, BORDER, TEXT, MUTED, ACCENT, ACCENT_TEXT, OK, WARN
    THEME = "chiaro" if str(name).lower().startswith("chi") or str(name).lower().startswith("lig") else "scuro"
    pal = LIGHT if THEME == "chiaro" else DARK
    BG, PANEL, PANEL2 = pal["BG"], pal["PANEL"], pal["PANEL2"]
    BORDER, TEXT, MUTED = pal["BORDER"], pal["TEXT"], pal["MUTED"]
    ACCENT, ACCENT_TEXT, OK, WARN = pal["ACCENT"], pal["ACCENT_TEXT"], pal["OK"], pal["WARN"]
    globals()["ZONE_COLORS"] = ({"light": "#2F73D0", "dark": "#5C6684", "flat": "#C87A1E", "bias": "#7B52C8"}
                                if THEME == "chiaro" else
                                {"light": "#74B4FF", "dark": "#7E8799", "flat": "#F0A35E", "bias": "#B592F5"})


def _shade(color: str, amount: float) -> str:
    """Schiarisce (amount > 0) o scurisce (amount < 0) un colore esadecimale."""
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    if amount >= 0:
        r, g, b = (int(v + (255 - v) * amount) for v in (r, g, b))
    else:
        r, g, b = (int(v * (1 + amount)) for v in (r, g, b))
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _css() -> str:
    """Foglio di stile costruito con i colori del tema corrente."""
    light = THEME == "chiaro"
    d = dict(BG=BG, PANEL=PANEL, PANEL2=PANEL2, BORDER=BORDER, TEXT=TEXT, MUTED=MUTED,
             ACCENT=ACCENT, ACCENT_TEXT=ACCENT_TEXT, OK=OK, WARN=WARN,
             INPUT=_shade(PANEL, 0.04 if light else -0.10),
             GROUPTOP=_shade(PANEL, 0.03 if light else 0.04),
             ROWALT=_shade(PANEL, -0.04 if light else 0.05),
             HOVER=_shade(PANEL2, -0.06 if light else 0.10),
             PREVIEWBG=_shade(BG, -0.35 if light else -0.25),
             LOGBG=_shade(PANEL, -0.02 if light else -0.25),
             DISABLED=_shade(MUTED, 0.35 if light else -0.25),
             FIELDHOVER=_shade(BORDER, -0.20 if light else 0.25),
             SELBG=_shade(ACCENT, 0.75 if light else -0.75),
             ACCENTDIM=_shade(ACCENT, 0.55 if light else -0.55),
             ACCENTHI=_shade(ACCENT, 0.20), ACCENTHI2=_shade(ACCENT, 0.35),
             ACCENTLO=_shade(ACCENT, -0.18), ACCENTLO2=_shade(ACCENT, -0.40),
             ACCENTGLOW=_shade(ACCENT, 0.60))
    return STYLESHEET_TEMPLATE.format(**d)


def build_stylesheet() -> str:
    """Foglio di stile completo: genera le icone delle frecce (su/giù) e le collega alle regole.

    Da chiamare dopo la creazione di QApplication.
    """
    import os
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "astrostack_icons")
    os.makedirs(d, exist_ok=True)
    dim = _shade(MUTED, 0.35 if THEME == "chiaro" else -0.25)
    files = {"__UP__": (f"up_{THEME}.png", True, TEXT), "__DOWN__": (f"down_{THEME}.png", False, TEXT),
             "__UP_DIM__": (f"up_dim_{THEME}.png", True, dim), "__DOWN_DIM__": (f"down_dim_{THEME}.png", False, dim)}
    css = _css()
    for key, (name, up, color) in files.items():
        path = os.path.join(d, name)
        try:
            _arrow_png(path, up, color)
        except Exception:
            pass
        css = css.replace(key, path.replace("\\", "/"))
    chk = os.path.join(d, f"check_{THEME}.png")
    try:
        _check_png(chk, ACCENT_TEXT)
    except Exception:
        pass
    css = css.replace("__CHECK__", chk.replace("\\", "/"))
    return css


def dark_palette():
    """Tavolozza scura coerente con il tema (anche per finestre di dialogo e frecce di sistema)."""
    from PySide6.QtGui import QColor, QPalette
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG, QPalette.ColorRole.WindowText: TEXT, QPalette.ColorRole.Base: PANEL2,
        QPalette.ColorRole.AlternateBase: PANEL, QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: PANEL2,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: ACCENT_TEXT, QPalette.ColorRole.ToolTipBase: PANEL2,
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.BrightText: WARN, QPalette.ColorRole.Link: ACCENT,
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#5C6684"))
    return pal
