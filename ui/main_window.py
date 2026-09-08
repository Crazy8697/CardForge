"""Card Forge main window: content | style | preview, bottom export bar."""
import json
import os

from PIL import Image
from PySide6.QtCore import QByteArray, Qt, QThread, QTimer, Signal, Slot, QObject
from PySide6.QtGui import QFont, QImage, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QSplitter, QVBoxLayout,
                               QWidget)

from engine.render import CardSpec, FontNotFound, render_card
from ui.preview import FullPreview, PreviewPane
from ui.settings import BASE_DIR_DEFAULT, StylePanel

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PRESETS_DIR = os.path.join(APP_DIR, "presets")

LEGEND = ("## header · [] empty box · [x] checked box · blank line = paragraph "
          "break · **bold** · *italic* · ~~strike~~")


class RenderWorker(QObject):
    done = Signal(int, QImage, int, int, bool)
    failed = Signal(int, str)

    @Slot(int, object, str)
    def render(self, gen, spec, base_path):
        try:
            base = Image.open(base_path)
            res = render_card(spec, base)
            img = res.image
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, img.width * 3,
                          QImage.Format_RGB888).copy()
            self.done.emit(gen, qimg, res.body_px, res.line_count, res.overflow)
        except (FontNotFound, OSError, ValueError) as e:
            self.failed.emit(gen, str(e))


