"""Style column: base plate, fonts, layout, sliders, gold palette, presets."""
import json
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPushButton, QRadioButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from engine.render import (FONT_DEFAULT, GOLD_BOT, GOLD_MID, GOLD_TOP,
                           TITLE_FONT_DEFAULT)

BASE_DIR_DEFAULT = r"C:\Users\Adam\Pictures\Barley"            # default output folder
BASES_DIR_DEFAULT = r"C:\Users\Adam\Pictures\Barley\Masters"  # base plates live here
FONTS_DIR = r"C:\Windows\Fonts"


class SliderSpin(QWidget):
    """Slider with a numeric spinbox beside it, int or float."""
    changed = Signal()

    def __init__(self, lo, hi, default, decimals=0, step=1.0, parent=None):
        super().__init__(parent)
        self._decimals = decimals
        self._factor = 10 ** decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(lo * self._factor), int(hi * self._factor))
        if decimals:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(decimals)
            self.spin.setSingleStep(step)
        else:
            self.spin = QSpinBox()
            self.spin.setSingleStep(int(step))
        self.spin.setRange(lo, hi)
        self.spin.setFixedWidth(72)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self._guard = False
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        self.set_value(default)

    def _from_slider(self, v):
        if self._guard:
            return
        self._guard = True
        self.spin.setValue(v / self._factor if self._decimals else v)
        self._guard = False
        self.changed.emit()

    def _from_spin(self, v):
        if self._guard:
            return
        self._guard = True
        self.slider.setValue(int(round(v * self._factor)))
        self._guard = False
        self.changed.emit()

    def value(self):
        return self.spin.value()

    def set_value(self, v):
        self.spin.setValue(v)


class ColorSwatch(QPushButton):
    changed = Signal()

    def __init__(self, label, default_rgb, parent=None):
        super().__init__(parent)
        self._label = label
        self._default = tuple(default_rgb)
        self._rgb = tuple(default_rgb)
        self.setFixedHeight(26)
        self.clicked.connect(self._pick)
        self._paint()

    def _paint(self):
        r, g, b = self._rgb
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        fg = "#000" if lum > 128 else "#fff"
        self.setStyleSheet(f"background: rgb({r},{g},{b}); color: {fg};")
        self.setText(f"{self._label}  {r},{g},{b}")

    def _pick(self):
        c = QColorDialog.getColor(QColor(*self._rgb), self, f"Gold {self._label}")
        if c.isValid():
            self._rgb = (c.red(), c.green(), c.blue())
            self._paint()
            self.changed.emit()

    def value(self):
        return list(self._rgb)

    def set_value(self, rgb):
        self._rgb = tuple(rgb)
        self._paint()
        self.changed.emit()

    def reset(self):
        self.set_value(self._default)


