"""Anteprima con zoom (rotella) e trascinamento."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItemGroup, QGraphicsPixmapItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

from . import theme as TH


def numpy_to_qimage(rgb8: np.ndarray) -> QImage:
    if rgb8.ndim == 2:
        rgb8 = np.repeat(rgb8[:, :, None], 3, axis=2)
    rgb8 = np.ascontiguousarray(rgb8[:, :, :3], dtype=np.uint8)
    h, w = rgb8.shape[:2]
    img = QImage(rgb8.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.copy()   # copia: il buffer numpy può essere liberato


class ImageView(QGraphicsView):
    zoom_changed = Signal(float)
    paint_at = Signal(float, float, bool)     # x, y in pixel dell'anteprima, True = primo punto
    paint_done = Signal()
    sampled = Signal(float, float)            # pipetta: punto scelto

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._item)
        # secondo livello per la dissolvenza tra un'anteprima e la successiva
        self._item2 = QGraphicsPixmapItem()
        self._item2.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._item2.setZValue(1)
        self._item2.setOpacity(0.0)
        self._scene.addItem(self._item2)
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(lambda v: self._item2.setOpacity(float(v)))
        self._fade.finished.connect(self._fade_done)
        self._zoom_anim = QVariantAnimation(self)
        self._zoom_anim.setDuration(160)
        self._zoom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._zoom_anim.valueChanged.connect(self._apply_zoom)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setStyleSheet(f"QGraphicsView {{ background: {TH.BG}; border: none; }}")
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._fitted = True
        self._has_image = False
        self._ann_group = None
        self._ann_visible = True

    def set_image(self, rgb8: np.ndarray, keep_view: bool = True):
        pix = QPixmap.fromImage(numpy_to_qimage(rgb8))
        first = not self._has_image
        same_size = self._item.pixmap().size() == pix.size()
        self._has_image = True
        if first or not same_size:
            self._fade.stop()
            self._item.setPixmap(pix)
            self._item2.setOpacity(0.0)
            self._scene.setSceneRect(self._item.boundingRect())
            self.fit()
            return
        # stessa dimensione: dissolvenza morbida dalla vecchia alla nuova anteprima
        self._fade.stop()
        if self._item2.opacity() > 0:      # dissolvenza precedente ancora in corso: consolida
            self._item.setPixmap(self._item2.pixmap())
        self._item2.setPixmap(pix)
        self._item2.setOpacity(0.0)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        if not keep_view:
            self.fit()

    # ------------------------------------------------------------ pennello (maschere dei livelli)
    def set_paint_mode(self, on: bool):
        self._paint = bool(on)
        self._painting = False
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.OpenHandCursor)

    def set_sample_mode(self, on: bool):
        self._sample = bool(on)
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.ScrollHandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, e):
        if getattr(self, "_sample", False) and e.button() == Qt.MouseButton.LeftButton and self._has_image:
            pt = self.mapToScene(e.position().toPoint())
            self.sampled.emit(float(pt.x()), float(pt.y()))
            e.accept()
            return
        if getattr(self, "_paint", False) and e.button() == Qt.MouseButton.LeftButton and self._has_image:
            self._painting = True
            pt = self.mapToScene(e.position().toPoint())
            self.paint_at.emit(float(pt.x()), float(pt.y()), True)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if getattr(self, "_painting", False):
            pt = self.mapToScene(e.position().toPoint())
            self.paint_at.emit(float(pt.x()), float(pt.y()), False)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if getattr(self, "_painting", False):
            self._painting = False
            self.paint_done.emit()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    # ------------------------------------------------------------ etichette
    def set_annotations(self, items: list, scale: float):
        """items: [{"names": [...], "x": px, "y": px, "radius": px}] in coordinate dell'immagine piena."""
        self.clear_annotations()
        if not items:
            return
        self._ann_group = QGraphicsItemGroup()
        self._ann_group.setZValue(5)
        pen = QPen(QColor(TH.ACCENT), 1.5)
        pen.setCosmetic(True)
        font = QFont()
        font.setPointSizeF(11)
        for a in items:
            x, y = a["x"] * scale, a["y"] * scale
            r = max(a.get("radius", 0) * scale, 6.0)
            circ = QGraphicsEllipseItem(x - r, y - r, 2 * r, 2 * r)
            circ.setPen(pen)
            circ.setBrush(Qt.BrushStyle.NoBrush)
            self._ann_group.addToGroup(circ)
            name = " / ".join(a.get("names", [])[:2])
            if name:
                t = QGraphicsSimpleTextItem(name)
                t.setBrush(QBrush(QColor(TH.ACCENT)))
                t.setFont(font)
                t.setFlag(t.GraphicsItemFlag.ItemIgnoresTransformations, True)   # testo sempre leggibile
                t.setPos(x + r + 3, y - 8)
                self._ann_group.addToGroup(t)
        self._scene.addItem(self._ann_group)
        self._ann_group.setVisible(self._ann_visible)

    def clear_annotations(self):
        g = getattr(self, "_ann_group", None)
        if g is not None:
            self._scene.removeItem(g)
            self._ann_group = None

    def show_annotations(self, on: bool):
        self._ann_visible = bool(on)
        g = getattr(self, "_ann_group", None)
        if g is not None:
            g.setVisible(self._ann_visible)

    def _fade_done(self):
        self._item.setPixmap(self._item2.pixmap())
        self._item2.setOpacity(0.0)

    def clear(self):
        self._fade.stop()
        self._item.setPixmap(QPixmap())
        self._item2.setPixmap(QPixmap())
        self._item2.setOpacity(0.0)
        self._has_image = False

    def _target_fit_scale(self) -> float:
        br = self._item.boundingRect()
        if br.width() <= 0 or br.height() <= 0:
            return 1.0
        vp = self.viewport().rect()
        return min((vp.width() - 4) / br.width(), (vp.height() - 4) / br.height())

    def fit(self, animated: bool = False):
        if not self._has_image:
            return
        self._fitted = True
        if animated:
            self._animate_zoom(self._target_fit_scale(), center=True)
        else:
            self._zoom_anim.stop()
            self.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
            self.zoom_changed.emit(self.transform().m11())

    def zoom_100(self):
        if self._has_image:
            self._fitted = False
            self._animate_zoom(1.0, center=True)

    def _animate_zoom(self, target: float, center: bool = False):
        self._zoom_anim.stop()
        self._center_mode = center
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter if center
                                     else QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom_anim.setStartValue(self.transform().m11())
        self._zoom_anim.setEndValue(float(target))
        self._zoom_anim.start()

    def _apply_zoom(self, v):
        cur = self.transform().m11()
        if cur > 0:
            self.scale(float(v) / cur, float(v) / cur)
        self.zoom_changed.emit(self.transform().m11())

    def wheelEvent(self, e):
        if not self._has_image:
            return
        f = 1.25 if e.angleDelta().y() > 0 else 0.8
        end = self._zoom_anim.endValue() if self._zoom_anim.state() == QVariantAnimation.State.Running else None
        cur = float(end) if end else self.transform().m11()
        if not (0.02 <= cur * f <= 40):
            return
        self._fitted = False
        self._animate_zoom(cur * f, center=False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._has_image and self._fitted:
            self.fit()
