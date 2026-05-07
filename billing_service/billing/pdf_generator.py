"""
pdf_generator.py - Generador de Facturas PDF

Este modulo implementa la generacion de facturas en formato PDF
usando la biblioteca ReportLab.

Caracteristicas:
- Formato profesional de factura
- Informacion de empresa y cliente
- Detalle de items con precios
- Calculo de subtotales, impuestos y totales
- Notas y terminos de pago
- Informacion bancaria

Autor: Equipo de Desarrollo LegalFlow
"""

import io
from decimal import Decimal
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# Configuracion de la empresa
COMPANY_INFO = {
    'name': 'LegalFlow S.A.S.',
    'address': 'Calle 100 # 19-61, Oficina 801',
    'city': 'Bogotá, Colombia',
    'phone': '+57 (1) 234 5678',
    'email': 'facturacion@legalflow.co',
    'website': 'www.legalflow.co',
    'tax_id': 'NIT: 901.234.567-8',
}


def format_currency(amount, currency='COP') -> str:
    """
    Formatea un monto como moneda.

    Args:
        amount: Monto numerico
        currency: Codigo de moneda (default: COP)

    Returns:
        str: Monto formateado (ej: "$1.234.567 COP")
    """
    if amount is None:
        amount = 0

    # Convertir a Decimal si es necesario
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    # Formatear con separadores de miles
    formatted = "{:,.0f}".format(amount).replace(',', '.')

    return f"${formatted} {currency}"


