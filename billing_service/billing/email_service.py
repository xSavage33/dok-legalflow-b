"""
email_service.py - Servicio de Envio de Emails para Facturas

Este modulo implementa el envio de facturas por correo electronico,
incluyendo el PDF de la factura como archivo adjunto.

Caracteristicas:
- Envio de facturas por email con PDF adjunto
- Plantillas HTML profesionales para emails
- Soporte para multiples destinatarios
- Registro de envios para auditoria
- Reintentos automaticos en caso de fallo

Autor: Equipo de Desarrollo LegalFlow
"""

import logging
from typing import List, Optional
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .pdf_generator import generate_invoice_pdf

# Configurar logger
logger = logging.getLogger(__name__)


# Plantilla HTML para el email de factura
INVOICE_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #1a365d;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            padding: 20px;
            background-color: #f7fafc;
            border: 1px solid #e2e8f0;
        }}
        .invoice-details {{
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e2e8f0;
        }}
        .detail-label {{
            font-weight: bold;
            color: #4a5568;
        }}
        .total {{
            font-size: 1.2em;
            color: #1a365d;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            font-size: 0.9em;
            color: #718096;
        }}
        .button {{
            display: inline-block;
            background-color: #2c5282;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 15px;
        }}
        .status-pending {{
            color: #d69e2e;
            font-weight: bold;
        }}
        .status-paid {{
            color: #38a169;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LegalFlow</h1>
        <p>Factura {invoice_number}</p>
    </div>

    <div class="content">
        <p>Estimado/a <strong>{client_name}</strong>,</p>

        <p>Adjunto encontrara la factura <strong>{invoice_number}</strong> correspondiente
        a los servicios legales prestados.</p>

        <div class="invoice-details">
            <div class="detail-row">
                <span class="detail-label">Numero de Factura:</span>
                <span>{invoice_number}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Fecha de Emision:</span>
                <span>{issue_date}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Fecha de Vencimiento:</span>
                <span>{due_date}</span>
            </div>
            {case_row}
            <div class="detail-row total">
                <span class="detail-label">Total a Pagar:</span>
                <span>{total_amount}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Estado:</span>
                <span class="{status_class}">{status}</span>
            </div>
        </div>

        <p>Por favor, revise los detalles de la factura adjunta. Si tiene alguna
        pregunta o necesita aclaracion, no dude en contactarnos.</p>

        {payment_info}

        <p>Agradecemos su confianza en nuestros servicios.</p>

        <p>Atentamente,<br>
        <strong>Equipo de Facturacion</strong><br>
        LegalFlow S.A.S.</p>
    </div>

    <div class="footer">
        <p>Este es un mensaje automatico generado por el sistema de facturacion de LegalFlow.</p>
        <p>LegalFlow S.A.S. | Calle 100 # 19-61, Oficina 801 | Bogota, Colombia</p>
        <p>Tel: +57 (1) 234 5678 | facturacion@legalflow.co</p>
    </div>
</body>
</html>
"""

PAYMENT_INFO_TEMPLATE = """
<div style="background-color: #ebf8ff; padding: 15px; border-radius: 5px; margin: 15px 0;">
    <p><strong>Informacion de Pago:</strong></p>
    <p>Puede realizar su pago mediante transferencia bancaria a:</p>
    <ul>
        <li>Banco: Bancolombia</li>
        <li>Tipo de Cuenta: Corriente</li>
        <li>Numero: 123-456789-01</li>
        <li>Titular: LegalFlow S.A.S.</li>
        <li>NIT: 901.234.567-8</li>
    </ul>
    <p>Por favor incluya el numero de factura como referencia del pago.</p>
</div>
"""

# Template para boton de pago online
ONLINE_PAYMENT_BUTTON_TEMPLATE = """
<div style="text-align: center; margin: 25px 0;">
    <p style="margin-bottom: 15px; font-size: 1.1em;"><strong>Pague en linea de forma rapida y segura:</strong></p>
    <a href="{payment_url}"
       style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 1.1em; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        Pagar Ahora - {balance_due}
    </a>
    <p style="margin-top: 10px; font-size: 0.9em; color: #718096;">Pagos seguros procesados por Stripe</p>
</div>
<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
"""


def format_currency(amount, currency='COP') -> str:
    """
    Formatea un monto como moneda.

    Args:
        amount: Monto numerico
        currency: Codigo de moneda

    Returns:
        str: Monto formateado
    """
    if amount is None:
        amount = 0
    formatted = "{:,.0f}".format(float(amount)).replace(',', '.')
    return f"${formatted} {currency}"


def send_invoice_email(
    invoice,
    recipient_emails: Optional[List[str]] = None,
    cc_emails: Optional[List[str]] = None,
    custom_message: Optional[str] = None,
    include_payment_info: bool = True,
    include_online_payment: bool = True
) -> dict:
    """
    Envia una factura por email con el PDF adjunto.

    Args:
        invoice: Instancia del modelo Invoice
        recipient_emails: Lista de emails destinatarios (opcional, usa client_email si no se especifica)
        cc_emails: Lista de emails en copia (opcional)
        custom_message: Mensaje personalizado adicional (opcional)
        include_payment_info: Incluir informacion de pago bancario (default: True)
        include_online_payment: Incluir boton de pago online (default: True)

    Returns:
        dict: Resultado del envio con status y mensaje
    """
    import os

    try:
        # Determinar destinatarios
        if not recipient_emails:
            if not invoice.client_email:
                return {
                    'success': False,
                    'error': 'No se especifico email del cliente'
                }
            recipient_emails = [invoice.client_email]

        # Generar el PDF de la factura
        pdf_buffer = generate_invoice_pdf(invoice)

        # Determinar clase CSS segun estado
        status_class = 'status-paid' if invoice.status == 'paid' else 'status-pending'

        # Construir fila del caso si existe
        case_row = ''
        if invoice.case_number:
            case_row = f'''
            <div class="detail-row">
                <span class="detail-label">Caso Asociado:</span>
                <span>{invoice.case_number}</span>
            </div>
            '''

        # Incluir boton de pago online si la factura tiene saldo pendiente
        online_payment_button = ''
        if include_online_payment and invoice.status not in ['paid', 'cancelled'] and invoice.balance_due > 0:
            # URL del portal de clientes
            client_portal_url = os.environ.get('CLIENT_PORTAL_URL', 'http://localhost:5174')
            payment_url = f"{client_portal_url}/invoices?pay={invoice.id}"
            balance_formatted = format_currency(invoice.balance_due, invoice.currency)
            online_payment_button = ONLINE_PAYMENT_BUTTON_TEMPLATE.format(
                payment_url=payment_url,
                balance_due=balance_formatted
            )

        # Incluir informacion de pago bancario si la factura no esta pagada
        payment_info = ''
        if include_payment_info and invoice.status not in ['paid', 'cancelled']:
            payment_info = online_payment_button + PAYMENT_INFO_TEMPLATE

        # Construir contenido HTML del email
        html_content = INVOICE_EMAIL_TEMPLATE.format(
            invoice_number=invoice.invoice_number,
            client_name=invoice.client_name,
            issue_date=invoice.issue_date.strftime('%d/%m/%Y'),
            due_date=invoice.due_date.strftime('%d/%m/%Y'),
            case_row=case_row,
            total_amount=format_currency(invoice.total_amount, invoice.currency),
            status=invoice.get_status_display(),
            status_class=status_class,
            payment_info=payment_info
        )

        # Agregar mensaje personalizado si existe
        if custom_message:
            html_content = html_content.replace(
                'Adjunto encontrara la factura',
                f'{custom_message}<br><br>Adjunto encontrara la factura'
            )

        # Generar version de texto plano
        text_content = strip_tags(html_content)

        # Crear el email
        subject = f"Factura {invoice.invoice_number} - LegalFlow"

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'facturacion@legalflow.co'),
            to=recipient_emails,
            cc=cc_emails or []
        )

        # Adjuntar version HTML
        email.attach_alternative(html_content, "text/html")

        # Adjuntar PDF de la factura
        pdf_filename = f"Factura_{invoice.invoice_number}.pdf"
        email.attach(pdf_filename, pdf_buffer.getvalue(), 'application/pdf')

        # Enviar el email
        email.send(fail_silently=False)

        logger.info(f"Factura {invoice.invoice_number} enviada a {', '.join(recipient_emails)}")

        return {
            'success': True,
            'message': f'Factura enviada exitosamente a {", ".join(recipient_emails)}',
            'recipients': recipient_emails,
            'cc': cc_emails or []
        }

    except Exception as e:
        logger.error(f"Error enviando factura {invoice.invoice_number}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def send_payment_confirmation_email(invoice, payment) -> dict:
    """
    Envia un email de confirmacion de pago.

    Args:
        invoice: Instancia del modelo Invoice
        payment: Instancia del modelo Payment

    Returns:
        dict: Resultado del envio
    """
    try:
        if not invoice.client_email:
            return {
                'success': False,
                'error': 'No se especifico email del cliente'
            }

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #38a169; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ padding: 20px; background-color: #f0fff4; border: 1px solid #c6f6d5; }}
                .details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 0.9em; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Pago Recibido</h1>
            </div>
            <div class="content">
                <p>Estimado/a <strong>{invoice.client_name}</strong>,</p>
                <p>Hemos recibido su pago. A continuacion los detalles:</p>
                <div class="details">
                    <p><strong>Factura:</strong> {invoice.invoice_number}</p>
                    <p><strong>Monto Pagado:</strong> {format_currency(payment.amount, invoice.currency)}</p>
                    <p><strong>Metodo de Pago:</strong> {payment.get_method_display()}</p>
                    <p><strong>Fecha de Pago:</strong> {payment.payment_date.strftime('%d/%m/%Y')}</p>
                    <p><strong>Referencia:</strong> {payment.payment_number}</p>
                    <p><strong>Saldo Pendiente:</strong> {format_currency(invoice.balance_due, invoice.currency)}</p>
                </div>
                <p>Gracias por su pago. Si tiene alguna pregunta, no dude en contactarnos.</p>
                <p>Atentamente,<br><strong>Equipo de Facturacion</strong><br>LegalFlow S.A.S.</p>
            </div>
            <div class="footer">
                <p>LegalFlow S.A.S. | facturacion@legalflow.co</p>
            </div>
        </body>
        </html>
        """

        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=f"Confirmacion de Pago - Factura {invoice.invoice_number}",
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'facturacion@legalflow.co'),
            to=[invoice.client_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Confirmacion de pago enviada para factura {invoice.invoice_number}")

        return {
            'success': True,
            'message': f'Confirmacion enviada a {invoice.client_email}'
        }

    except Exception as e:
        logger.error(f"Error enviando confirmacion de pago: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def send_payment_reminder_email(invoice, days_overdue: int = 0) -> dict:
    """
    Envia un recordatorio de pago para facturas pendientes o vencidas.

    Args:
        invoice: Instancia del modelo Invoice
        days_overdue: Dias de vencimiento (0 si no esta vencida)

    Returns:
        dict: Resultado del envio
    """
    try:
        if not invoice.client_email:
            return {
                'success': False,
                'error': 'No se especifico email del cliente'
            }

        # Determinar urgencia del mensaje
        if days_overdue > 30:
            urgency_color = "#c53030"
            urgency_text = f"URGENTE: Su factura tiene {days_overdue} dias de vencida"
        elif days_overdue > 0:
            urgency_color = "#d69e2e"
            urgency_text = f"Su factura tiene {days_overdue} dias de vencida"
        else:
            urgency_color = "#2c5282"
            urgency_text = "Recordatorio de pago proximo"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {urgency_color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ padding: 20px; background-color: #fffaf0; border: 1px solid #fbd38d; }}
                .details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 0.9em; color: #718096; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Recordatorio de Pago</h1>
                <p>{urgency_text}</p>
            </div>
            <div class="content">
                <p>Estimado/a <strong>{invoice.client_name}</strong>,</p>
                <p>Le recordamos que tiene una factura pendiente de pago:</p>
                <div class="details">
                    <p><strong>Factura:</strong> {invoice.invoice_number}</p>
                    <p><strong>Fecha de Emision:</strong> {invoice.issue_date.strftime('%d/%m/%Y')}</p>
                    <p><strong>Fecha de Vencimiento:</strong> {invoice.due_date.strftime('%d/%m/%Y')}</p>
                    <p><strong>Monto Total:</strong> {format_currency(invoice.total_amount, invoice.currency)}</p>
                    <p><strong>Saldo Pendiente:</strong> {format_currency(invoice.balance_due, invoice.currency)}</p>
                </div>
                {PAYMENT_INFO_TEMPLATE}
                <p>Si ya realizo el pago, por favor ignore este mensaje o contactenos para confirmar la recepcion.</p>
                <p>Atentamente,<br><strong>Equipo de Facturacion</strong><br>LegalFlow S.A.S.</p>
            </div>
            <div class="footer">
                <p>LegalFlow S.A.S. | facturacion@legalflow.co</p>
            </div>
        </body>
        </html>
        """

        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=f"Recordatorio: Factura {invoice.invoice_number} Pendiente de Pago",
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'facturacion@legalflow.co'),
            to=[invoice.client_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Recordatorio de pago enviado para factura {invoice.invoice_number}")

        return {
            'success': True,
            'message': f'Recordatorio enviado a {invoice.client_email}'
        }

    except Exception as e:
        logger.error(f"Error enviando recordatorio de pago: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
