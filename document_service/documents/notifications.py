"""
Modulo de Notificaciones para Document Service

Este modulo proporciona funciones para enviar notificaciones a traves
del notification_worker de Celery cuando se comparten documentos.
"""

import os
import logging
import requests
from celery import Celery

logger = logging.getLogger(__name__)

# Configurar conexion a Celery usando la misma configuracion que notification_worker
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/9')

# URL del matter service para obtener info del caso
MATTER_SERVICE_URL = os.environ.get('MATTER_SERVICE_URL', 'http://matter-service:8000')
INTERNAL_SERVICE_TOKEN = os.environ.get('INTERNAL_SERVICE_TOKEN', '')

# Crear instancia de Celery para enviar tareas
celery_app = Celery('notifications', broker=CELERY_BROKER_URL)


def get_case_info(case_id):
    """
    Obtiene la informacion de un caso desde matter_service.

    Args:
        case_id: UUID del caso

    Returns:
        dict: Informacion del caso o None si falla
    """
    if not case_id:
        return None

    try:
        headers = {
            'Content-Type': 'application/json',
            'X-Service-Token': INTERNAL_SERVICE_TOKEN,
        }
        response = requests.get(
            f"{MATTER_SERVICE_URL}/api/cases/{case_id}/",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error obteniendo info del caso {case_id}: {str(e)}")

    return None


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


def send_new_document_notification(document):
    """
    Envia notificacion cuando se sube un nuevo documento a un caso.

    Busca la informacion del caso desde matter_service y envia
    la notificacion al cliente asociado.

    Args:
        document: Instancia del modelo Document
    """
    if not document.case_id:
        return

    # Obtener info del caso
    case_info = get_case_info(document.case_id)
    if not case_info:
        logger.warning(f"No se pudo obtener info del caso {document.case_id} para notificar")
        return

    client_email = case_info.get('client_email')
    client_name = case_info.get('client_name')
    case_number = case_info.get('case_number')

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
        logger.info(f"Notificacion de documento enviada a {client_email}")
    except Exception as e:
        logger.error(f"Error enviando notificacion de nuevo documento: {str(e)}")
