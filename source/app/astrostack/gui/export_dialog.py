"""Finestra di esportazione: formato, qualità, risoluzione, nitidezza in uscita."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit,
                               QSlider, QSpinBox, QVBoxLayout)

from ..core.develop import EXPORT_PRESETS, ExportOptions, apply_preset
from . import tooltips as T
from .i18n import tr
from .widgets import AnimatedButton

FORMATS = [("tif16", "TIFF 16 bit (massima qualità)"), ("tif8", "TIFF 8 bit"), ("png16", "PNG 16 bit"),
           ("png8", "PNG 8 bit"), ("jpg", "JPG (per web e social)"), ("fits", "FITS lineare (senza sviluppo, per Siril/PixInsight)")]
SCALE = [("original", "Originale"), ("percent", "Percentuale"), ("width", "Larghezza in pixel")]
UPSCALE = [("lanczos", "Lanczos (nitido)"), ("cubic", "Cubico (morbido)"), ("linear", "Lineare (veloce)")]
SHARP = [("none", "Nessuna"), ("low", "Leggera"), ("standard", "Standard"), ("high", "Forte")]


class ExportDialog(QDialog):
    def __init__(self, image_size: tuple[int, int], has_develop: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Esporta immagine")
        self.setMinimumWidth(460)
        self.qs = QSettings("AstroStack", "AstroStack")
        self.image_size = image_size  # (w, h)
        lay = QVBoxLayout(self)
        f = QFormLayout()
        f.setHorizontalSpacing(12)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.preset = QComboBox()
        for k, label in (("custom", "Personalizzato"), ("instagram", "Instagram / social (1440 px)"),
                         ("web", "Web (2048 px)"), ("wallpaper", "Sfondo 4K (3840 px)"),
                         ("print_a3", "Stampa A3 a 300 dpi")):
            self.preset.addItem(label, k)
        self.preset.setToolTip(T.tip("Preset", "Imposta in un colpo formato, dimensione, qualità e nitidezza per "
                                     "l'uso che hai in mente. Dopo puoi comunque ritoccare i singoli campi."))
        f.addRow("Preset", self.preset)
        self.preset.currentIndexChanged.connect(self._apply_preset)
        self.fmt = QComboBox()
        for k, label in FORMATS:
            self.fmt.addItem(label, k)
        f.addRow("Formato", self.fmt)

        qrow = QHBoxLayout()
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(50, 100)
        self.quality.setValue(92)
        self.quality_label = QLabel("92")
        self.quality_label.setMinimumWidth(30)
        self.quality.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        qrow.addWidget(self.quality)
        qrow.addWidget(self.quality_label)
        self.quality_row = f.rowCount()
        f.addRow("Qualità JPG", qrow)

        self.png_level = QSpinBox()
        self.png_level.setRange(0, 9)
        self.png_level.setValue(6)
        self.png_level.setToolTip("0 = nessuna compressione (file grande, veloce) … 9 = massima (file piccolo, lento). Senza perdita.")
        f.addRow("Compressione PNG", self.png_level)

        self.tiff_comp = QComboBox()
        self.tiff_comp.addItem("Senza perdita (zlib): file più piccolo", "zlib")
        self.tiff_comp.addItem("Nessuna: file più grande, apertura più veloce", "none")
        f.addRow("Compressione TIFF", self.tiff_comp)

        self.scale_mode = QComboBox()
        for k, label in SCALE:
            self.scale_mode.addItem(label, k)
        f.addRow("Risoluzione", self.scale_mode)
        self.scale_percent = QDoubleSpinBox()
        self.scale_percent.setRange(5, 400)
        self.scale_percent.setValue(100)
        self.scale_percent.setSuffix(" %")
        self.scale_percent.setDecimals(0)
        f.addRow("Scala", self.scale_percent)
        self.width_px = QSpinBox()
        self.width_px.setRange(64, 40000)
        self.width_px.setValue(image_size[0])
        self.width_px.setSuffix(" px")
        f.addRow("Larghezza", self.width_px)
        self.size_label = QLabel("")
        self.size_label.setProperty("role", "muted")
        f.addRow("Dimensione finale", self.size_label)
        self.upscale = QComboBox()
        for k, label in UPSCALE:
            self.upscale.addItem(label, k)
        f.addRow("Ingrandimento", self.upscale)
        self.out_sharpen = QComboBox()
        for k, label in SHARP:
            self.out_sharpen.addItem(label, k)
        self.out_sharpen.setCurrentIndex(0)
        f.addRow("Nitidezza in uscita", self.out_sharpen)
        self.apply_dev = QCheckBox("Applica le regolazioni di Sviluppo")
        self.apply_dev.setChecked(has_develop)
        self.apply_dev.setEnabled(has_develop)
        f.addRow(self.apply_dev)
        self.author = QLineEdit(self.qs.value("export_author", "") or "")
        self.author.setPlaceholderText("nome dell'autore (facoltativo)")
        self.author.setToolTip(T.tip("Autore", "Scritto nei metadati del file (non visibile sull'immagine)."))
        f.addRow("Autore", self.author)
        self.copyright = QLineEdit(self.qs.value("export_copyright", "") or "")
        self.copyright.setPlaceholderText("© 2026 …")
        self.copyright.setToolTip(T.tip("Copyright", "Scritto nei metadati del file."))
        f.addRow("Copyright", self.copyright)
        self.watermark = QLineEdit(self.qs.value("export_watermark", "") or "")
        self.watermark.setPlaceholderText("firma stampata in basso a destra (vuoto = nessuna)")
        self.watermark.setToolTip(T.tip("Firma", "Testo scritto sull'immagine, in basso a destra. "
                                        "Lascia vuoto per non stamparlo."))
        f.addRow("Firma", self.watermark)
        lay.addLayout(f)

        brow = QHBoxLayout()
        brow.addStretch(1)
        self.btn_cancel = AnimatedButton("Annulla")
        self.btn_ok = AnimatedButton("Esporta…", "primary")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
        brow.addWidget(self.btn_cancel)
        brow.addWidget(self.btn_ok)
        lay.addLayout(brow)

        for w, key in ((self.fmt, "fmt"), (self.quality, "quality"), (self.png_level, "png_level"),
                       (self.tiff_comp, "tiff_comp"), (self.scale_mode, "scale_mode"), (self.upscale, "upscale"),
                       (self.out_sharpen, "out_sharpen"), (self.apply_dev, "apply_dev")):
            w.setToolTip(T.EXPORT.get(key, w.toolTip()))
            w.setToolTipDuration(60000)

        self.fmt.currentIndexChanged.connect(self._refresh)
        self.scale_mode.currentIndexChanged.connect(self._refresh)
        self.scale_percent.valueChanged.connect(self._refresh)
        self.width_px.valueChanged.connect(self._refresh)
        self._load()
        self._refresh()

    def _refresh(self, *_):
        fmt = self.fmt.currentData()
        self.quality.setEnabled(fmt == "jpg")
        self.png_level.setEnabled(fmt in ("png16", "png8"))
        self.tiff_comp.setEnabled(fmt in ("tif16", "tif8"))
        mode = self.scale_mode.currentData()
        self.scale_percent.setEnabled(mode == "percent")
        self.width_px.setEnabled(mode == "width")
        w, h = self.image_size
        if mode == "percent":
            s = self.scale_percent.value() / 100.0
            nw, nh = int(round(w * s)), int(round(h * s))
        elif mode == "width":
            nw = self.width_px.value()
            nh = int(round(h * nw / max(w, 1)))
        else:
            nw, nh = w, h
        self.size_label.setText(f"{nw} × {nh} px  ({nw * nh / 1e6:.1f} MP)")
        self.upscale.setEnabled(mode != "original" and nw > w)
        self.apply_dev.setEnabled(fmt != "fits" and self.apply_dev.isEnabled() or False)
        if fmt == "fits":
            self.apply_dev.setChecked(False)

    def _apply_preset(self):
        name = self.preset.currentData()
        if name == "custom":
            return
        opt = apply_preset(ExportOptions(), name)
        i = self.fmt.findData(opt.fmt)
        if i >= 0:
            self.fmt.setCurrentIndex(i)
        self.quality.setValue(opt.quality)
        self.scale_mode.setCurrentIndex(max(0, self.scale_mode.findData("width")))
        self.width_px.setValue(opt.width_px)
        j = self.out_sharpen.findData(opt.output_sharpen)
        if j >= 0:
            self.out_sharpen.setCurrentIndex(j)

    def options(self) -> ExportOptions:
        return ExportOptions(fmt=self.fmt.currentData(), quality=self.quality.value(), png_level=self.png_level.value(),
                             tiff_compression=self.tiff_comp.currentData(), scale_mode=self.scale_mode.currentData(),
                             scale_percent=self.scale_percent.value(), width_px=self.width_px.value(),
                             upscale_method=self.upscale.currentData(), output_sharpen=self.out_sharpen.currentData(),
                             apply_develop=self.apply_dev.isChecked(), preset=self.preset.currentData(),
                             author=self.author.text().strip(), copyright=self.copyright.text().strip(),
                             watermark=self.watermark.text().strip())

    def accept(self):
        o = self.options()
        for k, v in o.__dict__.items():
            self.qs.setValue("export_" + k, v)
        super().accept()

    def _load(self):
        def combo(c: QComboBox, key: str):
            v = self.qs.value("export_" + key, None)
            if v is not None:
                i = c.findData(str(v))
                if i >= 0:
                    c.setCurrentIndex(i)
        combo(self.fmt, "fmt"); combo(self.tiff_comp, "tiff_compression"); combo(self.scale_mode, "scale_mode")
        combo(self.upscale, "upscale_method"); combo(self.out_sharpen, "output_sharpen")
        try:
            self.quality.setValue(int(self.qs.value("export_quality", 92)))
            self.png_level.setValue(int(self.qs.value("export_png_level", 6)))
            self.scale_percent.setValue(float(self.qs.value("export_scale_percent", 100)))
        except Exception:
            pass
