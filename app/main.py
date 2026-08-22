"""
main.py
=======
Application entry point.  Run with::

    python -m app.main

or directly::

    python app/main.py
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from app.main_window import MainWindow


def main() -> None:
    """
    Create the :class:`QApplication`, configure global defaults, display
    :class:`MainWindow`, and start the Qt event loop.
    """
    app = QApplication(sys.argv)

    # Use a clean, modern sans-serif as the application-wide default font.
    app_font = QFont("Segoe UI", 10)
    app.setFont(app_font)

    window = MainWindow()
    window.resize(720, 580)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
