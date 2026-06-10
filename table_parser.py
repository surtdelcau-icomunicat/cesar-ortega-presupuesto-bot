"""
Parser de tablas para el bot de presupuestos.
- Excel (.xlsx): openpyxl con detección heurística de columnas
- Imagen (foto de tabla): API de Claude (visión) → JSON
Devuelve siempre: [{'concepto': str, 'cantidad': float, 'precio_unitario': float}, ...]
"""
import os
import json
import base64
import logging

logger = logging.getLogger(__name__)

# ===== EXCEL =====

KEYWORDS_CONCEPTO = ['concepto', 'descripcion', 'descripción', 'producto', 'articulo',
                     'artículo', 'item', 'nombre', 'referencia', 'ref']
KEYWORDS_CANTIDAD = ['cantidad', 'cant', 'uds', 'unidades', 'qty', 'ud', 'q.']
KEYWORDS_PRECIO = ['precio', 'p.unit', 'p. unit', 'unitario', 'importe', 'pvp', 'coste', 'eur', '€']


def _match_col(header_text, keywords):
    t = str(header_text).strip().lower()
    return any(k in t for k in keywords)


def parse_excel(file_path):
    """Lee la primera hoja de un .xlsx y extrae los items."""
    from openpyxl import load_workbook

    wb = load_workbook(file_path, data_only=True)
    ws = wb.active
    rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(v is not None and str(v).strip() != '' for v in r)]
    if not rows:
        raise ValueError("El Excel está vacío")

    # Buscar fila de cabecera en las primeras 5 filas
    col_concepto = col_cantidad = col_precio = None
    header_row_idx = None
    for i, row in enumerate(rows[:5]):
        c_con = c_cant = c_pre = None
        for j, val in enumerate(row):
            if val is None:
                continue
            if c_con is None and _match_col(val, KEYWORDS_CONCEPTO):
                c_con = j
            elif c_cant is None and _match_col(val, KEYWORDS_CANTIDAD):
                c_cant = j
            elif c_pre is None and _match_col(val, KEYWORDS_PRECIO):
                c_pre = j
        if c_con is not None and c_pre is not None:
            col_concepto, col_cantidad, col_precio = c_con, c_cant, c_pre
            header_row_idx = i
            break

    if header_row_idx is None:
        # Sin cabecera reconocible: col 0 = concepto, última col numérica = precio
        header_row_idx = -1
        col_concepto = 0
        first_data = rows[0]
        numeric_cols = [j for j, v in enumerate(first_data) if _to_float(v) is not None]
        if not numeric_cols:
            raise ValueError("No encuentro columnas de precio en el Excel")
        col_precio = numeric_cols[-1]
        col_cantidad = numeric_cols[0] if len(numeric_cols) > 1 else None

    items = []
    for row in rows[header_row_idx + 1:]:
        concepto = row[col_concepto] if col_concepto < len(row) else None
        precio = _to_float(row[col_precio]) if col_precio < len(row) else None
        if concepto is None or str(concepto).strip() == '' or precio is None:
            continue
        # Saltar filas de totales
        if any(k in str(concepto).lower() for k in ['total', 'subtotal', 'iva', 'suma']):
            continue
        cantidad = 1.0
        if col_cantidad is not None and col_cantidad < len(row):
            q = _to_float(row[col_cantidad])
            if q is not None and q > 0:
                cantidad = q
        items.append({
            'concepto': str(concepto).strip()[:80],
            'cantidad': cantidad,
            'precio_unitario': precio
        })

    if not items:
        raise ValueError("No he podido extraer productos del Excel")
    return items


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace('€', '').replace(' ', '')
    # formato español: 1.234,56
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


# ===== IMAGEN (Claude API) =====

PROMPT_VISION = """Analiza esta imagen de una tabla de productos/precios y extrae los datos.

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, con esta estructura exacta:
{"items": [{"concepto": "nombre del producto", "cantidad": 1, "precio_unitario": 15.50}]}

Reglas:
- "cantidad": si la tabla no tiene columna de cantidad, usa 1
- "precio_unitario": número decimal con punto, sin símbolo de euro
- Si los precios usan formato español (1.234,56), conviértelos a decimal (1234.56)
- Ignora filas de totales, subtotales o IVA
- Si hay varias columnas de precio, usa el precio unitario (no el total de línea)
"""


def parse_image(image_path):
    """Extrae la tabla de una imagen usando la API de Claude."""
    import anthropic

    client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY del entorno

    with open(image_path, 'rb') as f:
        image_data = base64.standard_b64encode(f.read()).decode('utf-8')

    ext = os.path.splitext(image_path)[1].lower()
    media_type = 'image/png' if ext == '.png' else 'image/jpeg'

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=4000,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image',
                 'source': {'type': 'base64', 'media_type': media_type, 'data': image_data}},
                {'type': 'text', 'text': PROMPT_VISION}
            ]
        }]
    )

    text = ''.join(block.text for block in message.content if block.type == 'text')
    text = text.replace('```json', '').replace('```', '').strip()

    data = json.loads(text)
    items = []
    for it in data.get('items', []):
        concepto = str(it.get('concepto', '')).strip()
        precio = it.get('precio_unitario')
        if not concepto or precio is None:
            continue
        cantidad = it.get('cantidad', 1) or 1
        items.append({
            'concepto': concepto[:80],
            'cantidad': float(cantidad),
            'precio_unitario': float(precio)
        })

    if not items:
        raise ValueError("No he podido leer productos en la imagen")
    return items
