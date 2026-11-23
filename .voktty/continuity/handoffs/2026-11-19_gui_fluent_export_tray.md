# Handoff: Implementación de Interfaz Gráfica Fluent, Exportación y Licencia

**Fecha:** 2026-11-19  
**Sesión:** Implementación de GUI Qt, soporte nacional, exportadores y licenciamiento

## Lo que se ha hecho

1. **Interfaz Gráfica de Usuario (GUI):**
   - Implementada en `idealista/gui.py` usando `PySide6`.
   - Lanzadores: `app.py`, `run_gui.bat` y flag `--gui` en `idealista/cli.py`.
   - Pestañas: Búsqueda y Filtros, Inmuebles y Análisis (tabla interactiva sortable), Licencia y Consola de logs en vivo.

2. **Soporte Nacional y Operaciones:**
   - Desplegable con las 52 provincias y territorios de España + zonas principales de Madrid y Barcelona.
   - Selector de operación: Venta (`venta-viviendas`) y Alquiler (`alquiler-viviendas`).
   - Parsers de ubicación en `idealista/search.py` y `idealista/detail.py` actualizados para extraer ciudad y barrio en cualquier provincia de España.

3. **Exportación a CSV y Excel:**
   - Implementado en `idealista/exporters.py`.
   - CSV con codificación UTF-8 BOM y delimitador `;` para compatibilidad directa con Excel.
   - Excel (`.xlsx`) mediante `openpyxl` con estilos Fluent (cabecera azul `#0078D4`, formato de moneda, porcentajes, bordes finos e hipervínculos funcionales en cada anuncio).

4. **Licenciamiento por Hardware ID:**
   - Implementado en `idealista/licensing.py` y `idealista/licensing_pub.py`.
   - 100% compatible con el sistema de `certificados`: utiliza la misma clave pública Ed25519, `HW_SALT = b"DEHuMonitor/hwid/v1"` y algoritmo de MachineGuid.
   - La misma clave de licencia funciona en ambos proyectos.
   - Herramienta de emisión y verificación: `tools/license_admin.py` con clave privada copiada a `tools/_private/license_private.pem`.

5. **Minimización a la Bandeja del Sistema (Tray):**
   - Icono dinámico con `QSystemTrayIcon`.
   - Minimización automática al tray con notificaciones nativas de Windows.
   - Menú contextual para restaurar, iniciar/detener y salir limpiamente.

6. **Estabilidad y Pruebas:**
   - Corregido error `'<' not supported between instances of 'NoneType' and 'int'` asegurando valores numéricos estrictos en `FilterConfig`.
   - Los 98 tests unitarios (`pytest`) pasan con éxito.
