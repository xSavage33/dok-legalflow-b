"""
Modulo de Vistas del Portal de Clientes (Client Portal Service)

Este archivo contiene todas las vistas (views) de la API REST para el portal de clientes.
Implementa endpoints que permiten a los clientes:
    - Ver sus casos legales (proxeando al servicio de casos)
    - Ver sus documentos (proxeando al servicio de documentos)
    - Ver sus facturas (proxeando al servicio de facturacion)
    - Gestionar sus preferencias de notificacion
    - Enviar y recibir mensajes con el equipo legal

Las vistas utilizan Django REST Framework para proporcionar una API RESTful
y actuan como proxy hacia otros microservicios del sistema LegalFlow.

Autor: Equipo LegalFlow
"""

# Importacion de la libreria requests para realizar peticiones HTTP a otros servicios
# requests es una libreria popular de Python para hacer llamadas HTTP de forma sencilla
import requests

# Importacion de clases genericas de Django REST Framework para crear vistas de API
# generics: Proporciona vistas predefinidas como ListCreateAPIView, RetrieveUpdateAPIView
# status: Contiene constantes para codigos de estado HTTP (200, 404, 403, etc.)
# filters: Proporciona backends de filtrado para busquedas
from rest_framework import generics, status, filters

# Importacion de Response para crear respuestas HTTP en formato JSON
from rest_framework.response import Response

# Importacion de APIView, la clase base para crear vistas de API personalizadas
from rest_framework.views import APIView

# Importacion del backend de filtrado de django-filter para filtrado avanzado
# DjangoFilterBackend permite filtrar querysets basados en parametros de consulta
from django_filters.rest_framework import DjangoFilterBackend

# Importacion de settings para acceder a la configuracion del proyecto Django
# Contiene las URLs de los otros microservicios
from django.conf import settings

# Importacion de timezone para manejar fechas y horas con zona horaria
from django.utils import timezone

# Importacion de Q para construir consultas complejas con operadores OR y AND
# Q permite combinar condiciones de filtrado de forma flexible
from django.db.models import Q

# Importacion de los modelos locales del portal de clientes
from .models import ClientPreference, Message

# Importacion de los serializadores para convertir modelos a/desde JSON
from .serializers import (
    ClientPreferenceSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    SystemNotificationSerializer,
)


def proxy_get(url, headers):
    """
    Funcion auxiliar para realizar peticiones GET proxy a otros microservicios.

    Esta funcion encapsula la logica de hacer peticiones HTTP a otros servicios
    del sistema, manejando errores y timeouts de forma consistente.

    Args:
        url (str): La URL completa del endpoint del microservicio destino
        headers (dict): Diccionario con los headers HTTP a enviar (incluye autorizacion)

    Returns:
        tuple: Una tupla con dos elementos:
            - dict: Los datos de respuesta en formato JSON o un diccionario de error
            - int: El codigo de estado HTTP de la respuesta (200, 404, 503, etc.)

    Raises:
        No lanza excepciones; los errores se capturan y retornan como respuesta
    """
    try:
        # Agregar el header 'Host' para evitar errores DisallowedHost en Docker
        # Cuando los servicios se comunican internamente, el host puede no coincidir
        proxy_headers = {**headers, 'Host': 'localhost'}

        # Realizar la peticion GET con un timeout de 10 segundos
        # El timeout evita que la aplicacion se bloquee si el servicio no responde
        response = requests.get(url, headers=proxy_headers, timeout=10)

        # Retornar los datos JSON y el codigo de estado de la respuesta
        return response.json(), response.status_code
    except Exception as e:
        # En caso de cualquier error, retornar un mensaje de error y codigo 503
        # 503 Service Unavailable indica que el servicio no esta disponible
        return {'error': str(e)}, 503


class MyCasesView(APIView):
    """
    Vista de API para obtener los casos del cliente autenticado.

    Esta vista actua como proxy hacia el servicio de casos (Matter Service),
    filtrando solo los casos que pertenecen al cliente actual.

    Metodos HTTP permitidos:
        GET: Obtiene la lista de casos del cliente

    Autenticacion:
        Requiere token JWT valido en el header Authorization
    """

    def get(self, request):
        """
        Maneja las peticiones GET para obtener los casos del cliente.

        Proxea la peticion al servicio de casos (Matter Service) agregando
        el filtro por client_id para obtener solo los casos del cliente actual.

        Args:
            request: Objeto HttpRequest con la informacion de la peticion

        Returns:
            Response: Respuesta JSON con la lista de casos del cliente
        """
        # Extraer el header de autorizacion de la peticion original
        # META contiene todos los headers HTTP con el prefijo HTTP_
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Construir la URL del servicio de casos con el filtro de client_id
        # request.user.id contiene el ID del usuario autenticado
        url = f"{settings.MATTER_SERVICE_URL}/api/cases/?client_id={request.user.id}"

        # Realizar la peticion proxy al servicio de casos
        data, status_code = proxy_get(url, headers)

        # Retornar la respuesta del servicio de casos al cliente
        return Response(data, status=status_code)


