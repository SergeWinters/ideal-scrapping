"""Estilos Fluent Design QSS para Idealista Scraper Pro.
Compatible con modo oscuro y basado en Windows 11 Fluent UI.
"""

FLUENT_QSS = """
/* Ventana principal y base */
QMainWindow, QDialog {
    background-color: #1E1E1E;
    color: #F3F3F3;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QWidget {
    color: #E0E0E0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* Tarjetas y Contenedores */
QFrame#CardFrame {
    background-color: #272727;
    border: 1px solid #333333;
    border-radius: 8px;
}

QGroupBox {
    background-color: #242424;
    border: 1px solid #353535;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: #0078D4;
    font-size: 13px;
}

/* Pestañas */
QTabWidget::pane {
    border: 1px solid #333333;
    background-color: #222222;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #272727;
    color: #AAAAAA;
    padding: 8px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    font-weight: 500;
}

QTabBar::tab:hover {
    background: #303030;
    color: #FFFFFF;
}

QTabBar::tab:selected {
    background: #0078D4;
    color: #FFFFFF;
    font-weight: bold;
}

/* Botones */
QPushButton {
    background-color: #2E2E2E;
    border: 1px solid #404040;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    color: #FFFFFF;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #383838;
    border-color: #555555;
}

QPushButton:pressed {
    background-color: #202020;
}

QPushButton:disabled {
    background-color: #222222;
    color: #606060;
    border-color: #2E2E2E;
}

/* Botones de acción acentuados */
QPushButton#PrimaryBtn {
    background-color: #0078D4;
    border: 1px solid #0078D4;
    font-weight: bold;
    color: #FFFFFF;
}

QPushButton#PrimaryBtn:hover {
    background-color: #1084D8;
    border-color: #1084D8;
}

QPushButton#PrimaryBtn:pressed {
    background-color: #006CBD;
}

QPushButton#StopBtn {
    background-color: #C42B1C;
    border: 1px solid #C42B1C;
    font-weight: bold;
    color: #FFFFFF;
}

QPushButton#StopBtn:hover {
    background-color: #D83B2B;
    border-color: #D83B2B;
}

QPushButton#SuccessBtn {
    background-color: #107C10;
    border: 1px solid #107C10;
    font-weight: 600;
    color: #FFFFFF;
}

QPushButton#SuccessBtn:hover {
    background-color: #138E13;
}

/* Entradas y Desplegables */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1A1A1A;
    border: 1px solid #383838;
    border-radius: 6px;
    padding: 6px 10px;
    color: #FFFFFF;
    selection-background-color: #0078D4;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0078D4;
    background-color: #161616;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QCheckBox {
    spacing: 8px;
    color: #DDDDDD;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #484848;
    border-radius: 4px;
    background-color: #1A1A1A;
}

QCheckBox::indicator:hover {
    border-color: #0078D4;
}

QCheckBox::indicator:checked {
    background-color: #0078D4;
    border-color: #0078D4;
}

/* Tabla */
QTableWidget {
    background-color: #202020;
    border: 1px solid #333333;
    border-radius: 8px;
    gridline-color: #2B2B2B;
    selection-background-color: #005A9E;
    selection-color: #FFFFFF;
}

QTableWidget::item {
    padding: 6px 8px;
}

QTableWidget::item:selected {
    background-color: #005A9E;
}

QHeaderView::section {
    background-color: #272727;
    color: #DCDCDC;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid #363636;
    border-bottom: 1px solid #363636;
    font-weight: 600;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #1C1C1C;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #383838;
    min-height: 25px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #505050;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Consola */
QPlainTextEdit#ConsoleLog {
    background-color: #121212;
    color: #00FF66;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid #2F2F2F;
    border-radius: 6px;
    padding: 8px;
}

/* Barra de progreso */
QProgressBar {
    background-color: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 4px;
    text-align: center;
    color: #FFFFFF;
    height: 14px;
}

QProgressBar::chunk {
    background-color: #0078D4;
    border-radius: 3px;
}

/* Barra de estado */
QStatusBar {
    background-color: #181818;
    border-top: 1px solid #2B2B2B;
    color: #9E9E9E;
}
"""


def apply_fluent_style(app):
    """Aplica el estilo nativo de Windows 11 o Fusion + QSS propio."""
    from PySide6.QtWidgets import QStyleFactory
    available_styles = {k.lower() for k in QStyleFactory.keys()}
    if "windows11" in available_styles:
        app.setStyle("windows11")
    elif "fusion" in available_styles:
        app.setStyle("Fusion")
    app.setStyleSheet(FLUENT_QSS)
