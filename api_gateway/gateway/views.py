"""
Vistas del API Gateway para LegalFlow.

Este archivo contiene las vistas proxy que reenvian peticiones desde el
API Gateway hacia los diferentes microservicios backend. El gateway actua
como punto de entrada unico para todas las peticiones del frontend,
proporcionando:

    - Autenticacion centralizada via JWT
    - Enrutamiento inteligente a microservicios
    - Verificacion de salud de servicios
    - Transformacion de peticiones y respuestas

Vistas incluidas:
    - HealthCheckView: Verificacion de salud del gateway y servicios
    - ProxyView: Clase base para vistas proxy
    - IAMProxyView: Proxy para el servicio de autenticacion
    - SimpleProxyView: Proxy generico que mantiene la ruta original
    - MatterProxyView: Proxy para el servicio de gestion de casos
    - DocumentProxyView: Proxy para el servicio de documentos
    - TimeTrackingProxyView: Proxy para el servicio de tiempo
    - BillingProxyView: Proxy para el servicio de facturacion
    - CalendarProxyView: Proxy para el servicio de calendario
    - PortalProxyView: Proxy para el portal de clientes
    - AnalyticsProxyView: Proxy para el servicio de analiticas

Arquitectura:
    Frontend -> API Gateway -> Microservicio correspondiente

Autor: LegalFlow Team
"""

# Importacion del modulo json para serializacion/deserializacion JSON
# Usado para procesar cuerpos de peticiones
import json

# Importacion de la clase base APIView de Django REST Framework
# Proporciona manejo automatico de metodos HTTP y negociacion de contenido
from rest_framework.views import APIView

# Importacion de la clase Response de Django REST Framework
# Permite crear respuestas HTTP con serializacion automatica
from rest_framework.response import Response

# Importacion del modulo status con codigos HTTP estandar
# Proporciona constantes como HTTP_401_UNAUTHORIZED, HTTP_503_SERVICE_UNAVAILABLE
from rest_framework import status

# Importacion de JsonResponse para respuestas JSON nativas de Django
# Usado cuando no se necesita la funcionalidad completa de DRF Response
from django.http import JsonResponse, HttpResponse

# Importacion del modulo settings de Django para configuracion
# Contiene URLs de servicios y otras configuraciones
from django.conf import settings

# Importacion de la funcion utilitaria para extraer usuario del token JWT
# Valida el token y retorna informacion del usuario autenticado
from .jwt_utils import get_user_from_token

# Importacion de la instancia global del cliente de servicios
# Maneja la comunicacion HTTP con los microservicios backend
from .service_client import service_client