class MyCaseDetailView(APIView):
    """
    Vista de API para obtener el detalle de un caso especifico del cliente.

    Esta vista permite al cliente ver los detalles completos de uno de sus casos,
    verificando que el caso realmente le pertenece antes de mostrar la informacion.

    Metodos HTTP permitidos:
        GET: Obtiene el detalle de un caso especifico

    Autenticacion:
        Requiere token JWT valido y el caso debe pertenecer al cliente
    """

    def get(self, request, case_id):
        """
        Maneja las peticiones GET para obtener el detalle de un caso.

        Proxea la peticion al servicio de casos y verifica que el cliente
        sea el propietario del caso antes de retornar los datos.

        Args:
            request: Objeto HttpRequest con la informacion de la peticion
            case_id: UUID del caso a consultar (capturado de la URL)

        Returns:
            Response: Respuesta JSON con los detalles del caso o error 403 si no autorizado
        """
        # Extraer el header de autorizacion de la peticion original
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Construir la URL del servicio de casos para el caso especifico
        url = f"{settings.MATTER_SERVICE_URL}/api/cases/{case_id}/"

        # Realizar la peticion proxy al servicio de casos
        data, status_code = proxy_get(url, headers)

        # Verificar que el cliente sea el propietario del caso
        # Solo si la peticion fue exitosa (200) verificamos la propiedad
        if status_code == 200 and str(data.get('client_id')) != str(request.user.id):
            # Si el client_id del caso no coincide con el usuario actual, denegar acceso
            return Response({'error': 'No autorizado'}, status=403)

        # Retornar los datos del caso si la verificacion fue exitosa
        return Response(data, status=status_code)


class MyDocumentsView(APIView):
    """
    Vista de API para obtener todos los documentos de los casos del cliente.

    Esta vista primero obtiene todos los casos del cliente, luego consulta
    los documentos de cada caso y los agrega en una sola respuesta.

    Metodos HTTP permitidos:
        GET: Obtiene todos los documentos de los casos del cliente

    Autenticacion:
        Requiere token JWT valido
    """

    def get(self, request):
        """
        Maneja las peticiones GET para obtener los documentos del cliente.

        Realiza dos tipos de consultas proxy:
        1. Obtiene todos los casos del cliente desde el servicio de casos
        2. Para cada caso, obtiene sus documentos desde el servicio de documentos

        Args:
            request: Objeto HttpRequest con la informacion de la peticion

        Returns:
            Response: Respuesta JSON con la lista agregada de todos los documentos
        """
        # Primero obtener los casos del cliente para saber que documentos consultar
        # Extraer el header de autorizacion
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Construir la URL para obtener los casos del cliente
        cases_url = f"{settings.MATTER_SERVICE_URL}/api/cases/?client_id={request.user.id}"

        # Obtener los casos del cliente
        cases_data, _ = proxy_get(cases_url, headers)

        # Si el cliente no tiene casos, retornar una lista vacia
        if not cases_data.get('results'):
            return Response({'results': []})

        # Lista para acumular todos los documentos de todos los casos
        all_documents = []

        # Iterar sobre cada caso del cliente para obtener sus documentos
        for case in cases_data.get('results', []):
            # Construir la URL del servicio de documentos para este caso
            docs_url = f"{settings.DOCUMENT_SERVICE_URL}/api/cases/{case['id']}/documents/"

            # Obtener los documentos de este caso
            docs_data, _ = proxy_get(docs_url, headers)

            # Si hay documentos, agregarlos a la lista acumulada
            if docs_data.get('results'):
                # extend agrega todos los elementos de la lista a all_documents
                all_documents.extend(docs_data['results'])

        # Retornar todos los documentos con el conteo total
        return Response({'results': all_documents, 'count': len(all_documents)})


