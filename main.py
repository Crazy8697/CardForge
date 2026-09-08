#!/usr/bin/env python3
"""Card Forge — gold-text card composer over dark base plates."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "icon.ico")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Card Forge")
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
