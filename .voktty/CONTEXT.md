# Contexto Actual

Última revisión: 2026-11-19.

## Ahora

- **Interfaz Gráfica Fluent:** Implementada en `idealista/gui.py`, lanzable mediante `python app.py` o `.\run_gui.bat`.
- **Soporte Nacional Completo:** Desplegable con las 52 provincias y territorios de España + selectores de Venta y Alquiler.
- **Exportación:** Exportación en vivo a CSV y Excel `.xlsx` con estilos Fluent y enlaces activos desde la tabla de resultados.
- **Sistema de Licencia Activo:** Criptografía Ed25519 idéntica a `certificados`. La misma clave de activación sirve para ambos proyectos.
- **Bandeja del Sistema (Tray):** Minimización en segundo plano con notificaciones de Windows y menú contextual.
- **Pruebas:** 98 tests unitarios pasando al 100%.

## Esperando al propietario

- Ninguna acción pendiente.

## Riesgos activos

- **DataDome / Anti-Bot:** Idealista emplea DataDome. En caso de saltar un Captcha, el usuario debe resolverlo manualmente en la ventana visible del navegador Playwright (evitar modo headless).

## Decisiones clave

- **[D-1] 2026-11-19:** Se reutiliza `HW_SALT = b"DEHuMonitor/hwid/v1"` y `PUBLIC_KEY_B64 = "b+PUpzoBRz9ex73Iuiz2+pR1rUWIjdCPrTsYpkXeHKA="` para compatibilidad total con las licencias de `certificados`.
- **[D-2] 2026-11-19:** Soporte para todas las provincias de España mediante slugs estándar de Idealista y extensión de parsers de ubicación en `search.py` y `detail.py`.
- **[D-3] 2026-11-19:** Defensa contra `None` en filtros numéricos de `config.py` y `gui.py` para evitar errores de comparación `TypeError`.
