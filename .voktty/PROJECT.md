# idealista_scrapper

Herramienta de extracción, análisis y búsqueda de oportunidades inmobiliarias en Idealista con soporte para todas las provincias de España, interfaz gráfica Qt (PySide6) con diseño Fluent Design, exportación a CSV/Excel, minimización al System Tray y licenciamiento criptográfico compatible con `certificados`.

## Qué es

Scraper y analizador inmobiliario de Idealista que extrae listados de venta o alquiler, enriquece detalles de inmuebles, calcula métricas de mercado por barrio/distrito y puntúa cada propiedad (great deal, good deal, fair, overpriced) comparándola contra la mediana de su zona. Incluye interfaz de consola (CLI) y aplicación de escritorio gráfica completa.

## Mapa de Componentes

| Componente | Ruta | Descripción |
|---|---|---|
| Interfaz Gráfica (GUI) | `idealista/gui.py`, `app.py` | UI PySide6 Fluent Design con pestañas de filtros, tabla interactiva, visor de logs y tray |
| Estilos Fluent | `idealista/styles.py` | QSS oscuro inspirado en Windows 11 Fluent UI |
| Exportadores | `idealista/exporters.py` | Exportación formateada a CSV (UTF-8-SIG) y Excel (.xlsx con openpyxl) |
| Licenciamiento | `idealista/licensing.py`, `licensing_pub.py` | Validación anti-copia Ed25519 por Hardware ID compatible con `certificados` |
| Admin de Licencias | `tools/license_admin.py` | Generador y verificador de claves criptográficas con clave privada |
| Motor de Búsqueda | `idealista/search.py`, `detail.py` | Extracción de tarjetas y fichas detalladas con Playwright |
| Modelo y Scoring | `idealista/market.py`, `scoring.py` | Estimación de precios de referencia, detección de anomalías y scoring |
| Configuración | `idealista/config.py`, `config.yaml` | Carga de YAML y validación de reglas de búsqueda y filtros |
| CLI | `idealista/cli.py` | Línea de comandos con flags y opción `--gui` |

## Stack y Entorno

- **Lenguaje:** Python 3.11+
- **GUI:** PySide6 (Qt for Python 6.12+)
- **Navegador / Scraping:** Playwright con Chromium persistente
- **Criptografía:** `cryptography` (Ed25519)
- **Hojas de cálculo:** `openpyxl`
- **Parsing HTML:** `lxml`
- **Sistema Operativo:** Windows 11 (PowerShell 7)

## Verificación

```powershell
# Ejecución de la suite completa de pruebas
python -m pytest tests

# Verificación de sintaxis e inicialización de la GUI
python -c "import os; os.environ['QT_QPA_PLATFORM'] = 'offscreen'; from idealista.gui import MainWindow; from PySide6.QtWidgets import QApplication; app = QApplication([]); win = MainWindow(); print('GUI OK')"
```

## Reglas del Proyecto

- **Compatibilidad de Licencias:** Mantener la misma clave pública y la sal `HW_SALT = b"DEHuMonitor/hwid/v1"` para que las claves emitidas en `certificados` funcionen en `idealista_scrapper` sin cambios.
- **Evitar Bloqueos Anti-Bot:** DataDome bloquea activamente el modo headless. Se recomienda mantener el modo con ventana visible por defecto (`headless: false`).
- **Valores Numéricos en Filtros:** Los filtros numéricos de `FilterConfig` (`min_price`, `max_price`, `min_rooms`, `min_size_m2`) deben enviarse como tipos numéricos válidos (enteros/flotantes) y nunca como `None`.

## Trampas Aprendidas

- **Trampa de comparación de NoneType:** En `FilterConfig`, `min_price` con valor `0` no debe evaluarse con `value or None`, ya que asigna `None` y `0 < None` genera `TypeError: '<' not supported between instances of 'NoneType' and 'int'`.
- **Hooks de nodeterm en Windows:** Hooks que invoquen `sh` sin tener Git en el PATH del sistema causan fallo en todas las llamadas de herramientas por `El sistema no puede encontrar la ruta especificada`.
