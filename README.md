# cesar-ortega-presupuesto-bot

Bot de Telegram que convierte una tabla (foto o Excel) en un presupuesto PDF con la imagen corporativa de Cesar Ortega SL.

## Flujo del bot

1. `/start`
2. Enviar la tabla: **foto** (la lee la API de Claude) o **archivo .xlsx** (lo lee openpyxl)
3. El bot muestra lo que ha leído → confirmar o reenviar
4. Indicar si los precios son **sin IVA** o **con IVA** (si son con IVA, calcula la base)
5. Nombre del cliente (opcional, `/skip` para omitir)
6. Elegir orientación: vertical u horizontal
7. Recibe el PDF: tabla con filas alternas, subtotal, IVA 21% y total destacado

## Despliegue en Render

1. Crear repo en GitHub y subir estos archivos (incluido `cesar-logo-h.png`)
2. Render → New → **Web Service** → conectar el repo
3. Build command: `./build.sh` — Start command: `python bot.py`
4. Variables de entorno:
   - `TELEGRAM_TOKEN` → token del bot nuevo (BotFather)
   - `ANTHROPIC_API_KEY` → API key de https://console.anthropic.com
   - `PYTHON_VERSION` → `3.11.8`
   - (`RENDER_EXTERNAL_URL` la pone Render automáticamente)

> ⚠️ Si cambias el nombre del repo, actualiza `LOGO_URL` en `bot.py`.

## Notas

- El Excel debe tener una columna de concepto/descripción y una de precio; la de cantidad es opcional (si no hay, cantidad = 1). Ignora filas de TOTAL/Subtotal/IVA.
- La lectura de fotos usa el modelo `claude-haiku-4-5` (rápido y barato). Cada foto cuesta una fracción de céntimo.
- Estructura del presupuesto: Nº automático (P-AAAAMMDD-HHMM), fecha, cliente opcional, validez 15 días.
