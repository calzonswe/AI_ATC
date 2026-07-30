from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenATC Client")
    app.setOrganizationName("OpenATC")
    app.setAttribute(Qt.ApplicationAttribute.AA_DisableHighDpiScaling, False)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