def generate_invoice_pdf(invoice) -> io.BytesIO:
    """
    Genera un PDF de factura profesional.

    Args:
        invoice: Instancia del modelo Invoice con items y pagos

    Returns:
        io.BytesIO: Buffer con el contenido del PDF
    """
    # Crear buffer en memoria para el PDF
    buffer = io.BytesIO()

    # Crear el documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )

    # Obtener estilos base
    styles = getSampleStyleSheet()

    # Crear estilos personalizados
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=12,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.HexColor('#2c5282'),
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4
    )

    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray
    )

    # Lista de elementos del PDF
    elements = []

    # ==================== ENCABEZADO ====================

    # Titulo de la factura
    elements.append(Paragraph("FACTURA", title_style))
    elements.append(Spacer(1, 0.3*cm))

    # Linea separadora
    elements.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#2c5282'),
        spaceAfter=0.5*cm
    ))

    # Informacion de empresa y factura en dos columnas
    company_data = [
        [
            # Columna izquierda: Datos de la empresa
            Paragraph(f"<b>{COMPANY_INFO['name']}</b>", normal_style),
            # Columna derecha: Datos de la factura
            Paragraph(f"<b>Factura N°:</b> {invoice.invoice_number}", normal_style)
        ],
        [
            Paragraph(COMPANY_INFO['address'], small_style),
            Paragraph(f"<b>Fecha de emisión:</b> {invoice.issue_date.strftime('%d/%m/%Y')}", normal_style)
        ],
        [
            Paragraph(COMPANY_INFO['city'], small_style),
            Paragraph(f"<b>Fecha de vencimiento:</b> {invoice.due_date.strftime('%d/%m/%Y')}", normal_style)
        ],
        [
            Paragraph(f"Tel: {COMPANY_INFO['phone']}", small_style),
            Paragraph(f"<b>Estado:</b> {invoice.get_status_display()}", normal_style)
        ],
        [
            Paragraph(COMPANY_INFO['tax_id'], small_style),
            Paragraph(f"<b>Moneda:</b> {invoice.currency}", normal_style)
        ],
    ]

    header_table = Table(company_data, colWidths=[10*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.5*cm))

    # ==================== DATOS DEL CLIENTE ====================

    elements.append(Paragraph("FACTURAR A:", header_style))

    client_info = f"""
    <b>{invoice.client_name}</b><br/>
    {invoice.client_address or 'Dirección no especificada'}<br/>
    Email: {invoice.client_email or 'No especificado'}<br/>
    {f'NIT/CC: {invoice.client_tax_id}' if invoice.client_tax_id else ''}
    """
    elements.append(Paragraph(client_info, normal_style))

    # Si hay caso asociado
    if invoice.case_number:
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(f"<b>Caso asociado:</b> {invoice.case_number}", normal_style))

    elements.append(Spacer(1, 0.5*cm))

    # ==================== DETALLE DE ITEMS ====================

    elements.append(Paragraph("DETALLE DE SERVICIOS", header_style))

    # Crear tabla de items
    items_data = [
        ['#', 'Descripción', 'Cant.', 'Precio Unit.', 'Total']
    ]

    # Agregar cada item
    for idx, item in enumerate(invoice.items.all(), 1):
        items_data.append([
            str(idx),
            Paragraph(item.description, normal_style),
            f"{item.quantity:.2f}",
            format_currency(item.unit_price, invoice.currency),
            format_currency(item.total, invoice.currency)
        ])

    # Si no hay items
    if invoice.items.count() == 0:
        items_data.append(['', 'No hay items en esta factura', '', '', ''])

    # Crear tabla con estilo
    items_table = Table(items_data, colWidths=[1*cm, 10*cm, 2*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Cuerpo
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Numero
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Cantidad
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Precios

        # Bordes y padding
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),

        # Alternar colores de filas
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*cm))

    # ==================== TOTALES ====================

    totals_data = [
        ['Subtotal:', format_currency(invoice.subtotal, invoice.currency)],
    ]

    if invoice.tax_rate > 0:
        totals_data.append([
            f'Impuesto ({invoice.tax_rate}%):',
            format_currency(invoice.tax_amount, invoice.currency)
        ])

    if invoice.discount_amount > 0:
        totals_data.append([
            'Descuento:',
            f'-{format_currency(invoice.discount_amount, invoice.currency)}'
        ])

    totals_data.append([
        'TOTAL:',
        format_currency(invoice.total_amount, invoice.currency)
    ])

    if invoice.amount_paid > 0:
        totals_data.append([
            'Pagado:',
            format_currency(invoice.amount_paid, invoice.currency)
        ])
        totals_data.append([
            'Saldo pendiente:',
            format_currency(invoice.balance_due, invoice.currency)
        ])

    totals_table = Table(totals_data, colWidths=[5*cm, 4*cm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        # Total en negrita y mas grande
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a365d')),
    ]))

    # Alinear totales a la derecha
    totals_wrapper = Table([[totals_table]], colWidths=[19*cm])
    totals_wrapper.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
    ]))
    elements.append(totals_wrapper)
    elements.append(Spacer(1, 0.5*cm))

    # ==================== PAGOS REGISTRADOS ====================

    if invoice.payments.exists():
        elements.append(Paragraph("PAGOS REGISTRADOS", header_style))

        payments_data = [['Fecha', 'Método', 'Referencia', 'Monto']]
        for payment in invoice.payments.all():
            payments_data.append([
                payment.payment_date.strftime('%d/%m/%Y'),
                payment.get_method_display(),
                payment.reference or '-',
                format_currency(payment.amount, invoice.currency)
            ])

        payments_table = Table(payments_data, colWidths=[3*cm, 4*cm, 6*cm, 4*cm])
        payments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#48bb78')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(payments_table)
        elements.append(Spacer(1, 0.5*cm))

    # ==================== NOTAS Y TERMINOS ====================

    if invoice.notes:
        elements.append(Paragraph("NOTAS:", header_style))
        elements.append(Paragraph(invoice.notes, normal_style))
        elements.append(Spacer(1, 0.3*cm))

    if invoice.terms:
        elements.append(Paragraph("TÉRMINOS Y CONDICIONES:", header_style))
        elements.append(Paragraph(invoice.terms, small_style))
        elements.append(Spacer(1, 0.3*cm))

    # ==================== PIE DE PAGINA ====================

    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(
        width="100%",
        thickness=1,
        color=colors.gray,
        spaceAfter=0.3*cm
    ))

    footer_text = f"""
    <b>Información de pago:</b> Transferencia bancaria a nombre de {COMPANY_INFO['name']}<br/>
    Para consultas sobre esta factura, contacte a {COMPANY_INFO['email']}<br/>
    <br/>
    <i>Documento generado electrónicamente por LegalFlow - {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>
    """
    elements.append(Paragraph(footer_text, small_style))

    # Generar el PDF
    doc.build(elements)

    # Volver al inicio del buffer
    buffer.seek(0)

    return buffer


def generate_invoice_pdf_response(invoice):
    """
    Genera una respuesta HTTP con el PDF de la factura.

    Args:
        invoice: Instancia del modelo Invoice

    Returns:
        HttpResponse: Respuesta HTTP con el PDF
    """
    from django.http import HttpResponse

    # Generar el PDF
    pdf_buffer = generate_invoice_pdf(invoice)

    # Crear respuesta HTTP
    response = HttpResponse(
        pdf_buffer.getvalue(),
        content_type='application/pdf'
    )

    # Nombre del archivo
    filename = f"Factura_{invoice.invoice_number}.pdf"

    # Header para descarga
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
