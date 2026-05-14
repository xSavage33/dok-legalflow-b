"""
Modulo de Notificaciones para Document Service

Este modulo proporciona funciones para enviar notificaciones a traves
del notification_worker de Celery cuando se comparten documentos.
"""

import os
from celery import Celery

# Configurar conexion a Celery usando la misma configuracion que notification_worker
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/9')

# Crear instancia de Celery para enviar tareas
celery_app = Celery('notifications', broker=CELERY_BROKER_URL)


def send_document_shared_notification(document, shared_with_email, shared_with_name, permission):
    """
    Envia notificacion cuando se comparte un documento.

    Args:
        document: Instancia del modelo Document
        shared_with_email: Email del usuario con quien se comparte
        shared_with_name: Nombre del usuario con quien se comparte
        permission: Tipo de permiso ('view', 'edit', 'download')
    """
    if not shared_with_email:
        return

    # Mapeo de permisos a texto legible
    permission_display = {
        'view': 'ver',
        'edit': 'editar',
        'download': 'descargar',
    }
    permission_text = permission_display.get(permission, permission)

    try:
        celery_app.send_task(
            'send_document_shared_notification',
            kwargs={
                'document_name': document.name,
                'recipient_email': shared_with_email,
                'recipient_name': shared_with_name or shared_with_email.split('@')[0],
                'shared_by_name': document.created_by_name or 'Un usuario',
                'permission': permission_text,
            }
        )
    except Exception as e:
        # No fallar la operacion si la notificacion falla
        print(f"Error enviando notificacion de documento compartido: {str(e)}")


def send_new_document_notification(document, case_number=None, client_email=None, client_name=None):
    """
    Envia notificacion cuando se sube un nuevo documento a un caso.

    Args:
        document: Instancia del modelo Document
        case_number: Numero del caso asociado (opcional)
        client_email: Email del cliente (opcional)
        client_name: Nombre del cliente (opcional)
    """
    if not client_email:
        return

    try:
        celery_app.send_task(
            'send_case_update',
            kwargs={
                'case_number': case_number or 'N/A',
                'client_email': client_email,
                'client_name': client_name or client_email.split('@')[0],
                'update_type': 'Nuevo Documento',
                'update_message': f'Se ha subido un nuevo documento "{document.name}" a su caso.',
            }
        )
    except Exception as e:
        print(f"Error enviando notificacion de nuevo documento: {str(e)}")
