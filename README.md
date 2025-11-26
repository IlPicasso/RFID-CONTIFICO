# RFID-CONTIFICO

## Versión

- 0.2.0
- 0.1.1
- 0.1.0

## Descripción

Guía de referencia para implementar inventarios con RFID integrados a Contífico mediante su API pública. Incluye un cliente mínimo en Python para registrar movimientos de inventario y sincronizar lecturas RFID.

### Componentes incluidos

- Cliente HTTP (`src/contifico_client.py`) con autenticación y helpers para catálogo y movimientos de inventario.
- Script de sincronización (`src/rfid_sync.py`) que agrupa lecturas RFID por SKU y registra un movimiento en Contífico.
- Ejemplo de eventos RFID en `examples/rfid_events.sample.json` listo para pruebas.

## Arquitectura sugerida

1. **Lectura RFID**: lectores ubicados en recepción, almacén y despacho generan eventos con `EPC`, timestamp y ubicación (antena/zona).
2. **Middleware**: servicio (p. ej., FastAPI/Express) que deduplica lecturas, mantiene el mapa `EPC → SKU`, persiste eventos y expone endpoints webhooks/REST.
3. **Integración con Contífico**: procesos que consumen la API de Contífico para crear/actualizar productos, registrar entradas (compras o ajustes positivos), salidas (ventas o ajustes negativos) y consultar existencias para reconciliar.
4. **Observabilidad y alertas**: bitácora de sincronización (éxitos/errores), métricas de latencia y alertas ante discrepancias de stock o EPC no reconocidos.

## Integración funcional con la API de Contífico

1. Instala dependencias: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
2. Define credenciales (variables de entorno o usa `python-dotenv`):

   ```env
   CONTIFICO_API_KEY="<tu Authorization>"
   CONTIFICO_API_TOKEN="<tu X-Api-Token>"
   CONTIFICO_BASE_URL="https://api.contifico.com/sistema/api/v1"
   CONTIFICO_MOVEMENT_ENDPOINT="inventario/guia/"           # opcional
   CONTIFICO_DOCUMENT_TYPE="AJUSTE_RFID"                    # opcional
   ```

3. Prepara lecturas RFID en formato JSON (ver `examples/rfid_events.sample.json`). Cada entrada requiere `epc` y `sku`.
4. Ejecuta un dry-run para validar el payload antes de impactar inventario:

   ```bash
   python -m src.rfid_sync \
     --events examples/rfid_events.sample.json \
     --warehouse-id BODEGA-1 \
     --api-key "$CONTIFICO_API_KEY" \
     --api-token "$CONTIFICO_API_TOKEN" \
     --dry-run
   ```

5. Cuando estés conforme, quita `--dry-run` para registrar el movimiento en Contífico (puedes ajustar `--endpoint` si tu ins
tancia usa una ruta distinta para ajustes):

   ```bash
   python -m src.rfid_sync \
     --events examples/rfid_events.sample.json \
     --warehouse-id BODEGA-1 \
     --api-key "$CONTIFICO_API_KEY" \
     --api-token "$CONTIFICO_API_TOKEN" \
     --observation "Conteo cíclico RFID 2024-09-20" \
     --endpoint inventario/guia/
   ```

El script agrupa las lecturas por SKU, genera el detalle requerido (`codigo_principal` + `cantidad`) y envía un POST al endpo
int configurado usando las cabeceras de autenticación de Contífico.

## Flujo operativo recomendado

- **Alta/recepción**: al recibir mercancía, registra el EPC y asócialo a un SKU existente en Contífico. Crea el producto si no existe y genera el movimiento de entrada (compra o ajuste).
- **Conteo cíclico**: ejecuta barridos periódicos por zona. Compara lecturas con el stock de Contífico y genera ajustes automáticos o pendientes para revisión.
- **Salida/venta**: al despachar o facturar, marca los EPC involucrados y genera la factura/nota de venta en Contífico o un ajuste negativo vinculado.
- **Alertas por ubicación**: si un EPC aparece fuera de su zona asignada o se detecta faltante, dispara una alerta y registra el evento.

## Referencias de API (resumen)

- **Autenticación**: usa el token de API proporcionado por Contífico en el encabezado de autorización (p. ej., `Authorization: Bearer <token>`). Configura variables de entorno para no exponer credenciales.
- **Catálogo de productos**: endpoints para listar, crear o actualizar productos y variaciones; usa `SKU` como llave primaria para mapear `EPC → SKU`.
- **Inventario y movimientos**: endpoints para consultar existencias por bodega y registrar movimientos de entrada/salida (ajustes o compras/ventas). Incluye referencias a bodega y documento para trazabilidad.
- **Ventas y facturación**: creación de facturas/notas de venta vinculando líneas por SKU y cantidad. El middleware puede rebajar existencias tras confirmar una venta.
- **Reportes**: usa exportes (JSON/CSV) para conciliaciones masivas o respaldo offline.

Consulta la documentación oficial de Contífico para la versión y rutas vigentes de la API, límites de rate y reglas fiscales aplicables a tu país.

## Por dónde empezar (plan de arranque)

1) **Accesos y entorno**
   - Solicita el token de API de Contífico y pruébalo con un `GET /products` (o el endpoint equivalente) desde tu red corporativa.
   - Define entorno de pruebas (sandbox o empresa demo) separado de producción; registra las bodegas y centros de costos que usarás.

2) **Catálogo base y mapeo EPC → SKU**
   - Exporta tu catálogo actual de Contífico (CSV) y limpia duplicados de SKU.
   - Crea una tabla de referencia `EPC, SKU, bodega/zona` para la primera ola de productos; esto te servirá para validar lecturas.

3) **Prueba de laboratorio (PoC)**
   - Monta un lector en una sola zona controlada y ejecuta lecturas durante 1-2 días para ajustar parámetros (potencia, dwell time, filtros de RSSI).
   - Implementa un script mínimo que reciba lecturas, las deduplique y guarde en una base ligera (SQLite/Postgres) con timestamp y antena.

4) **Integración mínima con Contífico**
   - Con el mapeo EPC listo, implementa dos llamadas básicas: creación/actualización de productos y registro de movimientos de inventario (ajuste +/–).
   - Define errores tolerables (ej. EPC desconocido) y su manejo: cola de revisión, alertas por correo/Slack o dashboard.

5) **Conteo cíclico y reconciliación**
   - Programa barridos diarios/semanales y compara contra existencias de Contífico por bodega.
   - Genera reportes CSV automáticos de diferencias para revisión y, una vez validados, publica ajustes mediante la API.

6) **Despliegue gradual y monitoreo**
   - Extiende la cobertura a más zonas/bodegas y monitorea métricas: tiempos de conteo, discrepancias, EPC no reconocidos y latencia de API.
   - Configura alertas ante fallos de sincronización (HTTP 4xx/5xx, timeouts) y registra reintentos.

Este plan te permite avanzar en ciclos cortos: primero valida lecturas, luego sincroniza inventario y finalmente escala cobertura y automatización.
