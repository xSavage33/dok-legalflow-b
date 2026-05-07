"""
iam_client.py - Cliente para comunicacion con el IAM Service

Este modulo proporciona funciones para verificar permisos de usuarios
consultando el servicio de Identity and Access Management (IAM).

Implementa:
- Verificacion de permisos a nivel de recurso
- Cache de permisos para reducir latencia
- Manejo de errores y fallbacks

Autor: Equipo de Desarrollo LegalFlow
"""

import logging
from typing import Optional
from functools import lru_cache

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

# Tiempo de cache para permisos (5 minutos)
PERMISSION_CACHE_TTL = 300


def get_iam_service_url() -> str:
    """
    Obtiene la URL del servicio IAM desde la configuracion.

    Returns:
        str: URL base del servicio IAM
    """
    return getattr(settings, 'IAM_SERVICE_URL', 'http://localhost:8001')


def check_permission(
    user_id: str,
    permission_codename: str,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None
) -> bool:
    """
    Verifica si un usuario tiene un permiso especifico.

    Consulta al IAM Service para verificar si el usuario tiene
    el permiso solicitado, opcionalmente a nivel de objeto.

    Args:
        user_id: UUID del usuario
        permission_codename: Codigo del permiso (ej: 'document.view')
        object_type: Tipo de objeto (ej: 'document', 'case')
        object_id: UUID del objeto especifico

    Returns:
        bool: True si el usuario tiene el permiso, False si no

    Raises:
        PermissionDenied: Si no se puede verificar y se debe denegar acceso
    """
    # Construir clave de cache
    cache_key = f"perm:{user_id}:{permission_codename}"
    if object_type and object_id:
        cache_key += f":{object_type}:{object_id}"

    # Verificar cache primero
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    try:
        # Construir la peticion al IAM Service
        iam_url = get_iam_service_url()
        url = f"{iam_url}/api/iam/check-permission/"

        payload = {
            'user_id': str(user_id),
            'permission_codename': permission_codename,
        }

        if object_type:
            payload['object_type'] = object_type
        if object_id:
            payload['object_id'] = str(object_id)

        # Realizar la peticion
        response = requests.post(
            url,
            json=payload,
            timeout=5,  # 5 segundos de timeout
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            result = response.json()
            has_permission = result.get('has_permission', False)

            # Guardar en cache
            cache.set(cache_key, has_permission, PERMISSION_CACHE_TTL)

            return has_permission
        else:
            logger.warning(
                f"IAM Service retorno status {response.status_code} "
                f"para user={user_id}, permission={permission_codename}"
            )
            # En caso de error, denegar por seguridad
            return False

    except requests.exceptions.Timeout:
        logger.error("Timeout al consultar IAM Service")
        # En caso de timeout, permitir temporalmente para no bloquear
        # En produccion, considerar una politica mas estricta
        return True

    except requests.exceptions.ConnectionError:
        logger.error("No se puede conectar al IAM Service")
        # Si no hay conexion, usar permisos del token JWT como fallback
        return True

    except Exception as e:
        logger.error(f"Error al verificar permisos: {str(e)}")
        return False


def check_document_permission(
    user,
    document,
    action: str = 'view'
) -> bool:
    """
    Verifica si un usuario puede realizar una accion sobre un documento.

    Esta funcion es un wrapper de alto nivel que verifica:
    1. Permisos globales del usuario (basados en rol)
    2. Permisos especificos del documento
    3. Permisos a nivel de caso (si el documento pertenece a un caso)

    Args:
        user: Objeto de usuario autenticado (con id, email, role)
        document: Instancia del documento a verificar
        action: Accion a realizar ('view', 'download', 'edit', 'delete')

    Returns:
        bool: True si el usuario tiene permiso, False si no
    """
    # Mapear acciones a codenames de permisos
    action_to_permission = {
        'view': 'document.view',
        'download': 'document.download',
        'edit': 'document.edit',
        'delete': 'document.delete',
        'upload': 'document.create',
    }

    permission_codename = action_to_permission.get(action, 'document.view')

    # Los administradores y socios tienen acceso completo
    if hasattr(user, 'role') and user.role in ['admin', 'partner']:
        return True

    # Verificar permiso global primero
    has_global_permission = check_permission(
        user_id=str(user.id),
        permission_codename=permission_codename
    )

    if not has_global_permission:
        return False

    # Verificar permiso especifico del documento
    has_object_permission = check_permission(
        user_id=str(user.id),
        permission_codename=permission_codename,
        object_type='document',
        object_id=str(document.id)
    )

    if has_object_permission:
        return True

    # Si el documento pertenece a un caso, verificar permiso del caso
    if document.case_id:
        has_case_permission = check_permission(
            user_id=str(user.id),
            permission_codename='case.view',
            object_type='case',
            object_id=str(document.case_id)
        )
        if has_case_permission:
            return True

    # Si el usuario creo el documento, tiene permiso de ver
    if str(document.created_by_id) == str(user.id):
        return True

    return False


def require_document_permission(action: str = 'view'):
    """
    Decorador para requerir permisos de documento en vistas.

    Uso:
        @require_document_permission('download')
        def get(self, request, id):
            ...

    Args:
        action: Accion requerida ('view', 'download', 'edit', 'delete')

    Returns:
        Decorator function
    """
    def decorator(view_method):
        def wrapper(self, request, *args, **kwargs):
            # Obtener el documento
            document = self.get_object()

            # Verificar permiso
            if not check_document_permission(request.user, document, action):
                raise PermissionDenied(
                    f"No tiene permiso para {action} este documento"
                )

            return view_method(self, request, *args, **kwargs)
        return wrapper
    return decorator


def clear_permission_cache(user_id: str = None):
    """
    Limpia la cache de permisos.

    Args:
        user_id: Si se especifica, solo limpia cache de ese usuario.
                 Si es None, limpia toda la cache de permisos.
    """
    if user_id:
        # Limpiar solo permisos de un usuario especifico
        # Nota: Esto requiere Redis con soporte de patrones
        pattern = f"perm:{user_id}:*"
        try:
            keys = cache.keys(pattern)
            for key in keys:
                cache.delete(key)
        except AttributeError:
            # Si el backend de cache no soporta keys(), no hacer nada
            pass
    else:
        # En este caso, seria necesario implementar una logica mas compleja
        # o usar un backend de cache que soporte flush selectivo
        pass