class StylePanel(QWidget):
    """Everything a preset stores. Emits changed on any edit."""
    changed = Signal()

    def __init__(self, presets_dir, parent=None):
        super().__init__(parent)
        self.presets_dir = presets_dir
        os.makedirs(presets_dir, exist_ok=True)
        self._loading = False

        root = QVBoxLayout(self)

        # --- base plate ---
        base_box = QGroupBox("Base plate")
        bl = QHBoxLayout(base_box)
        self.base_combo = QComboBox()
        self.base_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._populate_bases(BASES_DIR_DEFAULT)
        btn_base = QPushButton("Browse…")
        btn_base.clicked.connect(self._browse_base)
        bl.addWidget(self.base_combo, 1)
        bl.addWidget(btn_base)
        root.addWidget(base_box)

        # --- fonts ---
        font_box = QGroupBox("Fonts")
        fl = QFormLayout(font_box)
        self.body_font = self._font_combo(FONT_DEFAULT)
        self.title_font = self._font_combo(TITLE_FONT_DEFAULT)
        fl.addRow("Body", self._with_browse(self.body_font))
        fl.addRow("Title", self._with_browse(self.title_font))
        root.addWidget(font_box)

        # --- layout ---
        lay_box = QGroupBox("Layout")
        ll = QFormLayout(lay_box)
        self.layout_center = QRadioButton("Center")
        self.layout_left = QRadioButton("Left (structured)")
        self.layout_center.setChecked(True)
        row1 = QHBoxLayout()
        row1.addWidget(self.layout_center)
        row1.addWidget(self.layout_left)
        row1.addStretch()
        w1 = QWidget(); w1.setLayout(row1)
        ll.addRow("Text", w1)
        self.valign_top = QRadioButton("Top")
        self.valign_center = QRadioButton("Center")
        self.valign_top.setChecked(True)
        # radios need distinct groups; parent them via container widgets
        row2 = QHBoxLayout()
        row2.addWidget(self.valign_top)
        row2.addWidget(self.valign_center)
        row2.addStretch()
        w2 = QWidget(); w2.setLayout(row2)
        ll.addRow("V-align", w2)
        root.addWidget(lay_box)

        # --- sliders ---
        sl_box = QGroupBox("Sizing")
        sl = QFormLayout(sl_box)
        self.title_max = SliderSpin(40, 400, 150)
        self.body_max = SliderSpin(30, 300, 120)
        self.gap = SliderSpin(0.5, 4.0, 1.7, decimals=1, step=0.1)
        self.spacing = SliderSpin(1.0, 2.0, 1.25, decimals=2, step=0.05)
        self.margin = SliderSpin(2, 20, 8)
        self.region_top = SliderSpin(2, 40, 8)
        self.region_bot = SliderSpin(60, 98, 92)
        sl.addRow("Title max px", self.title_max)
        sl.addRow("Body max px", self.body_max)
        sl.addRow("Gap", self.gap)
        sl.addRow("Line spacing", self.spacing)
        sl.addRow("Side margin %", self.margin)
        sl.addRow("Region top %", self.region_top)
        sl.addRow("Region bottom %", self.region_bot)
        root.addWidget(sl_box)

        # --- gold palette ---
        gold_box = QGroupBox("Gold palette")
        gl = QVBoxLayout(gold_box)
        self.gold_top = ColorSwatch("top", GOLD_TOP)
        self.gold_mid = ColorSwatch("mid", GOLD_MID)
        self.gold_bot = ColorSwatch("bottom", GOLD_BOT)
        btn_reset = QPushButton("Reset to default")
        btn_reset.clicked.connect(self._reset_gold)
        gl.addWidget(self.gold_top)
        gl.addWidget(self.gold_mid)
        gl.addWidget(self.gold_bot)
        gl.addWidget(btn_reset)
        root.addWidget(gold_box)

        # --- presets ---
        pre_box = QGroupBox("Preset")
        pl = QHBoxLayout(pre_box)
        self.preset_combo = QComboBox()
        self._populate_presets()
        btn_save = QPushButton("Save")
        btn_del = QPushButton("Delete")
        btn_save.clicked.connect(self.save_preset)
        btn_del.clicked.connect(self.delete_preset)
        pl.addWidget(self.preset_combo, 1)
        pl.addWidget(btn_save)
        pl.addWidget(btn_del)
        root.addWidget(pre_box)
        root.addStretch()

        self.preset_combo.currentIndexChanged.connect(self._load_preset)

        for w in (self.base_combo, self.body_font, self.title_font):
            w.currentIndexChanged.connect(self._emit_changed)
        for r in (self.layout_center, self.layout_left,
                  self.valign_top, self.valign_center):
            r.toggled.connect(self._emit_changed)
        for s in (self.title_max, self.body_max, self.gap, self.spacing,
                  self.margin, self.region_top, self.region_bot):
            s.changed.connect(self._emit_changed)
        for c in (self.gold_top, self.gold_mid, self.gold_bot):
            c.changed.connect(self._emit_changed)

    # ------------------------------------------------------------------ utils
    def _emit_changed(self, *a):
        if not self._loading:
            self.changed.emit()

    def _with_browse(self, combo):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(combo, 1)
        b = QPushButton("…")
        b.setFixedWidth(28)
        b.clicked.connect(lambda: self._browse_font(combo))
        h.addWidget(b)
        return w

    def _font_combo(self, default_path):
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        try:
            fonts = sorted(f for f in os.listdir(FONTS_DIR)
                           if f.lower().endswith(".ttf"))
        except OSError:
            fonts = []
        for f in fonts:
            combo.addItem(f, os.path.join(FONTS_DIR, f))
        idx = combo.findData(default_path)
        if idx < 0:
            combo.addItem(os.path.basename(default_path), default_path)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)
        return combo

    def _browse_font(self, combo):
        path, _ = QFileDialog.getOpenFileName(self, "Choose font", FONTS_DIR,
                                              "Fonts (*.ttf *.otf)")
        if path:
            self._select_path(combo, path)

    def _populate_bases(self, folder):
        self.base_combo.clear()
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(".png"):
                    self.base_combo.addItem(f, os.path.join(folder, f))
        idx = self.base_combo.findText("card_base_dark50.png")
        if idx >= 0:
            self.base_combo.setCurrentIndex(idx)

    def _browse_base(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose base plate",
                                              BASES_DIR_DEFAULT, "PNG (*.png)")
        if path:
            self.set_base(path)

    def _select_path(self, combo, path):
        idx = combo.findData(path)
        if idx < 0:
            combo.addItem(os.path.basename(path), path)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def set_base(self, path):
        self._select_path(self.base_combo, path)

    def base_path(self):
        return self.base_combo.currentData()

    def _reset_gold(self):
        for c in (self.gold_top, self.gold_mid, self.gold_bot):
            c.reset()

    # ---------------------------------------------------------------- presets
    def _populate_presets(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("(preset)")
        for f in sorted(os.listdir(self.presets_dir)):
            if f.endswith(".json"):
                self.preset_combo.addItem(f[:-5])
        self.preset_combo.blockSignals(False)

    def _load_preset(self, idx):
        if idx <= 0:
            return
        name = self.preset_combo.currentText()
        path = os.path.join(self.presets_dir, name + ".json")
        try:
            with open(path, encoding="utf-8") as fh:
                self.apply(json.load(fh))
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Preset", f"couldn't load {name}: {e}")

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        path = os.path.join(self.presets_dir, name + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.values(), fh, indent=2)
        self._populate_presets()
        idx = self.preset_combo.findText(name)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def delete_preset(self):
        idx = self.preset_combo.currentIndex()
        if idx <= 0:
            return
        name = self.preset_combo.currentText()
        if QMessageBox.question(self, "Delete preset",
                                f"Delete preset '{name}'?") != QMessageBox.Yes:
            return
        try:
            os.remove(os.path.join(self.presets_dir, name + ".json"))
        except OSError:
            pass
        self._populate_presets()

    # ----------------------------------------------------------- (de)persist
    def values(self):
        return {
            "base": self.base_path(),
            "body_font": self.body_font.currentData(),
            "title_font": self.title_font.currentData(),
            "left": self.layout_left.isChecked(),
            "align": "top" if self.valign_top.isChecked() else "center",
            "title_max": self.title_max.value(),
            "body_max": self.body_max.value(),
            "gap": self.gap.value(),
            "spacing": self.spacing.value(),
            "margin_pct": self.margin.value(),
            "top_pct": self.region_top.value(),
            "bottom_pct": self.region_bot.value(),
            "gold_top": self.gold_top.value(),
            "gold_mid": self.gold_mid.value(),
            "gold_bot": self.gold_bot.value(),
        }

    def apply(self, d):
        self._loading = True
        try:
            if d.get("base"):
                self.set_base(d["base"])
            if d.get("body_font"):
                self._select_path(self.body_font, d["body_font"])
            if d.get("title_font"):
                self._select_path(self.title_font, d["title_font"])
            (self.layout_left if d.get("left") else self.layout_center).setChecked(True)
            (self.valign_top if d.get("align", "top") == "top"
             else self.valign_center).setChecked(True)
            self.title_max.set_value(d.get("title_max", 150))
            self.body_max.set_value(d.get("body_max", 120))
            self.gap.set_value(d.get("gap", 1.7))
            self.spacing.set_value(d.get("spacing", 1.25))
            self.margin.set_value(d.get("margin_pct", 8))
            self.region_top.set_value(d.get("top_pct", 8))
            self.region_bot.set_value(d.get("bottom_pct", 92))
            self.gold_top.set_value(d.get("gold_top", list(GOLD_TOP)))
            self.gold_mid.set_value(d.get("gold_mid", list(GOLD_MID)))
            self.gold_bot.set_value(d.get("gold_bot", list(GOLD_BOT)))
        finally:
            self._loading = False
        self.changed.emit()
