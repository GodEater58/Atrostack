"""Widget animati: pulsanti con transizioni fluide, barra di avanzamento morbida, notifiche "toast"."""
from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QWidget)

from . import theme as TH


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


class AnimatedButton(QPushButton):
    """Pulsante disegnato a mano con transizioni animate (hover, pressione, bagliore quando è occupato).

    variant: "primary" (oro, azione principale), "default", "link" (testo discreto), "toggle".
    """

    def __init__(self, text: str = "", variant: str = "default", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.variant = variant
        self._hover = 0.0
        self._press = 0.0
        self._glow = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._a_hover = QPropertyAnimation(self, b"hover", self)
        self._a_hover.setDuration(180)
        self._a_hover.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a_press = QPropertyAnimation(self, b"press", self)
        self._a_press.setDuration(110)
        self._a_press.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._a_glow = QVariantAnimation(self)
        self._a_glow.setDuration(1500)
        self._a_glow.setLoopCount(-1)
        self._a_glow.setStartValue(0.0)
        self._a_glow.setKeyValueAt(0.5, 1.0)
        self._a_glow.setEndValue(0.0)
        self._a_glow.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._a_glow.valueChanged.connect(self._set_glow)
        f = QFont(self.font())
        if variant == "primary":
            f.setPointSizeF(f.pointSizeF() + 2.5)
            f.setBold(True)
            self.setMinimumHeight(46)
            self.setMinimumWidth(150)
        elif variant == "link":
            self.setMinimumHeight(26)
        else:
            self.setMinimumHeight(34)
        self.setFont(f)

    # --------------------------------------------------------- proprietà animate
    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, v: float):
        self._hover = float(v)
        self.update()

    def _get_press(self) -> float:
        return self._press

    def _set_press(self, v: float):
        self._press = float(v)
        self.update()

    def _set_glow(self, v):
        self._glow = float(v)
        self.update()

    hover = Property(float, _get_hover, _set_hover)
    press = Property(float, _get_press, _set_press)

    def _animate(self, anim: QPropertyAnimation, current: float, target: float):
        anim.stop()
        anim.setStartValue(current)
        anim.setEndValue(target)
        anim.start()

    def set_busy(self, on: bool):
        if on:
            self._a_glow.start()
        else:
            self._a_glow.stop()
            self._glow = 0.0
            self.update()

    # --------------------------------------------------------- eventi
    def enterEvent(self, e):
        if self.isEnabled():
            self._animate(self._a_hover, self._hover, 1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate(self._a_hover, self._hover, 0.0)
        self._animate(self._a_press, self._press, 0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self.isEnabled():
            self._animate(self._a_press, self._press, 1.0)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._animate(self._a_press, self._press, 0.0)
        super().mouseReleaseEvent(e)

    def sizeHint(self):
        s = super().sizeHint()
        pad = 34 if self.variant == "primary" else 24 if self.variant != "link" else 12
        return s.expandedTo(QSize(self.fontMetrics().horizontalAdvance(self.text()) + pad, self.minimumHeight()))

    # --------------------------------------------------------- disegno
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        enabled = self.isEnabled()
        checked = self.isCheckable() and self.isChecked()
        radius = 11 if self.variant == "primary" else 8

        # bagliore pulsante (quando è occupato)
        if self._glow > 0:
            glow = QColor(TH.ACCENT)
            glow.setAlphaF(0.12 + 0.3 * self._glow)
            p.setPen(QPen(glow, 3 + 3 * self._glow))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, radius, radius)

        # colori
        if self.variant == "primary":
            base = QColor(TH.ACCENT) if enabled else QColor("#6A5A32")
            hov = QColor("#FAD07A")
            text = QColor(TH.ACCENT_TEXT) if enabled else QColor("#2A2416")
            border = None
        elif self.variant == "link":
            base = QColor(0, 0, 0, 0)
            hov = QColor(TH.PANEL2)
            text = mix(QColor(TH.MUTED), QColor(TH.TEXT), self._hover) if enabled else QColor("#5C6684")
            border = None
        else:
            base = QColor(TH.PANEL2) if enabled else QColor(TH.PANEL)
            hov = QColor("#2C3752")
            text = QColor(TH.TEXT) if enabled else QColor("#5C6684")
            border = QColor(TH.BORDER) if enabled else QColor(TH.PANEL2)
            if checked:
                base = mix(QColor(TH.PANEL2), QColor(TH.ACCENT), 0.18)
                hov = mix(QColor(TH.PANEL2), QColor(TH.ACCENT), 0.28)
                border = QColor(TH.ACCENT)
        bg = mix(base, hov, self._hover)
        if self._press > 0:
            bg = mix(bg, QColor(0, 0, 0), 0.14 * self._press)
        # "pressione": il pulsante si abbassa un filo
        shrink = 1.2 * self._press
        rr = r.adjusted(shrink, shrink, -shrink, -shrink)

        if self.variant == "primary" and enabled:
            g = QLinearGradient(rr.topLeft(), rr.bottomLeft())
            g.setColorAt(0.0, mix(bg, QColor(255, 255, 255), 0.14))
            g.setColorAt(1.0, mix(bg, QColor(0, 0, 0), 0.08))
            p.setBrush(g)
        elif self.variant == "default" and enabled:
            g = QLinearGradient(rr.topLeft(), rr.bottomLeft())
            g.setColorAt(0.0, mix(bg, QColor(255, 255, 255), 0.05))
            g.setColorAt(1.0, mix(bg, QColor(0, 0, 0), 0.10))
            p.setBrush(g)
        else:
            p.setBrush(bg)
        if border is not None:
            pen_col = mix(border, QColor(TH.MUTED), self._hover) if not checked else border
            p.setPen(QPen(pen_col, 1))
        else:
            p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rr, radius, radius)

        # sottolineatura discreta per i link al passaggio del mouse
        p.setPen(text)
        p.setFont(self.font())
        p.drawText(rr, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class SmoothProgressBar(QProgressBar):
    """Barra che scivola verso il nuovo valore invece di saltare."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_smooth(self, v: int):
        v = int(max(self.minimum(), min(self.maximum(), v)))
        if v < self.value():          # nuovo lavoro: riparte da zero senza animazione all'indietro
            self._anim.stop()
            self.setValue(v)
            return
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(v)
        self._anim.start()


class TrLabel(QLabel):
    """Etichetta che ricorda il testo italiano e lo mostra nella lingua scelta."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__("", parent)
        self._source = text
        self.setText(text)

    def setText(self, text):  # noqa: N802
        from .i18n import tr
        self._source = "" if text is None else str(text)
        super().setText(tr(self._source))

    def retranslate_i18n(self):
        from .i18n import tr
        super().setText(tr(self._source))


class LangSwitch(QWidget):
    """Interruttore IT | EN."""
    changed = Signal(str)

    def __init__(self, lang: str = "it", parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.buttons = {}
        for code, label in (("it", "IT"), ("en", "EN")):
            b = AnimatedButton(label)
            b.setCheckable(True)
            b.setFixedWidth(46)
            b.clicked.connect(lambda _=False, c=code: self.select(c))
            self.buttons[code] = b
            lay.addWidget(b)
        self.select(lang, emit=False)

    def select(self, code: str, emit: bool = True):
        code = "en" if str(code).lower().startswith("en") else "it"
        for c, b in self.buttons.items():
            b.setChecked(c == code)
        if emit:
            self.changed.emit(code)


class Toast(QLabel):
    """Notifica che scivola dal basso e sparisce da sola."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"QLabel {{ background: {TH.PANEL2}; color: {TH.TEXT}; border: 1px solid {TH.ACCENT}; "
                           f"border-radius: 10px; padding: 9px 18px; font-size: 13px; }}")
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._a_op = QPropertyAnimation(self._fx, b"opacity", self)
        self._a_op.setDuration(220)
        self._a_pos = QPropertyAnimation(self, b"pos", self)
        self._a_pos.setDuration(260)
        self._a_pos.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide_anim)
        self.hide()

    def show_message(self, text: str, ms: int = 2600, accent: str = ""):
        accent = accent or TH.ACCENT
        from .i18n import tr
        text = tr(text)
        self.setStyleSheet(f"QLabel {{ background: {TH.PANEL2}; color: {TH.TEXT}; border: 1px solid {accent}; "
                           f"border-radius: 10px; padding: 9px 18px; font-size: 13px; }}")
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        x = (par.width() - self.width()) // 2
        y_end = par.height() - self.height() - 18
        self.move(x, y_end + 24)
        self.show()
        self.raise_()
        self._a_op.stop()
        self._a_op.setStartValue(self._fx.opacity())
        self._a_op.setEndValue(1.0)
        self._a_op.start()
        self._a_pos.stop()
        self._a_pos.setStartValue(QPoint(x, y_end + 24))
        self._a_pos.setEndValue(QPoint(x, y_end))
        self._a_pos.start()
        self._timer.start(ms)

    def _hide_anim(self):
        self._a_op.stop()
        self._a_op.setStartValue(self._fx.opacity())
        self._a_op.setEndValue(0.0)
        self._a_op.start()
        QTimer.singleShot(260, self.hide)


class Collapser(QWidget):
    """Contenitore che apre/chiude il suo contenuto con uno scorrimento animato.

    Il contenuto mantiene la sua altezza naturale e viene semplicemente "scoperto"
    (nessuno schiacciamento dei controlli durante l'animazione).
    """

    def __init__(self, content: QWidget, parent: QWidget | None = None, duration: int = 260):
        super().__init__(parent)
        self.content = content
        content.setParent(self)
        content.move(0, 0)
        content.show()
        self.open = False
        self._h = 0
        self.setFixedHeight(0)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.valueChanged.connect(self._set_h)
        self.anim.finished.connect(self._done)

    def _content_height(self) -> int:
        return max(self.content.sizeHint().height(), self.content.minimumSizeHint().height())

    def _set_h(self, v):
        self._h = int(v)
        self.setFixedHeight(self._h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.content.setFixedWidth(self.width())
        self.content.resize(self.width(), self._content_height())

    def toggle(self) -> bool:
        self.anim.stop()
        self.content.setFixedWidth(self.width())
        self.content.adjustSize()
        target = self._content_height()
        self.content.resize(self.width(), target)
        if self.open:
            self.anim.setStartValue(self.height())
            self.anim.setEndValue(0)
            self.open = False
        else:
            self.anim.setStartValue(self.height())
            self.anim.setEndValue(target)
            self.open = True
        self.anim.start()
        return self.open

    def _done(self):
        if self.open:
            self.setFixedHeight(self._content_height())
