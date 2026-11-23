"""Punto de entrada de escritorio para Idealista Scraper Pro.
Lanza la interfaz Qt (PySide6) con estilo Fluent Design, tablas, exportación y minimización al tray.
"""
import sys
from PySide6.QtWidgets import QApplication

from idealista.gui import MainWindow
from idealista.styles import apply_fluent_style


def main():
    app = QApplication(sys.argv)
    apply_fluent_style(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
