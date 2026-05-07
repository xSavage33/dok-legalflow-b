"""
notifications.py - Sistema de Notificaciones del Calendario

Este modulo implementa el sistema de notificaciones automaticas para
eventos y plazos del calendario de LegalFlow.

Funcionalidades:
- Notificaciones de recordatorio para eventos
- Alertas de plazos proximos a vencer
- Notificaciones de plazos vencidos
- Envio de emails y notificaciones en el portal

Autor: Equipo de Desarrollo LegalFlow
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils import timezone

from .models import Event, Deadline

# Configurar logger
logger = logging.getLogger(__name__)


# Templates de email
EVENT_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2c5282; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ padding: 20px; background-color: #ebf8ff; border: 1px solid #bee3f8; }}
        .event-details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .detail-row {{ padding: 8px 0; border-bottom: 1px solid #e2e8f0; }}
        .footer {{ text-align: center; padding: 20px; font-size: 0.9em; color: #718096; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Recordatorio de Evento</h1>
    </div>
    <div class="content">
        <p>Estimado/a <strong>{user_name}</strong>,</p>
        <p>Le recordamos que tiene un evento proximo:</p>
        <div class="event-details">
            <div class="detail-row"><strong>Evento:</strong> {event_title}</div>
            <div class="detail-row"><strong>Tipo:</strong> {event_type}</div>
            <div class="detail-row"><strong>Fecha y Hora:</strong> {event_datetime}</div>
            <div class="detail-row"><strong>Ubicacion:</strong> {location}</div>
            {case_info}
            <div class="detail-row"><strong>Descripcion:</strong> {description}</div>
        </div>
        <p>Por favor, asegurese de estar preparado para este evento.</p>
        <p>Atentamente,<br><strong>LegalFlow</strong></p>
    </div>
    <div class="footer">
        <p>Este es un mensaje automatico del sistema de calendario de LegalFlow.</p>
    </div>
</body>
</html>
"""

