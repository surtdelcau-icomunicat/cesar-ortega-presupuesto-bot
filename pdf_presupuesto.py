from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
import os
from datetime import datetime

# Colores corporativos (mismos que el bot de ofertas)
COLOR_PRIMARY = HexColor("#153C8D")
COLOR_PRIMARY_DARK = HexColor("#0F2D6B")
COLOR_SECONDARY = HexColor("#222222")
COLOR_LIGHT_GRAY = HexColor("#F5F5F5")
COLOR_ROW_ALT = HexColor("#EEF2FA")
COLOR_BORDER = HexColor("#E0E0E0")
COLOR_WHITE = white
COLOR_TEXT = HexColor("#333333")
COLOR_TEXT_LIGHT = HexColor("#666666")

IVA_RATE = 0.21



def fmt_eur(x):
    """Formato español: 11.801,75"""
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

class PDFPresupuestoGenerator:
    """
    Genera un presupuesto en PDF a partir de una lista de items:
    items = [{'concepto': str, 'cantidad': float, 'precio_unitario': float}, ...]
    Los precios unitarios se asumen SIN IVA. El IVA se calcula al final.
    """

    def __init__(self, logo_path, orientation='portrait'):
        self.logo_path = logo_path
        self.orientation = orientation

        if orientation == 'landscape':
            self.page_width, self.page_height = landscape(A4)
        else:
            self.page_width, self.page_height = portrait(A4)

        self.margin = 1.2 * cm
        self.header_height = 3 * cm
        self.footer_height = 2.5 * cm

    # ===== HEADER / FOOTER (idénticos al bot de ofertas) =====

    def _draw_header(self, c, doc_number, cliente=None):
        header_height = self.header_height

        c.setFillColor(COLOR_PRIMARY)
        c.rect(0, self.page_height - header_height, self.page_width, header_height, fill=1, stroke=0)

        c.setFillColor(COLOR_PRIMARY_DARK)
        c.rect(0, self.page_height - header_height - 0.15*cm, self.page_width, 0.15*cm, fill=1, stroke=0)

        logo_size = 2 * cm
        logo_x = self.margin
        logo_y = self.page_height - header_height + (header_height - logo_size) / 2

        if self.logo_path and os.path.exists(self.logo_path):
            try:
                c.setFillColor(COLOR_WHITE)
                c.roundRect(logo_x - 0.2*cm, logo_y - 0.2*cm,
                            logo_size + 0.4*cm, logo_size + 0.4*cm,
                            0.2*cm, fill=1, stroke=0)
                c.drawImage(self.logo_path,
                            logo_x, logo_y,
                            width=logo_size, height=logo_size,
                            preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Error logo: {e}")

        text_x = logo_x + logo_size + 0.8*cm
        text_y_center = self.page_height - header_height / 2

        c.setFillColor(COLOR_WHITE)

        if self.orientation == 'portrait':
            company_font_size = 18
            title_font_size = 22
        else:
            company_font_size = 22
            title_font_size = 28

        c.setFont("Helvetica-Bold", company_font_size)
        c.drawString(text_x, text_y_center + 0.1*cm, "CESAR ORTEGA SL")

        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#B8C5E0"))
        c.drawString(text_x, text_y_center - 0.5*cm, "Suministraments Industrials")

        c.setFillColor(COLOR_WHITE)
        c.setFont("Helvetica-Bold", title_font_size)
        title_text = "PRESUPUESTO"
        title_width = c.stringWidth(title_text, "Helvetica-Bold", title_font_size)
        c.drawString(self.page_width - self.margin - title_width, text_y_center + 0.1*cm, title_text)

        fecha = datetime.now().strftime("%d/%m/%Y")
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#B8C5E0"))
        info_text = f"Nº {doc_number}  |  Fecha: {fecha}"
        info_width = c.stringWidth(info_text, "Helvetica", 10)
        c.drawString(self.page_width - self.margin - info_width, text_y_center - 0.5*cm, info_text)

    def _draw_footer(self, c, page_num=1, total_pages=1):
        footer_y = 1.8 * cm

        c.setStrokeColor(COLOR_PRIMARY)
        c.setLineWidth(0.8)
        c.line(self.margin, footer_y, self.page_width - self.margin, footer_y)

        c.setFillColor(COLOR_PRIMARY)
        c.rect(self.margin, footer_y - 0.05*cm, 3*cm, 0.1*cm, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(COLOR_PRIMARY)
        company_name = "CESAR ORTEGA SL"
        c.drawString(self.margin, footer_y - 0.55*cm, company_name)
        name_width = c.stringWidth(company_name, "Helvetica-Bold", 9)

        c.setFont("Helvetica", 8)
        c.setFillColor(COLOR_TEXT_LIGHT)
        c.drawString(self.margin + name_width + 0.3*cm, footer_y - 0.55*cm, "•  Suministros Industriales")

        c.setFont("Helvetica", 8)
        c.setFillColor(COLOR_TEXT)
        c.drawString(self.margin, footer_y - 0.95*cm,
                     "Carrer de la Verge de Montserrat, 31  |  08290 Ripollet, Barcelona")
        c.drawString(self.margin, footer_y - 1.25*cm,
                     "Tel: 936 917 146  |  WhatsApp: +34 678 429 948  |  suministroscesarortega.com")

        c.setFont("Helvetica", 8)
        c.setFillColor(COLOR_TEXT_LIGHT)
        page_text = f"Página {page_num} de {total_pages}"
        page_width = c.stringWidth(page_text, "Helvetica", 8)
        c.drawString(self.page_width - self.margin - page_width, footer_y - 0.55*cm, page_text)

    # ===== TABLA =====

    def _truncate(self, c, text, font, size, max_width):
        if c.stringWidth(text, font, size) <= max_width:
            return text
        while len(text) > 3 and c.stringWidth(text + "…", font, size) > max_width:
            text = text[:-1]
        return text + "…"

    def _columns(self):
        """Define posiciones y anchos de columnas según orientación."""
        usable = self.page_width - 2 * self.margin
        # proporciones: concepto, cantidad, precio unit, total
        if self.orientation == 'landscape':
            props = [0.55, 0.12, 0.16, 0.17]
        else:
            props = [0.46, 0.14, 0.19, 0.21]
        widths = [usable * p for p in props]
        xs = [self.margin]
        for w in widths[:-1]:
            xs.append(xs[-1] + w)
        return xs, widths

    def _draw_table_header(self, c, y):
        xs, widths = self._columns()
        row_h = 0.85 * cm

        c.setFillColor(COLOR_PRIMARY)
        c.roundRect(self.margin, y - row_h, self.page_width - 2*self.margin, row_h, 0.12*cm, fill=1, stroke=0)

        c.setFillColor(COLOR_WHITE)
        c.setFont("Helvetica-Bold", 10)
        text_y = y - row_h + 0.27*cm

        c.drawString(xs[0] + 0.3*cm, text_y, "CONCEPTO")

        for i, label in [(1, "CANTIDAD"), (2, "PRECIO UNIT."), (3, "TOTAL")]:
            w = c.stringWidth(label, "Helvetica-Bold", 10)
            c.drawString(xs[i] + widths[i] - w - 0.3*cm, text_y, label)

        return y - row_h

    def _draw_row(self, c, item, y, alt=False):
        xs, widths = self._columns()
        row_h = 0.75 * cm

        if alt:
            c.setFillColor(COLOR_ROW_ALT)
            c.rect(self.margin, y - row_h, self.page_width - 2*self.margin, row_h, fill=1, stroke=0)

        text_y = y - row_h + 0.24*cm

        concepto = self._truncate(c, str(item['concepto']), "Helvetica", 9.5, widths[0] - 0.6*cm)
        c.setFont("Helvetica", 9.5)
        c.setFillColor(COLOR_TEXT)
        c.drawString(xs[0] + 0.3*cm, text_y, concepto)

        cantidad = item.get('cantidad', 1)
        qty_str = f"{cantidad:g}"
        unit = item['precio_unitario']
        total = round(cantidad * unit, 2)

        c.setFont("Helvetica", 9.5)
        for i, val in [(1, qty_str), (2, f"{fmt_eur(unit)} €")]:
            w = c.stringWidth(val, "Helvetica", 9.5)
            c.drawString(xs[i] + widths[i] - w - 0.3*cm, text_y, val)

        c.setFont("Helvetica-Bold", 9.5)
        total_str = f"{fmt_eur(total)} €"
        w = c.stringWidth(total_str, "Helvetica-Bold", 9.5)
        c.drawString(xs[3] + widths[3] - w - 0.3*cm, text_y, total_str)

        # línea inferior sutil
        c.setStrokeColor(COLOR_BORDER)
        c.setLineWidth(0.4)
        c.line(self.margin, y - row_h, self.page_width - self.margin, y - row_h)

        return y - row_h

    def _draw_totals(self, c, y, subtotal):
        """Caja de totales alineada a la derecha. Devuelve la y final."""
        iva = round(subtotal * IVA_RATE, 2)
        total = round(subtotal + iva, 2)

        box_w = 7 * cm
        line_h = 0.7 * cm
        box_x = self.page_width - self.margin - box_w

        y -= 0.5 * cm

        rows = [
            ("Subtotal (sin IVA)", f"{fmt_eur(subtotal)} €", "Helvetica", 10, COLOR_TEXT),
            ("IVA (21%)", f"{fmt_eur(iva)} €", "Helvetica", 10, COLOR_TEXT),
        ]

        for label, val, font, size, color in rows:
            c.setFont(font, size)
            c.setFillColor(color)
            c.drawString(box_x + 0.3*cm, y - line_h + 0.22*cm, label)
            w = c.stringWidth(val, font, size)
            c.drawString(box_x + box_w - w - 0.3*cm, y - line_h + 0.22*cm, val)
            c.setStrokeColor(COLOR_BORDER)
            c.setLineWidth(0.4)
            c.line(box_x, y - line_h, box_x + box_w, y - line_h)
            y -= line_h

        # Fila TOTAL destacada
        total_h = 0.95 * cm
        c.setFillColor(COLOR_PRIMARY)
        c.roundRect(box_x, y - total_h, box_w, total_h, 0.12*cm, fill=1, stroke=0)
        c.setFillColor(COLOR_WHITE)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(box_x + 0.3*cm, y - total_h + 0.3*cm, "TOTAL")
        total_str = f"{fmt_eur(total)} €"
        w = c.stringWidth(total_str, "Helvetica-Bold", 12)
        c.drawString(box_x + box_w - w - 0.3*cm, y - total_h + 0.3*cm, total_str)

        y -= total_h

        # Nota de validez
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(COLOR_TEXT_LIGHT)
        c.drawString(self.margin, y - 0.1*cm,
                     "Presupuesto válido durante 15 días. Precios sujetos a disponibilidad de stock.")
        return y

    # ===== GENERACIÓN =====

    def generate_pdf(self, items, output_path, cliente=None):
        if self.orientation == 'landscape':
            pagesize = landscape(A4)
        else:
            pagesize = portrait(A4)

        c = canvas.Canvas(output_path, pagesize=pagesize)

        doc_number = datetime.now().strftime("P-%Y%m%d-%H%M")

        content_top = self.page_height - self.header_height - 0.15*cm - 0.6*cm
        content_bottom = self.footer_height + 0.5*cm

        row_h = 0.75 * cm
        header_row_h = 0.85 * cm
        cliente_h = 0.9 * cm if cliente else 0
        totals_h = 0.5*cm + 2 * 0.7*cm + 0.95*cm + 0.6*cm  # caja totales + nota

        # Calcular paginación: filas que caben por página
        usable_first = content_top - content_bottom - cliente_h - header_row_h
        rows_per_page = max(1, int((usable_first - totals_h) // row_h))
        rows_full_page = max(1, int(usable_first // row_h))

        # Distribución simple: si todo cabe en una página con totales, una página.
        n = len(items)
        pages = []
        remaining = list(items)
        while remaining:
            if len(remaining) * row_h + totals_h <= usable_first:
                pages.append(remaining)
                remaining = []
            elif len(remaining) <= rows_full_page:
                # caben las filas pero no los totales → totales en página siguiente
                pages.append(remaining)
                remaining = []
                pages.append([])  # página solo con totales
            else:
                pages.append(remaining[:rows_full_page])
                remaining = remaining[rows_full_page:]

        total_pages = len(pages)
        subtotal = round(sum(i.get('cantidad', 1) * i['precio_unitario'] for i in items), 2)

        for page_num, page_items in enumerate(pages, start=1):
            if page_num > 1:
                c.showPage()

            self._draw_header(c, doc_number, cliente)
            self._draw_footer(c, page_num, total_pages)

            y = content_top

            # Línea de cliente solo en la primera página
            if page_num == 1 and cliente:
                c.setFont("Helvetica", 10)
                c.setFillColor(COLOR_TEXT_LIGHT)
                c.drawString(self.margin, y - 0.5*cm, "Cliente:")
                c.setFont("Helvetica-Bold", 11)
                c.setFillColor(COLOR_SECONDARY)
                c.drawString(self.margin + 1.4*cm, y - 0.5*cm, str(cliente))
                y -= cliente_h

            if page_items:
                y = self._draw_table_header(c, y)
                for idx, item in enumerate(page_items):
                    y = self._draw_row(c, item, y, alt=(idx % 2 == 1))

            # Totales en la última página
            if page_num == total_pages:
                self._draw_totals(c, y, subtotal)

        c.save()
        print(f"Presupuesto generado: {output_path} ({n} items, {total_pages} pág)")
