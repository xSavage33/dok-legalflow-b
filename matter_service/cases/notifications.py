"""
Modulo de Notificaciones para Matter Service

Este modulo proporciona funciones para enviar notificaciones a traves
del notification_worker de Celery. Las notificaciones se envian de forma
asincrona para no bloquear las operaciones del servicio.
"""

import os
from celery import Celery

# Configurar conexion a Celery usando la misma configuracion que notification_worker
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/9')

# Crear instancia de Celery para enviar tareas
celery_app = Celery('notifications', broker=CELERY_BROKER_URL)


def send_case_created_notification(case):
    """
    Envia notificacion cuando se crea un nuevo caso.

    Notifica al cliente que se ha creado un caso a su nombre.

    Args:
        case: Instancia del modelo Case
    """
    if not case.client_email:
        return

    try:
        celery_app.send_task(
            'send_case_update',
            kwargs={
                'case_number': case.case_number,
                'client_email': case.client_email,
                'client_name': case.client_name,
                'update_type': 'Nuevo Caso',
                'update_message': f'Se ha creado el caso "{case.title}" a su nombre. Tipo: {case.get_case_type_display()}.',
            }
        )
    except Exception as e:
        # No fallar la operacion si la notificacion falla
        print(f"Error enviando notificacion de caso creado: {str(e)}")


def send_case_status_changed_notification(case, old_status, new_status):
    """
    Envia notificacion cuando cambia el estado de un caso.

    Args:
        case: Instancia del modelo Case
        old_status: Estado anterior del caso
        new_status: Nuevo estado del caso
    """
    if not case.client_email:
        return

    # Mapeo de estados a texto legible
    status_display = {
        'active': 'Activo',
        'pending': 'Pendiente',
        'on_hold': 'En Espera',
        'on_appeal': 'En Apelacion',
        'closed': 'Cerrado',
        'archived': 'Archivado',
    }

    new_status_text = status_display.get(new_status, new_status)

    try:
        celery_app.send_task(
            'send_case_update',
            kwargs={
                'case_number': case.case_number,
                'client_email': case.client_email,
                'client_name': case.client_name,
                'update_type': 'Cambio de Estado',
                'update_message': f'El estado de su caso ha cambiado a: {new_status_text}.',
            }
        )
    except Exception as e:
        print(f"Error enviando notificacion de cambio de estado: {str(e)}")


def send_case_updated_notification(case, update_description):
    """
    Envia notificacion generica de actualizacion de caso.

    Args:
        case: Instancia del modelo Case
        update_description: Descripcion de la actualizacion
    """
    if not case.client_email:
        return

    try:
        celery_app.send_task(
            'send_case_update',
            kwargs={
                'case_number': case.case_number,
                'client_email': case.client_email,
                'client_name': case.client_name,
                'update_type': 'Actualizacion',
                'update_message': update_description,
            }
        )
    except Exception as e:
        print(f"Error enviando notificacion de actualizacion: {str(e)}")
