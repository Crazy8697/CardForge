"""Live preview widgets: scaled-to-fit pane and a 100% zoom window."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea


class PreviewPane(QLabel):
    """Shows the latest full-res render scaled to fit, aspect locked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 380)
        self.setText("preview")
        self.setStyleSheet("background: #1a1a1a; color: #777;")

    def set_image(self, qimg):
        self._pix = QPixmap.fromImage(qimg)
        self._rescale()

    def pixmap_full(self):
        return self._pix

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._pix is None:
            return
        self.setPixmap(self._pix.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class FullPreview(QScrollArea):
    """Separate window showing the render at 100%."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Card Forge — 100% preview")
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self.setWidget(self._label)
        self.setWidgetResizable(False)
        self.resize(1000, 900)

    def set_pixmap(self, pix):
        self._label.setPixmap(pix)
        self._label.resize(pix.size())