class MyDocumentDownloadView(APIView):
    """
    Vista de API para descargar un documento del cliente.

    Esta vista permite a los clientes descargar documentos que pertenecen
    a sus casos. Verifica que el documento pertenezca a un caso del cliente
    antes de permitir la descarga.

    Metodos HTTP permitidos:
        GET: Descarga el archivo del documento

    Autenticacion:
        Requiere token JWT valido
    """

    def get(self, request, document_id):
        """
        Maneja las peticiones GET para descargar un documento.

        Verifica que el documento pertenezca a un caso del cliente
        y luego hace proxy al servicio de documentos para la descarga.

        Args:
            request: Objeto HttpRequest con la informacion de la peticion
            document_id: UUID del documento a descargar

        Returns:
            HttpResponse: Archivo del documento o error si no autorizado
        """
        from django.http import HttpResponse

        # Extraer el header de autorizacion
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Primero, obtener los casos del cliente
        cases_url = f"{settings.MATTER_SERVICE_URL}/api/cases/?client_id={request.user.id}"
        cases_data, _ = proxy_get(cases_url, headers)

        if not cases_data.get('results'):
            return Response(
                {'error': 'No tiene casos asociados'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Obtener lista de IDs de casos del cliente
        client_case_ids = [case['id'] for case in cases_data.get('results', [])]

        # Obtener informacion del documento para verificar que pertenece al cliente
        doc_url = f"{settings.DOCUMENT_SERVICE_URL}/api/documents/{document_id}/"
        doc_data, doc_status = proxy_get(doc_url, headers)

        if doc_status == 404:
            return Response(
                {'error': 'Documento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que el documento pertenece a un caso del cliente
        doc_case_id = doc_data.get('case_id')
        if doc_case_id not in client_case_ids:
            return Response(
                {'error': 'No tiene permiso para acceder a este documento'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Obtener metadata del documento para la respuesta
        original_filename = doc_data.get('original_filename', doc_data.get('name', 'documento'))
        mime_type = doc_data.get('mime_type', 'application/octet-stream')

        # Hacer proxy a la descarga del documento
        download_url = f"{settings.DOCUMENT_SERVICE_URL}/api/documents/{document_id}/download/"

        try:
            # Agregar Host header para evitar DisallowedHost en Docker
            download_headers = {**headers, 'Host': 'localhost'}
            response = requests.get(download_url, headers=download_headers, stream=True, timeout=60)

            if response.status_code == 200:
                # Crear respuesta con el contenido del archivo usando metadata del documento
                django_response = HttpResponse(
                    response.content,
                    content_type=mime_type if mime_type else 'application/octet-stream'
                )
                # Establecer el nombre del archivo para descarga
                django_response['Content-Disposition'] = f'attachment; filename="{original_filename}"'
                return django_response
            else:
                return Response(
                    {'error': 'Error al descargar el documento'},
                    status=response.status_code
                )
        except Exception as e:
            return Response(
                {'error': f'Error de conexion: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class MyInvoicesView(APIView):
    """
    Vista de API para obtener las facturas del cliente.

    Esta vista proxea las peticiones al servicio de facturacion para obtener
    todas las facturas asociadas al cliente autenticado.

    Metodos HTTP permitidos:
        GET: Obtiene la lista de facturas del cliente

    Autenticacion:
        Requiere token JWT valido
    """

    def get(self, request):
        """
        Maneja las peticiones GET para obtener las facturas del cliente.

        Proxea la peticion al servicio de facturacion (Billing Service)
        para obtener todas las facturas del cliente.

        Args:
            request: Objeto HttpRequest con la informacion de la peticion

        Returns:
            Response: Respuesta JSON con la lista de facturas del cliente
        """
        # Extraer el header de autorizacion de la peticion original
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Construir la URL del servicio de facturacion para el cliente actual
        url = f"{settings.BILLING_SERVICE_URL}/api/clients/{request.user.id}/invoices/"

        # Realizar la peticion proxy al servicio de facturacion
        data, status_code = proxy_get(url, headers)

        # Retornar la respuesta del servicio de facturacion
        return Response(data, status=status_code)


class MyTimeEntriesView(APIView):
    """
    Vista de API para obtener los registros de tiempo de los casos del cliente.

    Esta vista obtiene todos los registros de tiempo asociados a los casos
    del cliente, permitiendo ver el trabajo realizado por el equipo legal.
    Solo muestra entradas de tiempo ya facturadas o aprobadas.

    Metodos HTTP permitidos:
        GET: Obtiene los registros de tiempo de los casos del cliente

    Parametros de consulta:
        - case_id: Filtrar por caso especifico (opcional)
        - from_date: Fecha desde (YYYY-MM-DD, opcional)
        - to_date: Fecha hasta (YYYY-MM-DD, opcional)

    Autenticacion:
        Requiere token JWT valido
    """

    def get(self, request):
        """
        Maneja las peticiones GET para obtener registros de tiempo.

        Realiza las siguientes operaciones:
        1. Obtiene todos los casos del cliente
        2. Para cada caso, obtiene las entradas de tiempo del servicio de tiempo
        3. Filtra solo entradas facturadas o aprobadas
        4. Retorna el historial consolidado

        Args:
            request: Objeto HttpRequest con la informacion de la peticion

        Returns:
            Response: Respuesta JSON con la lista de registros de tiempo
        """
        # Extraer el header de autorizacion
        headers = {'Authorization': request.META.get('HTTP_AUTHORIZATION', '')}

        # Obtener parametros de filtro opcionales
        case_id_filter = request.query_params.get('case_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        # Si se especifica un caso, verificar que pertenezca al cliente
        if case_id_filter:
            case_url = f"{settings.MATTER_SERVICE_URL}/api/cases/{case_id_filter}/"
            case_data, case_status = proxy_get(case_url, headers)

            if case_status == 404:
                return Response({'error': 'Caso no encontrado'}, status=404)

            if str(case_data.get('client_id')) != str(request.user.id):
                return Response({'error': 'No autorizado'}, status=403)

            case_ids = [case_id_filter]
        else:
            # Obtener todos los casos del cliente
            cases_url = f"{settings.MATTER_SERVICE_URL}/api/cases/?client_id={request.user.id}"
            cases_data, _ = proxy_get(cases_url, headers)

            if not cases_data.get('results'):
                return Response({
                    'results': [],
                    'count': 0,
                    'total_hours': 0,
                    'total_amount': 0
                })

            case_ids = [case['id'] for case in cases_data.get('results', [])]

        # Lista para acumular todos los registros de tiempo
        all_time_entries = []
        total_hours = 0
        total_amount = 0

        # Obtener registros de tiempo de cada caso
        for case_id in case_ids:
            # Construir URL con filtros opcionales
            time_url = f"{settings.TIME_SERVICE_URL}/api/time-entries/?case_id={case_id}"

            # Agregar filtros de fecha si se especificaron
            if from_date:
                time_url += f"&date__gte={from_date}"
            if to_date:
                time_url += f"&date__lte={to_date}"

            # Solo obtener entradas facturadas o aprobadas (no borradores)
            time_url += "&status__in=billed,approved"

            time_data, time_status = proxy_get(time_url, headers)

            if time_status == 200 and time_data.get('results'):
                entries = time_data['results']
                all_time_entries.extend(entries)

                # Calcular totales
                for entry in entries:
                    hours = float(entry.get('hours', 0))
                    rate = float(entry.get('hourly_rate', 0))
                    total_hours += hours
                    total_amount += hours * rate

        # Ordenar por fecha descendente (mas reciente primero)
        all_time_entries.sort(key=lambda x: x.get('date', ''), reverse=True)

        # Retornar el historial con totales
        return Response({
            'results': all_time_entries,
            'count': len(all_time_entries),
            'total_hours': round(total_hours, 2),
            'total_amount': round(total_amount, 2),
            'summary': {
                'cases_count': len(case_ids),
                'entries_count': len(all_time_entries),
                'total_hours': round(total_hours, 2),
                'total_amount': round(total_amount, 2)
            }
        })


class ClientPreferenceView(generics.RetrieveUpdateAPIView):
    """
    Vista de API para obtener y actualizar las preferencias del cliente.

    Esta vista permite al cliente ver y modificar sus preferencias de notificacion,
    idioma y zona horaria. Utiliza get_or_create para asegurar que siempre
    exista un registro de preferencias para cada cliente.

    Hereda de RetrieveUpdateAPIView que proporciona:
        GET: Obtiene las preferencias actuales
        PUT: Actualiza todas las preferencias
        PATCH: Actualiza parcialmente las preferencias

    Autenticacion:
        Requiere token JWT valido
    """

    # Especificar el serializador a usar para convertir el modelo a/desde JSON
    serializer_class = ClientPreferenceSerializer

    def get_object(self):
        """
        Obtiene el objeto de preferencias del cliente actual.

        Utiliza get_or_create para obtener las preferencias existentes
        o crear un nuevo registro con valores por defecto si no existe.

        Returns:
            ClientPreference: El objeto de preferencias del cliente
        """
        # get_or_create retorna una tupla (objeto, creado)
        # _ ignora el segundo valor (booleano que indica si se creo)
        obj, _ = ClientPreference.objects.get_or_create(user_id=self.request.user.id)
        return obj


class MessageListCreateView(generics.ListCreateAPIView):
    """
    Vista de API para listar y crear mensajes.

    Esta vista permite al cliente:
    - Ver todos sus mensajes (enviados y recibidos)
    - Crear nuevos mensajes para enviar al equipo legal

    Soporta filtrado por case_id y status, y busqueda por subject y content.

    Hereda de ListCreateAPIView que proporciona:
        GET: Lista todos los mensajes del cliente
        POST: Crea un nuevo mensaje

    Autenticacion:
        Requiere token JWT valido
    """

    # Backends de filtrado: DjangoFilterBackend para filtros exactos, SearchFilter para busqueda
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    # Campos disponibles para filtrado exacto via parametros de consulta
    # Ejemplo: /messages/?case_id=xxx&status=read
    filterset_fields = ['case_id', 'status']

    # Campos disponibles para busqueda de texto
    # Ejemplo: /messages/?search=contrato
    search_fields = ['subject', 'content']

    def get_serializer_class(self):
        """
        Determina que serializador usar segun el metodo HTTP.

        Para POST (crear) usa MessageCreateSerializer que maneja
        la asignacion automatica del remitente.
        Para GET (listar) usa MessageSerializer completo.

        Returns:
            class: La clase del serializador apropiado
        """
        # Si es una peticion POST, usar el serializador de creacion
        if self.request.method == 'POST':
            return MessageCreateSerializer
        # Para otras peticiones (GET), usar el serializador completo
        return MessageSerializer

    def get_queryset(self):
        """
        Obtiene el conjunto de mensajes del cliente actual.

        Filtra los mensajes donde el cliente es el remitente O el destinatario,
        usando el operador Q para combinar condiciones con OR.

        Returns:
            QuerySet: Conjunto de mensajes del cliente
        """
        # Obtener el ID del usuario autenticado
        user_id = self.request.user.id

        # Filtrar mensajes donde el usuario es remitente O destinatario
        # Q() permite usar operador OR (|) entre condiciones
        return Message.objects.filter(
            Q(sender_id=user_id) | Q(recipient_id=user_id)
        )


class MessageDetailView(generics.RetrieveAPIView):
    """
    Vista de API para obtener el detalle de un mensaje especifico.

    Ademas de mostrar el mensaje, esta vista automaticamente marca
    el mensaje como leido si el usuario actual es el destinatario.

    Hereda de RetrieveAPIView que proporciona:
        GET: Obtiene el detalle de un mensaje

    Autenticacion:
        Requiere token JWT valido y el usuario debe ser remitente o destinatario
    """

    # Serializador para convertir el mensaje a JSON
    serializer_class = MessageSerializer

    # Campo usado para buscar el mensaje en la URL
    # Por defecto es 'pk', pero usamos 'id' para coincidir con UUID
    lookup_field = 'id'

    def get_queryset(self):
        """
        Obtiene el conjunto de mensajes accesibles por el cliente actual.

        Solo permite acceder a mensajes donde el usuario es remitente o destinatario.

        Returns:
            QuerySet: Conjunto de mensajes del cliente
        """
        # Obtener el ID del usuario autenticado
        user_id = self.request.user.id

        # Filtrar mensajes donde el usuario es remitente O destinatario
        return Message.objects.filter(
            Q(sender_id=user_id) | Q(recipient_id=user_id)
        )

    def retrieve(self, request, *args, **kwargs):
        """
        Maneja la peticion GET para obtener un mensaje.

        Ademas de retornar el mensaje, lo marca como leido si:
        - El usuario actual es el destinatario
        - El mensaje aun no ha sido marcado como leido

        Args:
            request: Objeto HttpRequest con la informacion de la peticion
            *args: Argumentos posicionales adicionales
            **kwargs: Argumentos de palabra clave adicionales (incluye 'id')

        Returns:
            Response: Respuesta JSON con los datos del mensaje
        """
        # Obtener el objeto mensaje usando get_object() de la clase padre
        message = self.get_object()

        # Verificar si el usuario es el destinatario y el mensaje no esta leido
        if str(message.recipient_id) == str(request.user.id) and message.status != 'read':
            # Marcar el mensaje como leido
            message.status = 'read'
            # Registrar la fecha y hora de lectura
            message.read_at = timezone.now()
            # Guardar los cambios en la base de datos
            message.save()

        # Retornar el mensaje serializado como JSON
        return Response(MessageSerializer(message).data)


class UnreadMessagesView(generics.ListAPIView):
    """
    Vista de API para obtener los mensajes no leidos del cliente.

    Esta vista es util para mostrar notificaciones o badges con la
    cantidad de mensajes pendientes de leer.

    Hereda de ListAPIView que proporciona:
        GET: Lista los mensajes no leidos

    Autenticacion:
        Requiere token JWT valido
    """

    # Serializador para convertir los mensajes a JSON
    serializer_class = MessageSerializer

    def get_queryset(self):
        """
        Obtiene los mensajes no leidos del cliente actual.

        Filtra mensajes donde:
        - El usuario es el destinatario
        - El estado es 'sent' (enviado) o 'delivered' (entregado)

        Returns:
            QuerySet: Conjunto de mensajes no leidos
        """
        # Filtrar mensajes no leidos donde el usuario es destinatario
        # status__in permite verificar si el valor esta en una lista
        return Message.objects.filter(
            recipient_id=self.request.user.id,
            status__in=['sent', 'delivered']
        )


class MarkMessageReadView(APIView):
    """
    Vista de API para marcar un mensaje como leido.

    Proporciona un endpoint explicito para marcar mensajes como leidos,
    util cuando el cliente quiere marcar un mensaje sin necesidad de
    abrir su detalle completo.

    Metodos HTTP permitidos:
        POST: Marca el mensaje como leido

    Autenticacion:
        Requiere token JWT valido y el usuario debe ser el destinatario
    """

    def post(self, request, id):
        """
        Maneja las peticiones POST para marcar un mensaje como leido.

        Solo permite marcar mensajes donde el usuario actual es el destinatario.

        Args:
            request: Objeto HttpRequest con la informacion de la peticion
            id: UUID del mensaje a marcar como leido (capturado de la URL)

        Returns:
            Response: Respuesta JSON con el mensaje actualizado o error 404
        """
        try:
            # Intentar obtener el mensaje verificando que el usuario sea el destinatario
            # get() lanza DoesNotExist si no encuentra el mensaje
            message = Message.objects.get(id=id, recipient_id=request.user.id)

            # Actualizar el estado del mensaje a 'leido'
            message.status = 'read'

            # Registrar la fecha y hora actual como momento de lectura
            message.read_at = timezone.now()

            # Guardar los cambios en la base de datos
            message.save()

            # Retornar el mensaje actualizado serializado como JSON
            return Response(MessageSerializer(message).data)
        except Message.DoesNotExist:
            # Si el mensaje no existe o no pertenece al usuario, retornar error 404
            return Response({'error': 'Message not found'}, status=404)


class SystemNotificationView(APIView):
    """
    Vista para recibir notificaciones del sistema desde otros microservicios.

    Esta vista permite que servicios internos como billing_service envien
    mensajes a los clientes sin requerir autenticacion de usuario.
    Se usa para notificar sobre nuevas facturas, pagos, actualizaciones de casos, etc.

    Seguridad:
        - Valida un token de servicio interno (SERVICE_TOKEN)
        - Solo acepta peticiones de servicios autorizados

    Metodos HTTP:
        POST: Crea un mensaje de notificacion del sistema
    """

    # Desactivar autenticacion JWT para este endpoint
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        Crea un mensaje de notificacion del sistema.

        Valida el token de servicio y crea el mensaje usando los datos
        proporcionados por el servicio que hace la peticion.

        Args:
            request: Objeto HttpRequest con los datos del mensaje

        Returns:
            Response: Mensaje creado o error de validacion
        """
        # Validar token de servicio interno
        service_token = request.headers.get('X-Service-Token')
        expected_token = getattr(settings, 'INTERNAL_SERVICE_TOKEN', 'internal-service-token')

        if service_token != expected_token:
            return Response(
                {'error': 'Token de servicio invalido'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Crear el mensaje usando el serializador
        serializer = SystemNotificationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
