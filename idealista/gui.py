"""Interfaz gráfica de usuario Qt (PySide6) con Fluent Design para Idealista Scraper Pro.
Compatible con todas las provincias de España y con el sistema de licencias de 'certificados'.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import (
    QAction, QBrush, QColor, QDesktopServices, QFont, 
    QIcon, QPainter, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, 
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, 
    QHeaderView, QLabel, QLineEdit, QMainWindow, 
    QMenu, QMessageBox, QPlainTextEdit, QProgressBar, 
    QPushButton, QSpinBox, QSplitter, QStatusBar, 
    QSystemTrayIcon, QTabWidget, QTableWidget, 
    QTableWidgetItem, QVBoxLayout, QWidget
)

from .browser import BrowserSession, ChallengeError
from .config import Config, load_config
from .exporters import export_to_csv, export_to_excel
from .licensing import (
    LocalStore, activate, describe, hwid_text, 
    remove, status, LicenseError
)
from .models import Listing
from .pipeline import run_pipeline, PipelineResult
from .scoring import rank_listings
from .styles import apply_fluent_style

GREEN = "#107C10"
BLUE = "#0078D4"
AMBER = "#D83B01"
RED = "#C42B1C"
GREY = "#8A8886"

# Catálogo completo de todas las provincias de España y zonas populares
SPAIN_PROVINCES = [
    ("--- COMUNIDAD DE MADRID ---", ""),
    ("Madrid (Capital completa)", "madrid-madrid"),
    ("Madrid (Toda la provincia)", "madrid-provincia"),
    ("Madrid - Centro", "madrid/centro"),
    ("Madrid - Chamberí", "madrid/chamberi"),
    ("Madrid - Salamanca", "madrid/barrio-de-salamanca"),
    ("Madrid - Retiro", "madrid/retiro"),
    ("Madrid - Chamartín", "madrid/chamartin"),
    ("Madrid - Tetuán", "madrid/tetuan"),
    ("Madrid - Moncloa / Aravaca", "madrid/moncloa"),
    ("Madrid - Arganzuela", "madrid/arganzuela"),
    ("Madrid - Fuencarral / El Pardo", "madrid/fuencarral"),
    ("Madrid - Carabanchel", "madrid/carabanchel"),
    ("Madrid - Puente de Vallecas", "madrid/puente-de-vallecas"),
    
    ("--- CATALUÑA ---", ""),
    ("Barcelona (Capital)", "barcelona-barcelona"),
    ("Barcelona (Toda la provincia)", "barcelona-provincia"),
    ("Barcelona - Eixample", "barcelona/eixample"),
    ("Barcelona - Gràcia", "barcelona/gracia"),
    ("Barcelona - Sarrià-Sant Gervasi", "barcelona/sarria-sant-gervasi"),
    ("Girona", "girona-provincia"),
    ("Lleida", "lleida-provincia"),
    ("Tarragona", "tarragona-provincia"),

    ("--- ANDALUCÍA ---", ""),
    ("Sevilla (Capital)", "sevilla-sevilla"),
    ("Sevilla (Toda la provincia)", "sevilla-provincia"),
    ("Málaga (Capital)", "malaga-malaga"),
    ("Málaga (Toda la provincia)", "malaga-provincia"),
    ("Almería", "almeria-provincia"),
    ("Cádiz", "cadiz-provincia"),
    ("Córdoba", "cordoba-provincia"),
    ("Granada", "granada-provincia"),
    ("Huelva", "huelva-provincia"),
    ("Jaén", "jaen-provincia"),

    ("--- COMUNIDAD VALENCIANA ---", ""),
    ("Valencia (Capital)", "valencia-valencia"),
    ("Valencia (Toda la provincia)", "valencia-provincia"),
    ("Alicante / Alacant", "alicante"),
    ("Castellón / Castelló", "castellon"),

    ("--- GALICIA ---", ""),
    ("A Coruña", "a-coruna"),
    ("Lugo", "lugo-provincia"),
    ("Ourense", "ourense-provincia"),
    ("Pontevedra (Vigo)", "pontevedra-provincia"),

    ("--- PAÍS VASCO ---", ""),
    ("Vizcaya / Bizkaia (Bilbao)", "vizcaya"),
    ("Guipúzcoa / Gipuzkoa (San Sebastián)", "guipuzcoa"),
    ("Álava / Araba (Vitoria-Gasteiz)", "alava"),

    ("--- CASTILLA Y LEÓN ---", ""),
    ("Ávila", "avila-provincia"),
    ("Burgos", "burgos-provincia"),
    ("León", "leon-provincia"),
    ("Palencia", "palencia-provincia"),
    ("Salamanca", "salamanca-provincia"),
    ("Segovia", "segovia-provincia"),
    ("Soria", "soria-provincia"),
    ("Valladolid", "valladolid-provincia"),
    ("Zamora", "zamora-provincia"),

    ("--- CASTILLA-LA MANCHA ---", ""),
    ("Albacete", "albacete-provincia"),
    ("Ciudad Real", "ciudad-real-provincia"),
    ("Cuenca", "cuenca-provincia"),
    ("Guadalajara", "guadalajara-provincia"),
    ("Toledo", "toledo-provincia"),

    ("--- CANARIAS Y BALEARES ---", ""),
    ("Baleares (Mallorca, Menorca, Ibiza)", "baleares"),
    ("Las Palmas (Gran Canaria, Lanzarote, Fuerteventura)", "las-palmas"),
    ("Santa Cruz de Tenerife (Tenerife, La Palma, Gomera)", "santa-cruz-de-tenerife-provincia"),

    ("--- OTRAS COMUNIDADES Y CIUDADES ---", ""),
    ("Asturias", "asturias"),
    ("Cantabria", "cantabria"),
    ("La Rioja", "la-rioja"),
    ("Murcia", "murcia-provincia"),
    ("Navarra", "navarra"),
    ("Badajoz", "badajoz-provincia"),
    ("Cáceres", "caceres-provincia"),
    ("Zaragoza", "zaragoza-provincia"),
    ("Huesca", "huesca-provincia"),
    ("Teruel", "teruel-provincia"),
    ("Ceuta", "ceuta"),
    ("Melilla", "melilla"),
]

TABLE_COLUMNS = [
    "#", "Score", "Oportunidad", "Precio (€)", "€/m²", 
    "vs Área", "Hab.", "m²", "Planta", "Ascensor", 
    "Barrio", "Enlace"
]


def make_round_icon(color_hex: str, letter: str = "I") -> QIcon:
    """Genera un icono circular dinámico para la aplicación y la bandeja del sistema."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 28, QFont.Bold)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, letter)
    p.end()
    return QIcon(pm)


