"""
Cliente HTTP para comunicacion con microservicios en LegalFlow.

Este archivo implementa un cliente HTTP reutilizable que maneja la comunicacion
entre el API Gateway y los microservicios backend. Proporciona metodos tanto
sincronos como asincronos para reenviar peticiones, con manejo robusto de
errores, timeouts y logging.

Caracteristicas principales:
    - Cliente HTTP asincrono usando httpx para alto rendimiento
    - Version sincrona para compatibilidad con codigo no-async
    - Manejo automatico de headers (Host, Authorization, Content-Type)
    - Soporte para todos los metodos HTTP (GET, POST, PUT, PATCH, DELETE)
    - Soporte para envio de archivos multipart
    - Verificacion de permisos via servicio IAM
    - Manejo de errores con logging detallado

Clases:
    - ServiceClient: Cliente principal para comunicacion con microservicios

Instancia global:
    - service_client: Instancia pre-configurada lista para usar

Autor: LegalFlow Team
"""

# Importacion de la biblioteca httpx para peticiones HTTP asincronas y sincronas
# httpx es una alternativa moderna a requests con soporte nativo para async
import httpx

# Importacion del modulo logging para registro de eventos y errores
# Permite rastrear problemas de conexion con microservicios
import logging

# Importacion del modulo settings de Django para acceder a configuracion
# Contiene las URLs de los microservicios y otras configuraciones
from django.conf import settings

# Configuracion del logger para este modulo
# __name__ crea un logger con el nombre del modulo actual (gateway.service_client)
logger = logging.getLogger(__name__)