class MainWindow(QWidget):
    render_requested = Signal(int, object, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Forge")
        self.resize(1500, 950)
        self.setAcceptDrops(True)
        self._gen = 0
        self._full_preview = None
        self._recents = []

        # ------------------------------------------------------ left: content
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel("Title"))
        self.title_edit = QLineEdit()
        ll.addWidget(self.title_edit)
        body_row = QHBoxLayout()
        body_row.addWidget(QLabel("Body"))
        body_row.addStretch()
        for text, tip, cb in (
                ("B", "Bold selection (Ctrl+B)", lambda: self._wrap_sel("**")),
                ("I", "Italicize selection (Ctrl+I)", lambda: self._wrap_sel("*")),
                ("S̶", "Strike through selection", lambda: self._wrap_sel("~~")),
                ("##", "Header line(s)", lambda: self._prefix_lines("## ")),
                ("☐", "Empty checkbox line(s)", lambda: self._prefix_lines("[] ")),
                ("☑", "Checked checkbox line(s)", lambda: self._prefix_lines("[x] "))):
            b = QPushButton(text)
            b.setFixedWidth(34)
            b.setToolTip(tip)
            b.clicked.connect(cb)
            body_row.addWidget(b)
        ll.addLayout(body_row)
        self.body_edit = QPlainTextEdit()
        mono = QFont("JetBrainsMono NFM", 10)
        mono.setStyleHint(QFont.Monospace)
        self.body_edit.setFont(mono)
        ll.addWidget(self.body_edit, 1)
        legend = QLabel(LEGEND)
        legend.setStyleSheet("color: #888; font-size: 11px;")
        legend.setWordWrap(True)
        ll.addWidget(legend)
        self.check_group = QGroupBox("Checklist (two-column, all checked)")
        self.check_group.setCheckable(True)
        self.check_group.setChecked(False)
        cgl = QVBoxLayout(self.check_group)
        self.check_edit = QLineEdit()
        self.check_edit.setPlaceholderText("item; item; item")
        cgl.addWidget(self.check_edit)
        ll.addWidget(self.check_group)

        # ------------------------------------------------------ middle: style
        self.style_panel = StylePanel(PRESETS_DIR)

        # ----------------------------------------------------- right: preview
        right = QWidget()
        rl = QVBoxLayout(right)
        self.preview = PreviewPane()
        rl.addWidget(self.preview, 1)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #aaa;")
        rl.addWidget(self.status)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.style_panel)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setStretchFactor(2, 4)
        self.split = split

        # -------------------------------------------------------- bottom bar
        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(QLabel("Out"))
        self.out_dir = QLineEdit(BASE_DIR_DEFAULT)
        bl.addWidget(self.out_dir, 2)
        btn_out = QPushButton("…")
        btn_out.setFixedWidth(28)
        btn_out.clicked.connect(self._browse_out)
        bl.addWidget(btn_out)

        bl.addWidget(QLabel("Day"))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 999)
        bl.addWidget(self.day_spin)
        bl.addWidget(QLabel("Kind"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["d", "dq", "e", "h"])
        self.kind_combo.setEditable(True)  # type anything for a custom kind
        self.kind_combo.setFixedWidth(64)
        bl.addWidget(self.kind_combo)
        bl.addWidget(QLabel("N"))
        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, 999)
        bl.addWidget(self.num_spin)
        bl.addWidget(QLabel("Suffix"))
        self.suffix_combo = QComboBox()
        self.suffix_combo.addItems(["", "q", "a"])
        self.suffix_combo.setEditable(True)
        self.suffix_combo.setFixedWidth(48)
        bl.addWidget(self.suffix_combo)

        self.name_field = QLineEdit()
        self.name_field.setReadOnly(True)
        self.name_field.setFixedWidth(200)
        bl.addWidget(self.name_field)
        self.custom_check = QCheckBox("Custom name")
        bl.addWidget(self.custom_check)

        self.export_btn = QPushButton("Export PNG")
        self.export_btn.clicked.connect(self.export_clicked)
        bl.addWidget(self.export_btn)

        recents_box = QGroupBox("Recent exports")
        rbl = QVBoxLayout(recents_box)
        self.recents_list = QListWidget()
        self.recents_list.setMaximumHeight(90)
        self.recents_list.itemActivated.connect(
            lambda it: os.startfile(it.text()) if os.path.exists(it.text()) else None)
        rbl.addWidget(self.recents_list)

        root = QVBoxLayout(self)
        root.addWidget(split, 1)
        root.addWidget(bottom)
        root.addWidget(recents_box)

        # ---------------------------------------------------- render thread
        self._thread = QThread(self)
        self._worker = RenderWorker()
        self._worker.moveToThread(self._thread)
        self.render_requested.connect(self._worker.render)
        self._worker.done.connect(self._render_done)
        self._worker.failed.connect(self._render_failed)
        self._thread.start()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._fire_render)

        self._cfg_timer = QTimer(self)
        self._cfg_timer.setSingleShot(True)
        self._cfg_timer.setInterval(800)
        self._cfg_timer.timeout.connect(self.save_config)

        # ------------------------------------------------------- wiring
        self.title_edit.textChanged.connect(self._edited)
        self.body_edit.textChanged.connect(self._edited)
        self.check_edit.textChanged.connect(self._edited)
        self.check_group.toggled.connect(self._edited)
        self.style_panel.changed.connect(self._edited)
        for w in (self.day_spin, self.num_spin):
            w.valueChanged.connect(self._name_edited)
        for w in (self.kind_combo, self.suffix_combo):
            w.currentTextChanged.connect(self._name_edited)
        self.custom_check.toggled.connect(self._custom_toggled)
        self.out_dir.textChanged.connect(lambda: self._cfg_timer.start())

        QShortcut(QKeySequence("Ctrl+B"), self, lambda: self._wrap_sel("**"))
        QShortcut(QKeySequence("Ctrl+I"), self, lambda: self._wrap_sel("*"))
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_clicked)
        QShortcut(QKeySequence("Ctrl+S"), self, self.style_panel.save_preset)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self.open_full_preview)

        self.load_config()
        self._update_name()
        self._debounce.start()

    # ----------------------------------------------------------- change flow
    def _edited(self, *a):
        self._debounce.start()
        self._cfg_timer.start()

    def _name_edited(self, *a):
        self._update_name()
        self._cfg_timer.start()

    def _custom_toggled(self, on):
        self.name_field.setReadOnly(not on)
        if not on:
            self._update_name()
        self._cfg_timer.start()

    def _update_name(self):
        if self.custom_check.isChecked():
            return
        name = (f"ksd{self.day_spin.value()}{self.kind_combo.currentText()}"
                f"{self.num_spin.value()}{self.suffix_combo.currentText()}.png")
        self.name_field.setText(name)

    # ----------------------------------------------------------- body markup
    def _wrap_sel(self, marker):
        """Toggle **/*/~~ around the selection (word under cursor if none),
        applied per line so markup never spans a line break."""
        c = self.body_edit.textCursor()
        if not c.hasSelection():
            c.select(QTextCursor.WordUnderCursor)
            if not c.hasSelection():
                return
        m = len(marker)
        lines = c.selectedText().split(" ")
        wrapped = all(l.startswith(marker) and l.endswith(marker) and len(l) >= 2 * m
                      for l in lines if l.strip())
        out = []
        for l in lines:
            if not l.strip():
                out.append(l)
            elif wrapped:
                out.append(l[m:-m])
            else:
                pre = l[:len(l) - len(l.lstrip())]
                post = l[len(l.rstrip()):]
                out.append(f"{pre}{marker}{l.strip()}{marker}{post}")
        c.insertText("\n".join(out))
        self.body_edit.setFocus()

    def _prefix_lines(self, prefix):
        """Toggle a line prefix (## / [] / [x] ) on all selected lines."""
        c = self.body_edit.textCursor()
        start, end = c.selectionStart(), c.selectionEnd()
        c.setPosition(start)
        c.movePosition(QTextCursor.StartOfBlock)
        c.setPosition(end, QTextCursor.KeepAnchor)
        c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        lines = c.selectedText().split(" ")
        have = all(l.startswith(prefix) for l in lines if l.strip())
        out = []
        for l in lines:
            if not l.strip():
                out.append(l)
                continue
            for p in ("## ", "[] ", "[x] "):
                if l.startswith(p):
                    l = l[len(p):]
                    break
            out.append(l if have else prefix + l)
        c.insertText("\n".join(out))
        self.body_edit.setFocus()

    # -------------------------------------------------------------- rendering
    def build_spec(self):
        v = self.style_panel.values()
        return CardSpec(
            body=self.body_edit.toPlainText().strip(),
            title=self.title_edit.text().strip(),
            checklist=self.check_edit.text() if self.check_group.isChecked() else "",
            font=v["body_font"],
            title_font=v["title_font"],
            left=v["left"],
            align=v["align"],
            gap=v["gap"],
            margin=v["margin_pct"] / 100.0,
            top=v["top_pct"] / 100.0,
            bottom=v["bottom_pct"] / 100.0,
            max_size=v["body_max"],
            title_size=v["title_max"],
            spacing=v["spacing"],
            gold_top=tuple(v["gold_top"]),
            gold_mid=tuple(v["gold_mid"]),
            gold_bot=tuple(v["gold_bot"]),
        )

    def _fire_render(self):
        base = self.style_panel.base_path()
        spec = self.build_spec()
        if not base or not os.path.exists(base):
            self.status.setText("base plate not found")
            return
        if not (spec.body or spec.title or spec.checklist):
            self.status.setText("nothing to render")
            return
        self._gen += 1
        self.status.setText("rendering…")
        self.render_requested.emit(self._gen, spec, base)

    @Slot(int, QImage, int, int, bool)
    def _render_done(self, gen, qimg, body_px, line_count, overflow):
        if gen != self._gen:
            return
        self.preview.set_image(qimg)
        msg = f"body {body_px}px · {line_count} lines"
        if overflow:
            msg += ' · <span style="color:#e8a33d;">⚠ shrunk to minimum, still overflows</span>'
        self.status.setText(msg)
        if self._full_preview and self._full_preview.isVisible():
            self._full_preview.set_pixmap(self.preview.pixmap_full())

    @Slot(int, str)
    def _render_failed(self, gen, err):
        if gen != self._gen:
            return
        self.status.setText(f'<span style="color:#e05555;">{err}</span>')

    # ---------------------------------------------------------------- export
    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder",
                                             self.out_dir.text())
        if d:
            self.out_dir.setText(d)

    def export_clicked(self):
        name = self.name_field.text().strip()
        if not name:
            return
        if not name.lower().endswith(".png"):
            name += ".png"
        path = os.path.join(self.out_dir.text().strip(), name)
        if os.path.exists(path):
            if QMessageBox.question(
                    self, "Overwrite?",
                    f"{name} exists in the output folder. Overwrite?") != QMessageBox.Yes:
                return
        self.export_to(path)

    def export_to(self, path):
        """Full-resolution synchronous export; used by the button and tests."""
        base_path = self.style_panel.base_path()
        if not base_path or not os.path.exists(base_path):
            QMessageBox.warning(self, "Export", "base plate not found")
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = render_card(self.build_spec(), Image.open(base_path))
            res.image.save(path, quality=95)
        except (FontNotFound, OSError) as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Export", str(e))
            return False
        QApplication.restoreOverrideCursor()
        self._add_recent(path)
        self.status.setText(f"exported {os.path.basename(path)} "
                            f"({res.image.width}x{res.image.height}, "
                            f"body {res.body_px}px)")
        self.save_config()
        return True

    def _add_recent(self, path):
        if path in self._recents:
            self._recents.remove(path)
        self._recents.insert(0, path)
        self._recents = self._recents[:10]
        self.recents_list.clear()
        self.recents_list.addItems(self._recents)

    # ----------------------------------------------------------- full preview
    def open_full_preview(self):
        pix = self.preview.pixmap_full()
        if pix is None:
            return
        if self._full_preview is None:
            self._full_preview = FullPreview()
        self._full_preview.set_pixmap(pix)
        self._full_preview.show()
        self._full_preview.raise_()

    # ------------------------------------------------------------- drag&drop
    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith(".png")
               for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith(".png"):
                self.style_panel.set_base(p)
                break

    # ---------------------------------------------------------------- config
    def save_config(self):
        cfg = {
            "content": {
                "title": self.title_edit.text(),
                "body": self.body_edit.toPlainText(),
                "checklist_on": self.check_group.isChecked(),
                "checklist": self.check_edit.text(),
            },
            "style": self.style_panel.values(),
            "output": {
                "folder": self.out_dir.text(),
                "day": self.day_spin.value(),
                "kind": self.kind_combo.currentText(),
                "number": self.num_spin.value(),
                "suffix": self.suffix_combo.currentText(),
                "custom_on": self.custom_check.isChecked(),
                "custom_name": self.name_field.text(),
            },
            "recents": self._recents,
            "geometry": bytes(self.saveGeometry().toHex()).decode(),
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, indent=2)
        except OSError:
            pass

    def load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return
        c = cfg.get("content", {})
        self.title_edit.setText(c.get("title", ""))
        self.body_edit.setPlainText(c.get("body", ""))
        self.check_group.setChecked(c.get("checklist_on", False))
        self.check_edit.setText(c.get("checklist", ""))
        if cfg.get("style"):
            self.style_panel.apply(cfg["style"])
        o = cfg.get("output", {})
        self.out_dir.setText(o.get("folder", BASE_DIR_DEFAULT))
        self.day_spin.setValue(o.get("day", 1))
        self.kind_combo.setCurrentText(o.get("kind", "d"))
        self.num_spin.setValue(o.get("number", 1))
        self.suffix_combo.setCurrentText(o.get("suffix", ""))
        self.custom_check.setChecked(o.get("custom_on", False))
        if o.get("custom_on") and o.get("custom_name"):
            self.name_field.setText(o["custom_name"])
        for p in cfg.get("recents", []):
            self._recents.append(p)
        self._recents = self._recents[:10]
        self.recents_list.addItems(self._recents)
        if cfg.get("geometry"):
            self.restoreGeometry(QByteArray.fromHex(cfg["geometry"].encode()))

    def closeEvent(self, e):
        self.save_config()
        self._thread.quit()
        self._thread.wait(3000)
        super().closeEvent(e)