DEADLINE_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {header_color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ padding: 20px; background-color: {bg_color}; border: 1px solid {border_color}; }}
        .deadline-details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .detail-row {{ padding: 8px 0; border-bottom: 1px solid #e2e8f0; }}
        .priority {{ font-weight: bold; color: {priority_color}; }}
        .footer {{ text-align: center; padding: 20px; font-size: 0.9em; color: #718096; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{header_title}</h1>
        <p>{header_subtitle}</p>
    </div>
    <div class="content">
        <p>Estimado/a <strong>{user_name}</strong>,</p>
        <p>{intro_message}</p>
        <div class="deadline-details">
            <div class="detail-row"><strong>Plazo:</strong> {deadline_title}</div>
            <div class="detail-row"><strong>Fecha de Vencimiento:</strong> {due_date}</div>
            <div class="detail-row"><strong>Dias Restantes:</strong> {days_remaining}</div>
            <div class="detail-row"><strong>Prioridad:</strong> <span class="priority">{priority}</span></div>
            {case_info}
            <div class="detail-row"><strong>Descripcion:</strong> {description}</div>
        </div>
        <p>{action_message}</p>
        <p>Atentamente,<br><strong>LegalFlow</strong></p>
    </div>
    <div class="footer">
        <p>Este es un mensaje automatico del sistema de plazos de LegalFlow.</p>
    </div>
</body>
</html>
"""


def get_priority_color(priority: str) -> str:
    """Retorna el color asociado a una prioridad."""
    colors = {
        'low': '#38a169',      # Verde
        'medium': '#d69e2e',   # Amarillo
        'high': '#dd6b20',     # Naranja
        'critical': '#c53030', # Rojo
    }
    return colors.get(priority, '#718096')


def send_portal_notification(
    recipient_id: str,
    recipient_name: str,
    subject: str,
    content: str,
    case_id: Optional[str] = None,
    case_number: Optional[str] = None
) -> bool:
    """
    Envia una notificacion al portal del cliente.

    Args:
        recipient_id: UUID del destinatario
        recipient_name: Nombre del destinatario
        subject: Asunto de la notificacion
        content: Contenido del mensaje
        case_id: ID del caso asociado (opcional)
        case_number: Numero del caso (opcional)

    Returns:
        bool: True si se envio correctamente, False en caso contrario
    """
    try:
        url = f"{settings.PORTAL_SERVICE_URL}/api/portal/internal/notification/"

        notification_data = {
            'sender_id': '00000000-0000-0000-0000-000000000000',
            'sender_name': 'Sistema de Calendario',
            'sender_role': 'system',
            'recipient_id': recipient_id,
            'recipient_name': recipient_name,
            'case_id': case_id,
            'case_number': case_number or '',
            'subject': subject,
            'content': content,
        }

        headers = {
            'Content-Type': 'application/json',
            'X-Service-Token': getattr(settings, 'INTERNAL_SERVICE_TOKEN', ''),
        }

        response = requests.post(url, json=notification_data, headers=headers, timeout=10)

        if response.status_code == 201:
            logger.info(f"Notificacion enviada al portal para {recipient_name}")
            return True
        else:
            logger.warning(f"Error enviando notificacion al portal: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error enviando notificacion al portal: {str(e)}")
        return False


def send_email_notification(
    to_email: str,
    subject: str,
    html_content: str
) -> bool:
    """
    Envia una notificacion por email.

    Args:
        to_email: Email del destinatario
        subject: Asunto del email
        html_content: Contenido HTML del email

    Returns:
        bool: True si se envio correctamente
    """
    try:
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'calendario@legalflow.co'),
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Email de notificacion enviado a {to_email}")
        return True

    except Exception as e:
        logger.error(f"Error enviando email a {to_email}: {str(e)}")
        return False


def send_event_reminder(event: Event, user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envia un recordatorio de evento a un usuario.

    Args:
        event: Instancia del modelo Event
        user_info: Diccionario con informacion del usuario (id, name, email)

    Returns:
        dict: Resultado del envio
    """
    try:
        # Preparar informacion del caso
        case_info = ''
        if event.case_number:
            case_info = f'<div class="detail-row"><strong>Caso:</strong> {event.case_number}</div>'

        # Formatear el HTML
        html_content = EVENT_REMINDER_TEMPLATE.format(
            user_name=user_info.get('name', 'Usuario'),
            event_title=event.title,
            event_type=event.get_event_type_display(),
            event_datetime=event.start_datetime.strftime('%d/%m/%Y %H:%M'),
            location=event.location or 'No especificada',
            case_info=case_info,
            description=event.description or 'Sin descripcion'
        )

        subject = f"Recordatorio: {event.title} - {event.start_datetime.strftime('%d/%m/%Y %H:%M')}"

        results = {
            'event_id': str(event.id),
            'user_id': user_info.get('id'),
            'email_sent': False,
            'portal_sent': False
        }

        # Enviar email si hay direccion
        if user_info.get('email'):
            results['email_sent'] = send_email_notification(
                user_info['email'],
                subject,
                html_content
            )

        # Enviar notificacion al portal
        results['portal_sent'] = send_portal_notification(
            recipient_id=str(user_info.get('id', '')),
            recipient_name=user_info.get('name', 'Usuario'),
            subject=subject,
            content=f"Recordatorio: {event.title} programado para {event.start_datetime.strftime('%d/%m/%Y %H:%M')}. Ubicacion: {event.location or 'No especificada'}",
            case_id=str(event.case_id) if event.case_id else None,
            case_number=event.case_number
        )

        return results

    except Exception as e:
        logger.error(f"Error enviando recordatorio de evento: {str(e)}")
        return {'error': str(e)}


def send_deadline_reminder(deadline: Deadline, user_info: Dict[str, Any], is_overdue: bool = False) -> Dict[str, Any]:
    """
    Envia un recordatorio de plazo a un usuario.

    Args:
        deadline: Instancia del modelo Deadline
        user_info: Diccionario con informacion del usuario
        is_overdue: Si el plazo ya esta vencido

    Returns:
        dict: Resultado del envio
    """
    try:
        # Configurar colores y mensajes segun urgencia
        days_remaining = deadline.days_remaining or 0

        if is_overdue or days_remaining < 0:
            header_color = '#c53030'
            bg_color = '#fff5f5'
            border_color = '#feb2b2'
            header_title = 'PLAZO VENCIDO'
            header_subtitle = f'Vencido hace {abs(days_remaining)} dias'
            intro_message = 'Este plazo ha vencido y requiere atencion inmediata:'
            action_message = 'Por favor, tome las acciones necesarias lo antes posible.'
        elif days_remaining <= 1:
            header_color = '#c53030'
            bg_color = '#fff5f5'
            border_color = '#feb2b2'
            header_title = 'PLAZO URGENTE'
            header_subtitle = 'Vence hoy o manana'
            intro_message = 'Este plazo vence muy pronto y requiere atencion inmediata:'
            action_message = 'Por favor, complete las tareas pendientes de inmediato.'
        elif days_remaining <= 3:
            header_color = '#dd6b20'
            bg_color = '#fffaf0'
            border_color = '#fbd38d'
            header_title = 'Plazo Proximo'
            header_subtitle = f'Vence en {days_remaining} dias'
            intro_message = 'Este plazo esta proximo a vencer:'
            action_message = 'Asegurese de completar las tareas pendientes a tiempo.'
        else:
            header_color = '#2c5282'
            bg_color = '#ebf8ff'
            border_color = '#bee3f8'
            header_title = 'Recordatorio de Plazo'
            header_subtitle = f'{days_remaining} dias restantes'
            intro_message = 'Le recordamos el siguiente plazo pendiente:'
            action_message = 'Planifique sus actividades para cumplir con este plazo.'

        # Preparar informacion del caso
        case_info = ''
        if deadline.case_number:
            case_info = f'<div class="detail-row"><strong>Caso:</strong> {deadline.case_number}</div>'

        # Formatear el HTML
        html_content = DEADLINE_REMINDER_TEMPLATE.format(
            header_color=header_color,
            bg_color=bg_color,
            border_color=border_color,
            header_title=header_title,
            header_subtitle=header_subtitle,
            user_name=user_info.get('name', 'Usuario'),
            intro_message=intro_message,
            deadline_title=deadline.title,
            due_date=deadline.due_date.strftime('%d/%m/%Y'),
            days_remaining=f"{days_remaining} dias" if days_remaining >= 0 else f"Vencido hace {abs(days_remaining)} dias",
            priority=deadline.get_priority_display(),
            priority_color=get_priority_color(deadline.priority),
            case_info=case_info,
            description=deadline.description or 'Sin descripcion',
            action_message=action_message
        )

        if is_overdue:
            subject = f"VENCIDO: {deadline.title} - Accion requerida"
        else:
            subject = f"Plazo: {deadline.title} - Vence {deadline.due_date.strftime('%d/%m/%Y')}"

        results = {
            'deadline_id': str(deadline.id),
            'user_id': user_info.get('id'),
            'email_sent': False,
            'portal_sent': False
        }

        # Enviar email si hay direccion
        if user_info.get('email'):
            results['email_sent'] = send_email_notification(
                user_info['email'],
                subject,
                html_content
            )

        # Enviar notificacion al portal
        urgency = "VENCIDO" if is_overdue else f"{days_remaining} dias restantes"
        results['portal_sent'] = send_portal_notification(
            recipient_id=str(user_info.get('id', '')),
            recipient_name=user_info.get('name', 'Usuario'),
            subject=subject,
            content=f"Plazo: {deadline.title}\nVencimiento: {deadline.due_date.strftime('%d/%m/%Y')}\nEstado: {urgency}\nPrioridad: {deadline.get_priority_display()}",
            case_id=str(deadline.case_id) if deadline.case_id else None,
            case_number=deadline.case_number
        )

        return results

    except Exception as e:
        logger.error(f"Error enviando recordatorio de plazo: {str(e)}")
        return {'error': str(e)}


def process_event_reminders() -> Dict[str, Any]:
    """
    Procesa y envia recordatorios de eventos proximos.

    Busca eventos con recordatorios configurados y envia notificaciones
    a los asistentes segun los tiempos especificados.

    Returns:
        dict: Resumen de notificaciones enviadas
    """
    now = timezone.now()
    results = {
        'events_processed': 0,
        'notifications_sent': 0,
        'errors': []
    }

    try:
        # Buscar eventos en las proximas 24 horas con recordatorios
        upcoming_events = Event.objects.filter(
            status__in=['scheduled', 'confirmed'],
            start_datetime__gte=now,
            start_datetime__lte=now + timedelta(hours=24)
        )

        for event in upcoming_events:
            if not event.reminder_minutes:
                continue

            minutes_until_event = (event.start_datetime - now).total_seconds() / 60

            for reminder_minutes in event.reminder_minutes:
                # Verificar si es momento de enviar este recordatorio
                if reminder_minutes - 5 <= minutes_until_event <= reminder_minutes + 5:
                    # Enviar a todos los asistentes
                    for attendee_id in event.attendees:
                        # En produccion, obtendriamos la info del usuario del IAM service
                        user_info = {
                            'id': attendee_id,
                            'name': 'Usuario',
                            'email': None  # Se obtendria del servicio IAM
                        }
                        result = send_event_reminder(event, user_info)
                        if 'error' not in result:
                            results['notifications_sent'] += 1
                        else:
                            results['errors'].append(result['error'])

            results['events_processed'] += 1

    except Exception as e:
        results['errors'].append(str(e))
        logger.error(f"Error procesando recordatorios de eventos: {str(e)}")

    return results


def process_deadline_reminders() -> Dict[str, Any]:
    """
    Procesa y envia recordatorios de plazos.

    Busca plazos pendientes y envia notificaciones a los usuarios
    asignados segun la proximidad del vencimiento.

    Returns:
        dict: Resumen de notificaciones enviadas
    """
    today = date.today()
    results = {
        'deadlines_processed': 0,
        'notifications_sent': 0,
        'errors': []
    }

    try:
        # Buscar plazos pendientes en los proximos 7 dias o vencidos
        pending_deadlines = Deadline.objects.filter(
            status='pending',
            due_date__lte=today + timedelta(days=7)
        )

        for deadline in pending_deadlines:
            days_remaining = deadline.days_remaining

            # Determinar si debemos enviar notificacion
            should_notify = False
            is_overdue = days_remaining < 0

            # Notificar si: vencido, vence hoy, 1 dia, 3 dias, o 7 dias
            if is_overdue:
                should_notify = True
            elif days_remaining in [0, 1, 3, 7]:
                should_notify = True

            if should_notify and deadline.assigned_to_id:
                # En produccion, obtendriamos la info del usuario del IAM service
                user_info = {
                    'id': str(deadline.assigned_to_id),
                    'name': deadline.assigned_to_name or 'Usuario',
                    'email': None  # Se obtendria del servicio IAM
                }

                result = send_deadline_reminder(deadline, user_info, is_overdue)

                if 'error' not in result:
                    results['notifications_sent'] += 1
                    # Actualizar fecha de ultimo recordatorio
                    deadline.last_reminder_sent = today
                    deadline.save(update_fields=['last_reminder_sent'])
                else:
                    results['errors'].append(result['error'])

            results['deadlines_processed'] += 1

    except Exception as e:
        results['errors'].append(str(e))
        logger.error(f"Error procesando recordatorios de plazos: {str(e)}")

    return results


def check_and_update_overdue_deadlines() -> Dict[str, Any]:
    """
    Verifica y actualiza el estado de plazos vencidos.

    Busca plazos pendientes con fecha pasada y actualiza su estado
    a 'missed' (vencido).

    Returns:
        dict: Resumen de plazos actualizados
    """
    today = date.today()
    results = {
        'checked': 0,
        'updated_to_missed': 0,
        'errors': []
    }

    try:
        # Buscar plazos pendientes con fecha de vencimiento pasada
        overdue_deadlines = Deadline.objects.filter(
            status='pending',
            due_date__lt=today
        )

        results['checked'] = overdue_deadlines.count()

        for deadline in overdue_deadlines:
            try:
                deadline.status = 'missed'
                deadline.save(update_fields=['status', 'updated_at'])
                results['updated_to_missed'] += 1

                # Enviar notificacion de plazo vencido
                if deadline.assigned_to_id:
                    user_info = {
                        'id': str(deadline.assigned_to_id),
                        'name': deadline.assigned_to_name or 'Usuario',
                        'email': None
                    }
                    send_deadline_reminder(deadline, user_info, is_overdue=True)

            except Exception as e:
                results['errors'].append(f"Error actualizando plazo {deadline.id}: {str(e)}")

    except Exception as e:
        results['errors'].append(str(e))
        logger.error(f"Error verificando plazos vencidos: {str(e)}")

    return results