class ScraperWorker(QThread):
    """Hilo secundario para ejecutar el scraping de Idealista sin bloquear la UI."""
    log_signal = Signal(str)
    status_signal = Signal(str)
    finished_signal = Signal(object)
    failed_signal = Signal(str)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self._is_stopped = False

    def run(self):
        self.status_signal.emit("Iniciando navegador...")
        self.log_signal.emit("Iniciando sesión del navegador Playwright...")
        try:
            with BrowserSession(self.cfg) as session:
                self.status_signal.emit("Scrapeando listados de Idealista...")
                result = run_pipeline(
                    self.cfg,
                    session,
                    log=self._handle_log,
                    out=self._handle_log,
                )
                self.finished_signal.emit(result)
        except ChallengeError as exc:
            self.failed_signal.emit(f"Detección Anti-Bot (DataDome/Captcha): {exc}")
        except Exception as exc:
            self.failed_signal.emit(f"Error en la ejecución: {exc}")

    def _handle_log(self, text: str):
        if not self._is_stopped:
            self.log_signal.emit(str(text))


class LicenseTab(QWidget):
    """Pestaña de registro de licencia por Hardware ID idéntica a certificados."""
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.db = LocalStore()
        lay = QVBoxLayout(self)
        lay.setSpacing(16)

        # Tarjeta 1: Hardware ID
        g1 = QGroupBox("Identificador Único del Equipo (Hardware ID)")
        f1 = QFormLayout(g1)
        h1 = QHBoxLayout()
        self.hw_input = QLineEdit(hwid_text())
        self.hw_input.setReadOnly(True)
        self.hw_input.setFont(QFont("Consolas", 12))
        copy_btn = QPushButton("Copiar ID")
        copy_btn.clicked.connect(self.copy_hwid)
        h1.addWidget(self.hw_input)
        h1.addWidget(copy_btn)
        f1.addRow("Hardware ID:", h1)

        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.RichText)
        f1.addRow("Estado:", self.status_label)
        lay.addWidget(g1)

        # Tarjeta 2: Activar Licencia
        g2 = QGroupBox("Activar Licencia")
        v2 = QVBoxLayout(g2)
        inst = QLabel(
            "1) Copia el Hardware ID de este equipo y solicítale tu clave de activación al administrador.<br>"
            "2) Pega aquí la clave entregada (válida para este equipo y compatible con <b>certificados</b>):"
        )
        inst.setWordWrap(True)
        v2.addWidget(inst)

        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-...")
        self.key_input.setMaximumHeight(90)
        v2.addWidget(self.key_input)

        h_btns = QHBoxLayout()
        btn_activate = QPushButton("Activar Licencia")
        btn_activate.setObjectName("PrimaryBtn")
        btn_activate.clicked.connect(self.activate_key)

        btn_remove = QPushButton("Quitar Licencia")
        btn_remove.clicked.connect(self.remove_key)

        h_btns.addWidget(btn_activate)
        h_btns.addWidget(btn_remove)
        h_btns.addStretch()
        v2.addLayout(h_btns)

        self.msg_label = QLabel()
        self.msg_label.setWordWrap(True)
        v2.addWidget(self.msg_label)

        lay.addWidget(g2)
        lay.addStretch()
        self.refresh()

    def copy_hwid(self):
        QApplication.clipboard().setText(self.hw_input.text())
        self.msg_label.setText(f'<span style="color:{GREEN};font-weight:600;">✔ Hardware ID copiado al portapapeles</span>')

    def refresh(self):
        st = status(self.db)
        if st["plan"] == "pro":
            col = AMBER if st["days_left"] <= 7 else GREEN
            self.status_label.setText(f'<span style="color:{col};font-weight:600;">✔ {describe(st)}</span>')
            self.win.plan_badge.setText(f'<span style="color:{col};font-weight:bold;">PRO ({st["days_left"]}d)</span>')
        else:
            self.status_label.setText(f'<span style="color:{GREY};font-weight:600;">● {describe(st)}</span>')
            self.win.plan_badge.setText(f'<span style="color:{GREY};">Plan Básico</span>')

    def activate_key(self):
        raw = self.key_input.toPlainText().strip()
        if not raw:
            self.msg_label.setText(f'<span style="color:{RED};">✖ Por favor ingresa una clave de licencia.</span>')
            return
        try:
            st = activate(self.db, raw)
            self.key_input.clear()
            self.msg_label.setText(f'<span style="color:{GREEN};font-weight:600;">✔ {describe(st)}</span>')
            self.refresh()
            QMessageBox.information(self, "Licencia Activada", f"¡Licencia activada con éxito!\n{describe(st)}")
        except LicenseError as exc:
            self.msg_label.setText(f'<span style="color:{RED};font-weight:600;">✖ {exc}</span>')

    def remove_key(self):
        if QMessageBox.question(self, "Quitar Licencia", "¿Deseas eliminar la licencia de este equipo?") == QMessageBox.Yes:
            remove(self.db)
            self.key_input.clear()
            self.msg_label.clear()
            self.refresh()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Idealista Scraper Pro — Deal Finder")
        self.resize(1180, 760)
        self.setMinimumSize(920, 600)
        self.setWindowIcon(make_round_icon(GREEN, "I"))

        self.db = LocalStore()
        self.worker: ScraperWorker | None = None
        self.last_result: PipelineResult | None = None
        self.all_listings: list[Listing] = []
        self.is_quitting = False

        self.setup_ui()
        self.setup_tray()
        self.load_defaults_into_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Barra Superior de Encabezado
        top_bar = QHBoxLayout()
        title = QLabel("Idealista Deal-Finder")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")
        top_bar.addWidget(title)

        top_bar.addSpacing(16)
        self.plan_badge = QLabel()
        self.plan_badge.setTextFormat(Qt.RichText)
        top_bar.addWidget(self.plan_badge)
        top_bar.addStretch()

        self.btn_open_output = QPushButton("Abrir Carpeta Salida")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        top_bar.addWidget(self.btn_open_output)

        main_layout.addLayout(top_bar)

        # Pestañas Principales
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Filtros y Configuración
        self.tab_filters = QWidget()
        self.setup_filters_tab()
        self.tabs.addTab(self.tab_filters, "Búsqueda y Filtros")

        # Tab 2: Tabla de Resultados
        self.tab_results = QWidget()
        self.setup_results_tab()
        self.tabs.addTab(self.tab_results, "Inmuebles y Análisis")

        # Tab 3: Licencia
        self.tab_license = LicenseTab(self)
        self.tabs.addTab(self.tab_license, "Licencia")

        # Tab 4: Consola / Logs
        self.tab_logs = QWidget()
        self.setup_logs_tab()
        self.tabs.addTab(self.tab_logs, "Consola en Vivo")

        # Barra Inferior: Progreso y Estado
        bot_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(160)
        bot_layout.addWidget(self.progress_bar)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Listo para iniciar búsqueda.")
        bot_layout.addWidget(self.status_bar)

        main_layout.addLayout(bot_layout)

    def setup_filters_tab(self):
        layout = QVBoxLayout(self.tab_filters)
        layout.setSpacing(12)

        # Grupo: Selección de Zona y Operación
        g_url = QGroupBox("Zona Geográfica y URL de Búsqueda")
        v_url = QVBoxLayout(g_url)

        h_selectors = QHBoxLayout()
        
        # Tipo de Operación
        h_selectors.addWidget(QLabel("Operación:"))
        self.combo_operation = QComboBox()
        self.combo_operation.addItems(["Venta", "Alquiler"])
        self.combo_operation.currentIndexChanged.connect(self.update_url_from_selectors)
        h_selectors.addWidget(self.combo_operation)

        h_selectors.addSpacing(16)
        # Provincias de España
        h_selectors.addWidget(QLabel("Provincia / Zona:"))
        self.combo_province = QComboBox()
        self.combo_province.addItem("Personalizada (Escribir abajo)...", "")
        for label, slug in SPAIN_PROVINCES:
            self.combo_province.addItem(label, slug)
        self.combo_province.currentIndexChanged.connect(self.update_url_from_selectors)
        h_selectors.addWidget(self.combo_province, 1)

        v_url.addLayout(h_selectors)

        # Campo de URL editable
        h_url_edit = QHBoxLayout()
        h_url_edit.addWidget(QLabel("URL:"))
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://www.idealista.com/venta-viviendas/madrid-madrid/")
        h_url_edit.addWidget(self.input_url)
        v_url.addLayout(h_url_edit)

        layout.addWidget(g_url)

        # Grupo: Filtros de Precio y Características
        g_filters = QGroupBox("Filtros del Inmueble")
        form_filt = QFormLayout(g_filters)

        h_price = QHBoxLayout()
        self.spin_min_price = QSpinBox()
        self.spin_min_price.setRange(0, 10000000)
        self.spin_min_price.setSingleStep(10000)
        self.spin_min_price.setSuffix(" €")
        self.spin_min_price.setValue(0)

        self.spin_max_price = QSpinBox()
        self.spin_max_price.setRange(0, 20000000)
        self.spin_max_price.setSingleStep(10000)
        self.spin_max_price.setSuffix(" €")
        self.spin_max_price.setValue(350000)

        h_price.addWidget(QLabel("Mín:"))
        h_price.addWidget(self.spin_min_price)
        h_price.addWidget(QLabel("Máx:"))
        h_price.addWidget(self.spin_max_price)
        form_filt.addRow("Precio (€):", h_price)

        h_spec = QHBoxLayout()
        self.spin_min_rooms = QSpinBox()
        self.spin_min_rooms.setRange(0, 10)
        self.spin_min_rooms.setValue(2)

        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(0, 1000)
        self.spin_min_size.setSingleStep(5)
        self.spin_min_size.setSuffix(" m²")
        self.spin_min_size.setValue(50)

        h_spec.addWidget(QLabel("Mín Habitaciones:"))
        h_spec.addWidget(self.spin_min_rooms)
        h_spec.addWidget(QLabel("Mín Superficie:"))
        h_spec.addWidget(self.spin_min_size)
        form_filt.addRow("Características:", h_spec)

        self.chk_elevator = QCheckBox("Exigir Ascensor (--require-elevator)")
        form_filt.addRow("", self.chk_elevator)

        layout.addWidget(g_filters)

        # Grupo: Opciones de Scraping y Rendimiento
        g_scrap = QGroupBox("Opciones del Motor de Scraping")
        form_scrap = QFormLayout(g_scrap)

        h_pages = QHBoxLayout()
        self.spin_pages = QSpinBox()
        self.spin_pages.setRange(1, 30)
        self.spin_pages.setValue(1)

        self.chk_pagination = QCheckBox("Permitir Paginación (--allow-pagination)")
        h_pages.addWidget(self.spin_pages)
        h_pages.addWidget(self.chk_pagination)
        h_pages.addStretch()
        form_scrap.addRow("Páginas a extraer:", h_pages)

        self.spin_details = QSpinBox()
        self.spin_details.setRange(0, 150)
        self.spin_details.setValue(30)
        form_scrap.addRow("Límite de detalles enriquecidos:", self.spin_details)

        h_flags = QHBoxLayout()
        self.chk_cache = QCheckBox("Usar caché de detalles previa")
        self.chk_cache.setChecked(True)
        self.chk_headless = QCheckBox("Navegador oculto / Headless (No recomendado por DataDome)")
        self.chk_headless.setChecked(False)

        h_flags.addWidget(self.chk_cache)
        h_flags.addWidget(self.chk_headless)
        form_scrap.addRow("Opciones:", h_flags)

        layout.addWidget(g_scrap)

        # Botón de Acción Principal
        self.btn_run = QPushButton("🚀 Iniciar Extracción y Análisis")
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.setFixedHeight(40)
        self.btn_run.clicked.connect(self.toggle_scraping)
        layout.addWidget(self.btn_run)

        layout.addStretch()

    def setup_results_tab(self):
        layout = QVBoxLayout(self.tab_results)
        layout.setSpacing(10)

        # Barra de Controles y Filtros Rápidos
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        h_ctrl = QHBoxLayout(top_card)
        h_ctrl.setContentsMargins(10, 8, 10, 8)

        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("🔍 Filtrar por barrio, distrito o texto...")
        self.search_filter.textChanged.connect(self.apply_table_filter)
        h_ctrl.addWidget(self.search_filter)

        self.deal_filter = QComboBox()
        self.deal_filter.addItems(["Todas las ofertas", "great deal", "good deal", "fair", "overpriced"])
        self.deal_filter.currentIndexChanged.connect(self.apply_table_filter)
        h_ctrl.addWidget(self.deal_filter)

        h_ctrl.addSpacing(16)
        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.clicked.connect(self.export_csv_action)
        h_ctrl.addWidget(self.btn_export_csv)

        self.btn_export_excel = QPushButton("Exportar Excel (.xlsx)")
        self.btn_export_excel.setObjectName("SuccessBtn")
        self.btn_export_excel.clicked.connect(self.export_excel_action)
        h_ctrl.addWidget(self.btn_export_excel)

        layout.addWidget(top_card)

        # Tabla de Datos
        self.table = QTableWidget()
        self.table.setColumnCount(len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.on_table_double_clicked)
        layout.addWidget(self.table)

        # Resumen Estadístico Inferior
        self.lbl_stats = QLabel("Sin datos cargados.")
        self.lbl_stats.setStyleSheet("color: #AAAAAA; font-weight: 500;")
        layout.addWidget(self.lbl_stats)

    def setup_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("ConsoleLog")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        h_btn = QHBoxLayout()
        btn_clear = QPushButton("Limpiar Consola")
        btn_clear.clicked.connect(self.log_view.clear)
        h_btn.addStretch()
        h_btn.addWidget(btn_clear)
        layout.addLayout(h_btn)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(make_round_icon(GREEN, "I"), self)
        self.tray.setToolTip("Idealista Scraper Pro")

        menu = QMenu()
        act_open = QAction("Abrir Idealista Scraper", self)
        act_open.triggered.connect(self.restore_window)
        menu.addAction(act_open)

        act_run = QAction("Iniciar Scraping", self)
        act_run.triggered.connect(self.toggle_scraping)
        menu.addAction(act_run)

        menu.addSeparator()
        act_quit = QAction("Salir", self)
        act_quit.triggered.connect(self.quit_application)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)
            self.tray.showMessage(
                "Idealista Scraper",
                "La aplicación sigue ejecutándose en segundo plano.",
                QSystemTrayIcon.Information,
                3000,
            )
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.is_quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Idealista Scraper",
            "Minimizado a la bandeja del sistema. Doble clic para abrir; «Salir» en su menú para cerrar.",
            QSystemTrayIcon.Information,
            3000,
        )

    def quit_application(self):
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, "Salir", "Hay una extracción en curso. ¿Deseas detenerla y salir?") != QMessageBox.Yes:
                return
            self.worker.terminate()
            self.worker.wait(1500)
        self.is_quitting = True
        self.tray.hide()
        QApplication.quit()

    def update_url_from_selectors(self):
        slug = self.combo_province.currentData()
        if not slug:
            return
        op = "alquiler-viviendas" if self.combo_operation.currentText() == "Alquiler" else "venta-viviendas"
        new_url = f"https://www.idealista.com/{op}/{slug}/"
        self.input_url.setText(new_url)

    def load_defaults_into_ui(self):
        try:
            cfg = load_config()
            if cfg.search.urls:
                self.input_url.setText(cfg.search.urls[0])
            self.spin_max_price.setValue(cfg.filters.max_price or 350000)
            self.spin_min_price.setValue(cfg.filters.min_price or 0)
            self.spin_min_rooms.setValue(cfg.filters.min_rooms or 2)
            self.spin_min_size.setValue(int(cfg.filters.min_size_m2 or 50))
            self.chk_elevator.setChecked(bool(cfg.filters.require_elevator))
            self.spin_pages.setValue(cfg.search.max_pages or 1)
            self.chk_pagination.setChecked(bool(cfg.search.allow_pagination))
            self.spin_details.setValue(cfg.search.max_details or 30)
            self.chk_cache.setChecked(bool(cfg.search.use_cache))
            self.chk_headless.setChecked(bool(cfg.search.headless))
        except Exception:
            self.input_url.setText("https://www.idealista.com/venta-viviendas/madrid-madrid/")

    def append_log(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"{stamp}  {text}")

    def toggle_scraping(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "Detener", 
                "¿Deseas interrumpir la extracción en curso?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker._is_stopped = True
                self.worker.terminate()
                self.btn_run.setText("🚀 Iniciar Extracción y Análisis")
                self.btn_run.setObjectName("PrimaryBtn")
                self.btn_run.setStyleSheet("")
                self.progress_bar.setVisible(False)
                self.status_bar.showMessage("Extracción cancelada.")
                self.tray.setIcon(make_round_icon(GREEN, "I"))
            return

        url = self.input_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Por favor ingresa o selecciona una URL de búsqueda.")
            return

        try:
            cfg = load_config()
            cfg.search.urls = [url]
            
            # Filtros numéricos seguros (sin valores None para evitar fallos de comparación)
            max_p = int(self.spin_max_price.value())
            cfg.filters.max_price = max_p if max_p > 0 else 305000
            cfg.filters.min_price = int(self.spin_min_price.value())
            cfg.filters.min_rooms = int(self.spin_min_rooms.value())
            cfg.filters.min_size_m2 = float(self.spin_min_size.value())
            cfg.filters.require_elevator = self.chk_elevator.isChecked()
            
            # Opciones de búsqueda
            cfg.search.max_pages = max(1, self.spin_pages.value())
            cfg.search.allow_pagination = self.chk_pagination.isChecked()
            cfg.search.max_details = max(0, self.spin_details.value())
            cfg.search.use_cache = self.chk_cache.isChecked()
            cfg.search.headless = self.chk_headless.isChecked()
            
            cfg.validate()
        except Exception as exc:
            QMessageBox.critical(self, "Error de Configuración", str(exc))
            return

        self.btn_run.setText("⏹ Detener Extracción")
        self.btn_run.setObjectName("StopBtn")
        self.btn_run.setStyleSheet("background-color: #C42B1C; border-color: #C42B1C; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Iniciando scraper...")
        self.tray.setIcon(make_round_icon(BLUE, "S"))

        self.worker = ScraperWorker(cfg)
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.status_bar.showMessage)
        self.worker.finished_signal.connect(self.on_scraping_finished)
        self.worker.failed_signal.connect(self.on_scraping_failed)
        self.worker.start()

    def on_scraping_finished(self, result: PipelineResult):
        self.last_result = result
        self.all_listings = result.listings
        self.btn_run.setText("🚀 Iniciar Extracción y Análisis")
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.setStyleSheet("")
        self.progress_bar.setVisible(False)
        self.tray.setIcon(make_round_icon(GREEN, "I"))

        self.status_bar.showMessage(f"Completado. {len(result.listings)} inmuebles encontrados y analizados.")
        self.tray.showMessage(
            "Idealista Scraper — Finalizado",
            f"Se han extraído {len(result.listings)} inmuebles ({result.scored} puntuados).",
            QSystemTrayIcon.Information,
            5000,
        )

        self.populate_table(result.listings)
        self.tabs.setCurrentWidget(self.tab_results)

    def on_scraping_failed(self, error_msg: str):
        self.btn_run.setText("🚀 Iniciar Extracción y Análisis")
        self.btn_run.setObjectName("PrimaryBtn")
        self.btn_run.setStyleSheet("")
        self.progress_bar.setVisible(False)
        self.tray.setIcon(make_round_icon(RED, "E"))

        self.status_bar.showMessage("Error durante la extracción.")
        self.append_log(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Fallo en Scraping", error_msg)

    def populate_table(self, listings: list[Listing]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        ranked = rank_listings(listings)
        self.table.setRowCount(len(ranked))

        deal_colors = {
            "great deal": ("#0E700E", "#DFF6DD"),
            "good deal": ("#107C10", "#EBF9EB"),
            "fair": ("#8A6D00", "#FFF4CE"),
            "overpriced": ("#A80000", "#FDE7E9"),
        }

        for r_idx, item in enumerate(ranked):
            score_txt = f"{item.score:.2f}" if item.score is not None else "-"
            band_txt = item.band.title() if item.band else "Sin datos"
            price_txt = f"{item.price:,.0f} €" if item.price is not None else "-"
            eur_m2_txt = f"{item.price_m2:,.0f} €" if item.price_m2 is not None else "-"
            disc_txt = f"{item.discount_pct:+.1f}%" if item.discount_pct is not None else "-"
            rooms_txt = str(item.rooms) if item.rooms is not None else "-"
            size_txt = f"{item.size_m2:.0f}" if item.size_m2 is not None else "-"
            floor_txt = item.floor or "-"
            elev_txt = "Sí" if item.elevator is True else ("No" if item.elevator is False else "?")
            barrio_txt = item.neighborhood or item.district or item.city or "-"

            vals = [
                str(r_idx + 1), score_txt, band_txt, price_txt, eur_m2_txt,
                disc_txt, rooms_txt, size_txt, floor_txt, elev_txt,
                barrio_txt, "Ver ficha"
            ]

            for c_idx, val in enumerate(vals):
                it = QTableWidgetItem(val)
                # Formato y alineación
                if c_idx in (0, 1, 6, 7, 8, 9, 11):
                    it.setTextAlignment(Qt.AlignCenter)
                elif c_idx in (3, 4, 5):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                # Formato del Deal
                if c_idx == 2 and item.band in deal_colors:
                    fg, bg = deal_colors[item.band]
                    it.setForeground(QBrush(QColor(fg)))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)

                # Enlace activo
                if c_idx == 11:
                    it.setForeground(QBrush(QColor(BLUE)))
                    f = it.font()
                    f.setUnderline(True)
                    it.setFont(f)
                    it.setData(Qt.UserRole, item.url)

                self.table.setItem(r_idx, c_idx, it)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.update_stats_label(ranked)

    def update_stats_label(self, listings: list[Listing]):
        if not listings:
            self.lbl_stats.setText("0 inmuebles coincidentes.")
            return

        prices = [x.price for x in listings if x.price]
        avg_price = sum(prices) / len(prices) if prices else 0
        eur_m2 = [x.price_m2 for x in listings if x.price_m2]
        avg_eur_m2 = sum(eur_m2) / len(eur_m2) if eur_m2 else 0

        self.lbl_stats.setText(
            f"Mostrando {len(listings)} inmuebles | "
            f"Precio medio: {avg_price:,.0f} € | "
            f"€/m² medio: {avg_eur_m2:,.0f} €/m²"
        )

    def apply_table_filter(self):
        query = self.search_filter.text().strip().lower()
        deal_sel = self.deal_filter.currentText().lower()

        for r in range(self.table.rowCount()):
            match_text = True
            match_deal = True

            if query:
                row_str = " ".join(
                    self.table.item(r, c).text().lower() 
                    for c in range(self.table.columnCount()) 
                    if self.table.item(r, c)
                )
                match_text = query in row_str

            if deal_sel != "todas las ofertas":
                deal_item = self.table.item(r, 2)
                if deal_item:
                    match_deal = deal_sel == deal_item.text().lower()

            self.table.setRowHidden(r, not (match_text and match_deal))

    def on_table_double_clicked(self, index):
        item = self.table.item(index.row(), 11)
        if item:
            url = item.data(Qt.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def export_csv_action(self):
        if not self.all_listings:
            QMessageBox.warning(self, "Aviso", "No hay datos para exportar.")
            return
        default_file = f"idealista_{datetime.now():%Y%m%d_%H%M}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a CSV", default_file, "Archivos CSV (*.csv)")
        if path:
            export_to_csv(path, self.all_listings)
            QMessageBox.information(self, "Éxito", f"Datos exportados correctamente en:\n{path}")

    def export_excel_action(self):
        if not self.all_listings:
            QMessageBox.warning(self, "Aviso", "No hay datos para exportar.")
            return
        default_file = f"idealista_{datetime.now():%Y%m%d_%H%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_file, "Archivos Excel (*.xlsx)")
        if path:
            export_to_excel(path, self.all_listings)
            QMessageBox.information(self, "Éxito", f"Archivo Excel generado con formato profesional en:\n{path}")

    def open_output_folder(self):
        cfg = load_config()
        out_dir = Path(cfg.output.dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