class HealthCheckView(APIView):
    """
    Endpoint de verificacion de salud del API Gateway.

    Proporciona informacion sobre el estado del gateway y la conectividad
    con todos los microservicios backend. Util para monitoreo, balanceadores
    de carga y herramientas de orquestacion como Kubernetes.

    Endpoints:
        GET /health/
    """
    # Deshabilita autenticacion/permisos para health check
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        Verifica la salud del gateway y todos los servicios conectados.

        Itera sobre todos los microservicios configurados y verifica
        la conectividad enviando peticiones a sus endpoints de salud.

        Args:
            request: Objeto de solicitud HTTP (no usado directamente)

        Returns:
            Response: JSON con estado del gateway y cada microservicio
        """
        # Diccionario para almacenar el estado de cada servicio
        services_status = {}

        # Itera sobre todos los servicios configurados en settings.SERVICE_URLS
        for service_name, url in settings.SERVICE_URLS.items():
            # Intenta conectar al endpoint de salud de cada servicio
            response, error = service_client.forward_request_sync(
                service_name,     # Nombre del servicio (ej: 'iam', 'matter')
                '/health/',       # Endpoint estandar de health check
                'GET'             # Metodo HTTP
            )

            # Determina el estado basado en si hubo error o no
            if error:
                # Servicio no saludable: registra el error
                services_status[service_name] = {'status': 'unhealthy', 'error': error}
            else:
                # Servicio saludable: conexion exitosa
                services_status[service_name] = {'status': 'healthy'}

        # Retorna respuesta con estado general y detalle por servicio
        return Response({
            'service': 'api_gateway',        # Identificador del servicio
            'status': 'healthy',             # Estado del gateway (siempre healthy si responde)
            'services': services_status      # Estado de cada microservicio
        })


class ProxyView(APIView):
    """
    Vista base para proxies de microservicios.

    Esta clase abstracta proporciona la funcionalidad comun para todas
    las vistas proxy del gateway. Maneja la extraccion de headers,
    autenticacion JWT y reenvio de peticiones a microservicios.

    Atributos de clase:
        service_name (str): Nombre del microservicio destino (debe sobrescribirse)
        requires_auth (bool): Si requiere autenticacion JWT (default: True)

    Metodos principales:
        - get_headers: Extrae headers relevantes de la peticion
        - forward: Reenvia la peticion al microservicio

    Las clases hijas deben:
        1. Establecer service_name al microservicio correspondiente
        2. Implementar metodos HTTP (get, post, put, patch, delete)
    """

    # Deshabilita autenticacion de DRF (y por tanto CSRF de DRF)
    # El gateway maneja su propia autenticacion JWT
    authentication_classes = []
    permission_classes = []

    # Nombre del microservicio destino (debe sobrescribirse en clases hijas)
    service_name = None

    # Indica si la vista requiere autenticacion JWT
    requires_auth = True

    def get_headers(self, request):
        """
        Extrae y prepara headers HTTP para reenviar al microservicio.

        Selecciona los headers relevantes de la peticion original
        que deben ser reenviados al servicio destino.

        Args:
            request: Objeto de solicitud HTTP de Django

        Returns:
            dict: Diccionario con headers a reenviar
                 (Authorization y Content-Type si existen)
        """
        # Diccionario para almacenar headers a reenviar
        headers = {}

        # Extrae el header de autorizacion (token JWT)
        # HTTP_AUTHORIZATION es como Django almacena el header Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header:
            headers['Authorization'] = auth_header

        # Extrae el header Content-Type para peticiones con cuerpo
        # Necesario para que el microservicio interprete correctamente el body
        content_type = request.META.get('CONTENT_TYPE')
        if content_type:
            headers['Content-Type'] = content_type

        return headers

    def forward(self, request, path):
        """
        Reenvia la peticion HTTP al microservicio destino.

        Maneja todo el proceso de proxy: autenticacion, preparacion
        de datos, envio y transformacion de respuesta.

        Args:
            request: Objeto de solicitud HTTP de Django/DRF
            path: Ruta del endpoint en el microservicio destino

        Returns:
            Response: Respuesta del microservicio o error si falla
        """
        # Verifica autenticacion si es requerida
        if self.requires_auth:
            # Intenta extraer informacion del usuario del token JWT
            user_info, error = get_user_from_token(request)
            if error:
                # Token invalido o ausente: retorna 401 Unauthorized
                return Response({'error': error}, status=status.HTTP_401_UNAUTHORIZED)

        # Extrae headers relevantes de la peticion original
        headers = self.get_headers(request)

        # Obtiene el metodo HTTP de la peticion
        method = request.method

        # Inicializa variables para datos y archivos
        data = None
        files = None

        # Solo procesa cuerpo de peticion para metodos que lo permiten
        if method in ['POST', 'PUT', 'PATCH']:
            # Verifica si la peticion incluye archivos (multipart/form-data)
            if request.FILES:
                # Prepara archivos en formato compatible con httpx
                files = {}
                for key, uploaded_file in request.FILES.items():
                    # Cada archivo se representa como tupla: (nombre, contenido, tipo_mime)
                    files[key] = (
                        uploaded_file.name,         # Nombre original del archivo
                        uploaded_file.read(),       # Contenido binario del archivo
                        uploaded_file.content_type  # Tipo MIME (ej: image/png)
                    )

                # Extrae campos no-archivo del formulario
                data = {}
                # Lista de campos que NO deben ser aplanados (son listas intencionales)
                list_fields = ['items', 'parties', 'tags', 'assigned_attorneys', 'attachments']
                for key, value in request.data.items():
                    # Excluye campos que son archivos
                    if key not in request.FILES:
                        # Maneja valores que vienen como listas
                        if isinstance(value, list):
                            # Solo aplana si NO es un campo de lista y tiene un elemento
                            if len(value) == 1 and key not in list_fields:
                                data[key] = value[0]
                            else:
                                data[key] = value
                        else:
                            data[key] = value
            else:
                # Sin archivos: trata el cuerpo como JSON
                try:
                    # Usa request.data directamente si es un dict normal
                    # Esto preserva la estructura original de los datos JSON
                    if hasattr(request.data, 'dict'):
                        # Es un QueryDict, convertir a dict
                        data = dict(request.data)
                        # Aplana listas de un solo elemento SOLO para campos simples
                        # No aplanar campos que son intencionalmente listas (como 'items')
                        # Lista de campos que NO deben ser aplanados
                        list_fields = ['items', 'parties', 'tags', 'assigned_attorneys', 'attachments']
                        for key, value in data.items():
                            if isinstance(value, list) and len(value) == 1 and key not in list_fields:
                                data[key] = value[0]
                    else:
                        # Ya es un dict normal (JSON parseado), usar directamente
                        data = request.data
                except Exception:
                    # Si falla la conversion, usa diccionario vacio
                    data = {}

        # Extrae parametros de query string si existen
        params = dict(request.query_params) if request.query_params else None

        # Reenvia la peticion al microservicio usando el cliente
        response, error = service_client.forward_request_sync(
            self.service_name,  # Nombre del servicio destino
            path,               # Ruta del endpoint
            method,             # Metodo HTTP
            headers=headers,    # Headers a reenviar
            data=data,          # Datos del cuerpo
            params=params,      # Parametros de query
            files=files         # Archivos adjuntos
        )

        # Maneja errores de comunicacion con el microservicio
        if error:
            # Retorna error 503 Service Unavailable
            return Response(
                {'error': 'Service unavailable', 'detail': error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Procesa y retorna la respuesta del microservicio
        try:
            # Intenta parsear la respuesta como JSON
            response_data = response.json()
            # Retorna respuesta JSON con el codigo de estado original
            return Response(response_data, status=response.status_code)
        except Exception:
            # Si no es JSON, retorna la respuesta raw (ej: archivos binarios)
            return HttpResponse(
                response.content,                                              # Contenido binario
                status=response.status_code,                                   # Codigo de estado
                content_type=response.headers.get('content-type', 'application/octet-stream')
            )


class IAMProxyView(ProxyView):
    """
    Vista proxy para el servicio de Identidad y Gestion de Acceso (IAM).

    Maneja todas las peticiones relacionadas con autenticacion, autorizacion
    y gestion de usuarios. Incluye logica especial para endpoints publicos
    como login y registro que no requieren autenticacion previa.

    Endpoints proxeados:
        - /api/auth/* : Autenticacion (login, logout, refresh)
        - /api/iam/*  : Gestion de usuarios, roles, permisos

    Atributos:
        service_name: 'iam' - Nombre del microservicio IAM
    """

    # Nombre del servicio IAM en la configuracion
    service_name = 'iam'

    def _get_full_path(self, request, path):
        """
        Reconstruye la ruta completa de la API basada en la peticion original.

        El gateway puede recibir peticiones en /api/auth/ o /api/iam/,
        y esta funcion asegura que se reenvie al path correcto del IAM.

        Args:
            request: Objeto de solicitud HTTP con la ruta original
            path: Ruta capturada por el patron de URL

        Returns:
            str: Ruta completa para el microservicio IAM
        """
        # Obtiene la ruta original de la peticion
        original_path = request.path

        # Determina el prefijo correcto basado en la ruta original
        if original_path.startswith('/api/auth/'):
            # Peticiones de autenticacion van a /api/auth/
            return f'/api/auth/{path}'
        elif original_path.startswith('/api/iam/'):
            # Peticiones de IAM van a /api/iam/
            return f'/api/iam/{path}'

        # Fallback: usa /api/ como prefijo
        return f'/api/{path}'

    def get(self, request, path=''):
        """
        Maneja peticiones GET al servicio IAM.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada del patron de URL

        Returns:
            Response: Respuesta del microservicio IAM
        """
        # Reenvia la peticion con la ruta reconstruida
        return self.forward(request, self._get_full_path(request, path))

    def post(self, request, path=''):
        """
        Maneja peticiones POST al servicio IAM.

        Incluye logica especial para endpoints publicos que no
        requieren autenticacion previa (login, registro, tokens).

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada del patron de URL

        Returns:
            Response: Respuesta del microservicio IAM
        """
        # Verifica si es un endpoint publico que no requiere autenticacion
        # login, register y token son endpoints que usuarios no autenticados necesitan
        if path.startswith('login') or path.startswith('register') or path.startswith('token'):
            # Desactiva temporalmente el requerimiento de autenticacion
            self.requires_auth = False

        # Reenvia la peticion al IAM
        return self.forward(request, self._get_full_path(request, path))

    def put(self, request, path=''):
        """
        Maneja peticiones PUT al servicio IAM.

        Usado para actualizaciones completas de recursos (usuarios, roles).

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada del patron de URL

        Returns:
            Response: Respuesta del microservicio IAM
        """
        return self.forward(request, self._get_full_path(request, path))

    def patch(self, request, path=''):
        """
        Maneja peticiones PATCH al servicio IAM.

        Usado para actualizaciones parciales de recursos.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada del patron de URL

        Returns:
            Response: Respuesta del microservicio IAM
        """
        return self.forward(request, self._get_full_path(request, path))

    def delete(self, request, path=''):
        """
        Maneja peticiones DELETE al servicio IAM.

        Usado para eliminar usuarios, roles o permisos.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada del patron de URL

        Returns:
            Response: Respuesta del microservicio IAM
        """
        return self.forward(request, self._get_full_path(request, path))


class SimpleProxyView(ProxyView):
    """
    Vista proxy simple que mantiene la ruta original de la peticion.

    A diferencia de IAMProxyView que reconstruye rutas, esta clase
    reenvia la peticion con la ruta exacta como fue recibida.
    Ideal para microservicios que esperan rutas identicas al gateway.

    Las clases hijas solo necesitan establecer service_name.
    """

    def get(self, request, path=''):
        """
        Maneja peticiones GET manteniendo la ruta original.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada (no usado, se usa request.path)

        Returns:
            Response: Respuesta del microservicio
        """
        # Usa request.path directamente para mantener la ruta completa
        return self.forward(request, request.path)

    def post(self, request, path=''):
        """
        Maneja peticiones POST manteniendo la ruta original.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada (no usado)

        Returns:
            Response: Respuesta del microservicio
        """
        return self.forward(request, request.path)

    def put(self, request, path=''):
        """
        Maneja peticiones PUT manteniendo la ruta original.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada (no usado)

        Returns:
            Response: Respuesta del microservicio
        """
        return self.forward(request, request.path)

    def patch(self, request, path=''):
        """
        Maneja peticiones PATCH manteniendo la ruta original.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada (no usado)

        Returns:
            Response: Respuesta del microservicio
        """
        return self.forward(request, request.path)

    def delete(self, request, path=''):
        """
        Maneja peticiones DELETE manteniendo la ruta original.

        Args:
            request: Objeto de solicitud HTTP
            path: Ruta capturada (no usado)

        Returns:
            Response: Respuesta del microservicio
        """
        return self.forward(request, request.path)


class MatterProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Gestion de Casos (Matter Service).

    Maneja todas las peticiones relacionadas con casos legales, tareas
    y clientes. Hereda de SimpleProxyView para mantener rutas originales.

    Endpoints proxeados:
        - /api/cases/*   : CRUD de casos legales
        - /api/tasks/*   : Gestion de tareas
        - /api/clients/* : Gestion de clientes

    Atributos:
        service_name: 'matter' - Nombre del microservicio de casos
    """
    service_name = 'matter'


class DocumentProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Documentos (Document Service).

    Maneja todas las peticiones relacionadas con almacenamiento y
    gestion de documentos legales. Soporta upload/download de archivos.

    Endpoints proxeados:
        - /api/documents/* : CRUD de documentos
        - /api/folders/*   : Gestion de carpetas

    Atributos:
        service_name: 'document' - Nombre del microservicio de documentos
    """
    service_name = 'document'


class TimeTrackingProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Control de Tiempo (Time Tracking Service).

    Maneja todas las peticiones relacionadas con registro de horas
    trabajadas, cronometros y tarifas por hora.

    Endpoints proxeados:
        - /api/time-entries/* : Entradas de tiempo
        - /api/timers/*       : Cronometros activos
        - /api/rates/*        : Tarifas por hora

    Atributos:
        service_name: 'time' - Nombre del microservicio de tiempo
    """
    service_name = 'time'


class BillingProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Facturacion (Billing Service).

    Maneja todas las peticiones relacionadas con facturacion,
    pagos y acuerdos de tarifas con clientes.

    Endpoints proxeados:
        - /api/invoices/*        : CRUD de facturas
        - /api/rate-agreements/* : Acuerdos de tarifas

    Atributos:
        service_name: 'billing' - Nombre del microservicio de facturacion
    """
    service_name = 'billing'


class CalendarProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Calendario (Calendar Service).

    Maneja todas las peticiones relacionadas con eventos, vencimientos
    y dias festivos del despacho.

    Endpoints proxeados:
        - /api/events/*    : Eventos del calendario
        - /api/deadlines/* : Vencimientos y plazos legales
        - /api/holidays/*  : Dias festivos y no laborables

    Atributos:
        service_name: 'calendar' - Nombre del microservicio de calendario
    """
    service_name = 'calendar'


class PortalProxyView(SimpleProxyView):
    """
    Vista proxy para el Portal de Clientes (Client Portal Service).

    Maneja todas las peticiones del portal donde los clientes pueden
    ver el estado de sus casos, documentos y facturas.

    Endpoints proxeados:
        - /api/portal/* : Todas las funcionalidades del portal

    Atributos:
        service_name: 'portal' - Nombre del microservicio del portal
    """
    service_name = 'portal'


class AnalyticsProxyView(SimpleProxyView):
    """
    Vista proxy para el servicio de Analiticas (Analytics Service).

    Maneja todas las peticiones relacionadas con reportes, dashboards
    y metricas del despacho juridico.

    Endpoints proxeados:
        - /api/analytics/* : Dashboard, reportes, KPIs

    Atributos:
        service_name: 'analytics' - Nombre del microservicio de analiticas
    """
    service_name = 'analytics'