class ServiceClient:
    """
    Cliente HTTP para comunicacion con microservicios.

    Esta clase encapsula toda la logica necesaria para enviar peticiones
    HTTP a los diferentes microservicios del sistema LegalFlow. Maneja
    automaticamente la construccion de URLs, headers y el manejo de errores.

    Atributos:
        timeout (float): Tiempo maximo de espera para peticiones en segundos
        service_urls (dict): Diccionario con URLs base de cada microservicio

    Metodos principales:
        - forward_request: Reenvia peticiones de forma asincrona
        - forward_request_sync: Reenvia peticiones de forma sincrona
        - check_permission: Verifica permisos de usuario via IAM

    Ejemplo de uso:
        client = ServiceClient(timeout=30.0)
        response, error = client.forward_request_sync(
            'matter',
            '/api/cases/',
            'GET',
            headers={'Authorization': 'Bearer token123'}
        )
    """

    def __init__(self, timeout=30.0):
        """
        Inicializa el cliente de servicios con configuracion base.

        Args:
            timeout (float): Tiempo maximo de espera en segundos para peticiones.
                           Por defecto es 30 segundos para operaciones largas.
        """
        # Almacena el timeout configurado para usar en todas las peticiones
        self.timeout = timeout

        # Obtiene el diccionario de URLs de servicios desde la configuracion de Django
        # Ejemplo: {'matter': 'http://matter-service:8000', 'billing': 'http://billing-service:8001'}
        self.service_urls = settings.SERVICE_URLS

    def get_service_url(self, service_name):
        """
        Obtiene la URL base de un microservicio por su nombre.

        Busca en el diccionario de URLs configurado la URL correspondiente
        al nombre del servicio especificado.

        Args:
            service_name (str): Nombre identificador del servicio
                              (ej: 'matter', 'billing', 'iam')

        Returns:
            str or None: URL base del servicio si existe, None si no se encuentra
        """
        # Retorna la URL del servicio o None si no existe en la configuracion
        return self.service_urls.get(service_name)

    async def forward_request(self, service_name, path, method, headers=None, data=None, params=None, files=None):
        """
        Reenvia una peticion HTTP a un microservicio de forma asincrona.

        Este metodo asincrono es ideal para uso con frameworks async como
        FastAPI o vistas async de Django. Proporciona mejor rendimiento
        al no bloquear el event loop durante peticiones de red.

        Args:
            service_name (str): Nombre del microservicio destino
            path (str): Ruta del endpoint (ej: '/api/cases/')
            method (str): Metodo HTTP (GET, POST, PUT, PATCH, DELETE)
            headers (dict, optional): Headers HTTP a incluir
            data (dict, optional): Datos del cuerpo de la peticion
            params (dict, optional): Parametros de query string
            files (dict, optional): Archivos para envio multipart

        Returns:
            tuple: (response, error) donde response es el objeto httpx.Response
                   si fue exitoso, o (None, mensaje_error) si fallo
        """
        # Obtiene la URL base del servicio desde la configuracion
        base_url = self.get_service_url(service_name)

        # Verifica que el servicio este configurado
        if not base_url:
            return None, f'Unknown service: {service_name}'

        # Construye la URL completa concatenando base y path
        url = f"{base_url}{path}"

        # Prepara headers limpios - NO establecer Host manualmente
        # httpx establecera el Host correcto basado en la URL
        forward_headers = {}

        # Copia headers proporcionados, excluyendo los que httpx maneja automaticamente
        if headers:
            for key, value in headers.items():
                # Convierte la clave a minusculas para comparacion case-insensitive
                key_lower = key.lower()

                # Excluye headers que podrian causar conflictos
                # host: ya se establece manualmente
                # content-length: httpx lo calcula automaticamente
                # transfer-encoding: httpx lo maneja segun el contenido
                if key_lower not in ['host', 'content-length', 'transfer-encoding']:
                    forward_headers[key] = value

        try:
            # Crea un cliente httpx asincrono con el timeout configurado
            # El context manager (async with) asegura que se cierre correctamente
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Ejecuta la peticion segun el metodo HTTP especificado
                if method == 'GET':
                    # Peticion GET con parametros de query string opcionales
                    response = await client.get(url, headers=forward_headers, params=params)

                elif method == 'POST':
                    # Peticion POST: con archivos usa multipart, sino JSON
                    if files:
                        # Envio multipart para formularios con archivos
                        response = await client.post(url, headers=forward_headers, data=data, files=files)
                    else:
                        # Envio JSON para datos estructurados
                        response = await client.post(url, headers=forward_headers, json=data)

                elif method == 'PUT':
                    # Peticion PUT para actualizaciones completas de recursos
                    response = await client.put(url, headers=forward_headers, json=data)

                elif method == 'PATCH':
                    # Peticion PATCH para actualizaciones parciales de recursos
                    response = await client.patch(url, headers=forward_headers, json=data)

                elif method == 'DELETE':
                    # Peticion DELETE para eliminar recursos
                    response = await client.delete(url, headers=forward_headers)

                else:
                    # Metodo HTTP no soportado
                    return None, f'Unsupported method: {method}'

                # Retorna la respuesta exitosa sin error
                return response, None

        except httpx.TimeoutException:
            # Error de timeout: el servicio no respondio a tiempo
            logger.error(f"Timeout connecting to {service_name} at {url}")
            return None, 'Service timeout'

        except httpx.ConnectError:
            # Error de conexion: no se pudo establecer conexion con el servicio
            logger.error(f"Connection error to {service_name} at {url}")
            return None, 'Service unavailable'

        except Exception as e:
            # Captura cualquier otro error inesperado
            logger.error(f"Error forwarding to {service_name}: {str(e)}")
            return None, str(e)

    def forward_request_sync(self, service_name, path, method, headers=None, data=None, params=None, files=None):
        """
        Reenvia una peticion HTTP a un microservicio de forma sincrona.

        Version sincrona del metodo forward_request para uso en contextos
        que no soportan async/await, como vistas tradicionales de Django
        o middleware.

        Args:
            service_name (str): Nombre del microservicio destino
            path (str): Ruta del endpoint (ej: '/api/cases/')
            method (str): Metodo HTTP (GET, POST, PUT, PATCH, DELETE)
            headers (dict, optional): Headers HTTP a incluir
            data (dict, optional): Datos del cuerpo de la peticion
            params (dict, optional): Parametros de query string
            files (dict, optional): Archivos para envio multipart

        Returns:
            tuple: (response, error) donde response es el objeto httpx.Response
                   si fue exitoso, o (None, mensaje_error) si fallo
        """
        # Obtiene la URL base del servicio desde la configuracion
        base_url = self.get_service_url(service_name)

        # Verifica que el servicio este configurado
        if not base_url:
            return None, f'Unknown service: {service_name}'

        # Construye la URL completa concatenando base y path
        url = f"{base_url}{path}"

        # Prepara headers limpios - NO establecer Host manualmente
        # httpx establecera el Host correcto basado en la URL
        forward_headers = {}

        # Copia headers proporcionados con filtrado especial
        if headers:
            for key, value in headers.items():
                # Convierte la clave a minusculas para comparacion
                key_lower = key.lower()

                # Excluye headers que httpx maneja automaticamente
                if key_lower not in ['host', 'content-length', 'transfer-encoding']:
                    # Excluye Content-Type cuando hay archivos
                    # httpx establece el boundary correcto para multipart
                    if files and key_lower == 'content-type':
                        continue
                    forward_headers[key] = value

        try:
            # Crea un cliente httpx sincrono con el timeout configurado
            # El context manager (with) asegura que se cierre correctamente
            with httpx.Client(timeout=self.timeout) as client:
                # Ejecuta la peticion segun el metodo HTTP especificado
                if method == 'GET':
                    # Peticion GET con parametros de query string opcionales
                    response = client.get(url, headers=forward_headers, params=params)

                elif method == 'POST':
                    # Peticion POST: con archivos usa multipart, sino JSON
                    if files:
                        # Envio multipart para formularios con archivos
                        response = client.post(url, headers=forward_headers, data=data, files=files)
                    else:
                        # Envio JSON para datos estructurados
                        response = client.post(url, headers=forward_headers, json=data)

                elif method == 'PUT':
                    # Peticion PUT: soporta archivos para actualizaciones de documentos
                    if files:
                        response = client.put(url, headers=forward_headers, data=data, files=files)
                    else:
                        response = client.put(url, headers=forward_headers, json=data)

                elif method == 'PATCH':
                    # Peticion PATCH: soporta archivos para actualizaciones parciales
                    if files:
                        response = client.patch(url, headers=forward_headers, data=data, files=files)
                    else:
                        response = client.patch(url, headers=forward_headers, json=data)

                elif method == 'DELETE':
                    # Peticion DELETE para eliminar recursos
                    response = client.delete(url, headers=forward_headers)

                else:
                    # Metodo HTTP no soportado
                    return None, f'Unsupported method: {method}'

                # Retorna la respuesta exitosa sin error
                return response, None

        except httpx.TimeoutException:
            # Error de timeout: el servicio no respondio a tiempo
            logger.error(f"Timeout connecting to {service_name} at {url}")
            return None, 'Service timeout'

        except httpx.ConnectError:
            # Error de conexion: no se pudo establecer conexion con el servicio
            logger.error(f"Connection error to {service_name} at {url}")
            return None, 'Service unavailable'

        except Exception as e:
            # Captura cualquier otro error inesperado
            logger.error(f"Error forwarding to {service_name}: {str(e)}")
            return None, str(e)

    def check_permission(self, user_id, permission_codename, object_type=None, object_id=None):
        """
        Verifica si un usuario tiene un permiso especifico via el servicio IAM.

        Este metodo consulta el servicio de Identity and Access Management (IAM)
        para verificar si el usuario tiene el permiso solicitado, opcionalmente
        sobre un objeto especifico.

        Args:
            user_id (str/UUID): Identificador unico del usuario
            permission_codename (str): Codigo del permiso a verificar
                                      (ej: 'view_case', 'edit_invoice')
            object_type (str, optional): Tipo de objeto para permisos a nivel objeto
                                        (ej: 'case', 'document')
            object_id (str/UUID, optional): ID del objeto especifico

        Returns:
            bool: True si el usuario tiene el permiso, False en caso contrario
                  o si ocurre un error de comunicacion

        Ejemplo:
            # Verificar permiso global
            puede_ver = client.check_permission(user_id, 'view_analytics')

            # Verificar permiso sobre objeto especifico
            puede_editar = client.check_permission(
                user_id, 'edit_case',
                object_type='case', object_id=case_id
            )
        """
        # Construye el diccionario de datos para la peticion al IAM
        data = {
            'user_id': str(user_id),                    # Convierte UUID a string
            'permission_codename': permission_codename  # Codigo del permiso
        }

        # Agrega tipo de objeto si se especifica (permisos a nivel objeto)
        if object_type:
            data['object_type'] = object_type

        # Agrega ID de objeto si se especifica
        if object_id:
            data['object_id'] = str(object_id)

        # Realiza peticion POST al endpoint de verificacion de permisos del IAM
        response, error = self.forward_request_sync(
            'iam',                           # Nombre del servicio IAM
            '/api/iam/check-permission/',    # Endpoint de verificacion
            'POST',                          # Metodo HTTP
            data=data                        # Datos de la peticion
        )

        # Si hubo error de comunicacion, deniega el permiso por seguridad
        if error:
            return False

        try:
            # Intenta obtener el resultado de la respuesta JSON
            # El IAM retorna {'has_permission': True/False}
            return response.json().get('has_permission', False)
        except Exception:
            # Si hay error parseando la respuesta, deniega por seguridad
            return False


# Instancia global del cliente de servicios pre-configurada
# Permite importar y usar directamente: from .service_client import service_client
service_client = ServiceClient()
