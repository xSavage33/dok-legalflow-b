"""
views.py - Vistas y controladores del servicio de calendario

Este archivo contiene todas las vistas (views) de la API REST para el servicio
de calendario de LegalFlow. Las vistas manejan las solicitudes HTTP y devuelven
respuestas apropiadas.

Vistas incluidas:
    - Gestion de eventos (CRUD, proximos, hoy)
    - Gestion de plazos (CRUD, proximos, vencidos, completar, extender)
    - Gestion de festivos (CRUD, verificacion de dias habiles)
    - Calculo de plazos basado en dias habiles

El archivo utiliza Django REST Framework para proporcionar una API RESTful
con filtrado, busqueda y ordenamiento automaticos.

Autor: Equipo LegalFlow
Fecha de creacion: 2024
"""

# Importacion de clases genericas de Django REST Framework
# generics: proporciona vistas basadas en clases con operaciones CRUD predefinidas
# status: contiene constantes para codigos de estado HTTP (200, 404, 400, etc.)
# filters: proporciona backends de filtrado y busqueda
from rest_framework import generics, status, filters

# Importacion de Response para crear respuestas HTTP personalizadas
from rest_framework.response import Response

# Importacion de APIView para crear vistas personalizadas basadas en clases
from rest_framework.views import APIView

# Importacion de DjangoFilterBackend para filtrado avanzado
# Permite filtrar querysets basandose en parametros de consulta URL
from django_filters.rest_framework import DjangoFilterBackend

# Importacion de timezone de Django para manejo de fechas con zona horaria
from django.utils import timezone

# Importacion de clases de fecha y tiempo
# date: para trabajar con fechas sin componente de hora
# timedelta: para calcular diferencias entre fechas
# datetime: para trabajar con fechas y horas completas
from datetime import date, timedelta, datetime

# Importacion de los modelos definidos en models.py
# Event: modelo de eventos del calendario
# Deadline: modelo de plazos legales
# HolidayCalendar: modelo de dias festivos
from .models import Event, Deadline, HolidayCalendar

# Importacion de los serializadores definidos en serializers.py
# Los serializadores convierten objetos Python a JSON y viceversa
from .serializers import (
    EventSerializer,                    # Serializador para lectura de eventos
    EventCreateSerializer,              # Serializador para creacion de eventos
    DeadlineSerializer,                 # Serializador para lectura de plazos
    DeadlineCreateSerializer,           # Serializador para creacion de plazos
    HolidayCalendarSerializer,          # Serializador para festivos
    CalculateDeadlineSerializer,        # Serializador para entrada de calculo
    DeadlineCalculationResultSerializer, # Serializador para resultado de calculo
)


class EventListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear eventos

    Esta vista maneja dos operaciones HTTP:
        - GET: Lista todos los eventos con soporte para filtrado, busqueda y ordenamiento
        - POST: Crea un nuevo evento en el sistema

    Soporta los siguientes filtros:
        - case_id: Filtrar por ID del caso
        - event_type: Filtrar por tipo de evento
        - status: Filtrar por estado del evento
        - date_from: Filtrar eventos desde esta fecha
        - date_to: Filtrar eventos hasta esta fecha

    Campos de busqueda:
        - title: Buscar en el titulo
        - description: Buscar en la descripcion
        - case_number: Buscar por numero de caso
    """

    # Queryset base: todos los eventos de la base de datos
    queryset = Event.objects.all()

    # Configuracion de backends de filtrado
    # DjangoFilterBackend: permite filtrado exacto por campos
    # SearchFilter: permite busqueda de texto en campos especificados
    # OrderingFilter: permite ordenamiento dinamico por campos
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Campos disponibles para filtrado exacto
    # Ejemplo de uso: ?case_id=123&status=scheduled
    filterset_fields = ['case_id', 'event_type', 'status']

    # Campos donde se realizara la busqueda de texto
    # Ejemplo de uso: ?search=audiencia
    search_fields = ['title', 'description', 'case_number']

    # Campos disponibles para ordenamiento
    # Ejemplo de uso: ?ordering=-start_datetime (orden descendente)
    ordering_fields = ['start_datetime', 'created_at']

    # Ordenamiento predeterminado: por fecha de inicio ascendente
    ordering = ['start_datetime']

    def get_serializer_class(self):
        """
        Selecciona el serializador apropiado segun el metodo HTTP

        Para POST (creacion) usa EventCreateSerializer que tiene campos
        limitados y asigna automaticamente el creador.
        Para GET (lectura) usa EventSerializer que incluye todos los campos.

        Returns:
            class: Clase del serializador a utilizar
        """
        # Si es una solicitud POST, usar el serializador de creacion
        if self.request.method == 'POST':
            return EventCreateSerializer
        # Para otros metodos (GET), usar el serializador completo
        return EventSerializer

    def get_queryset(self):
        """
        Personaliza el queryset aplicando filtros de fecha adicionales

        Este metodo extiende el filtrado base para soportar rangos de fecha
        mediante los parametros date_from y date_to.

        Returns:
            QuerySet: Queryset filtrado de eventos
        """
        # Obtener el queryset base de la clase padre
        queryset = super().get_queryset()

        # Obtener parametros de fecha del query string
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        # Aplicar filtro de fecha inicial si se proporciono
        # __date__gte: la parte de fecha es mayor o igual que
        if date_from:
            queryset = queryset.filter(start_datetime__date__gte=date_from)

        # Aplicar filtro de fecha final si se proporciono
        # __date__lte: la parte de fecha es menor o igual que
        if date_to:
            queryset = queryset.filter(start_datetime__date__lte=date_to)

        # Retornar el queryset filtrado
        return queryset


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un evento especifico

    Esta vista maneja tres operaciones HTTP sobre un evento individual:
        - GET: Obtiene los detalles completos del evento
        - PUT/PATCH: Actualiza el evento (total o parcialmente)
        - DELETE: Elimina el evento del sistema

    El evento se identifica por su UUID en la URL.
    """

    # Queryset base: todos los eventos
    queryset = Event.objects.all()

    # Serializador para lectura y actualizacion
    serializer_class = EventSerializer

    # Campo utilizado para buscar el evento en la URL
    # La URL seria: /events/<uuid:id>/
    lookup_field = 'id'


class UpcomingEventsView(generics.ListAPIView):
    """
    Vista para listar eventos proximos

    Devuelve los eventos programados o confirmados que ocurriran
    dentro de un numero especificado de dias (por defecto 7 dias).

    Parametros de consulta:
        - days: Numero de dias hacia adelante a considerar (default: 7)

    Ejemplo de uso:
        GET /events/upcoming/?days=14  -> Eventos de los proximos 14 dias
    """

    # Serializador para los resultados
    serializer_class = EventSerializer

    def get_queryset(self):
        """
        Construye el queryset de eventos proximos

        Filtra los eventos que:
        1. Comienzan entre hoy y la fecha limite
        2. Estan en estado 'scheduled' o 'confirmed'

        Returns:
            QuerySet: Eventos proximos filtrados
        """
        # Obtener el parametro 'days' de la URL, default 7
        days = int(self.request.query_params.get('days', 7))

        # Calcular la fecha limite sumando dias a la fecha actual
        end_date = date.today() + timedelta(days=days)

        # Filtrar eventos que estan dentro del rango de fechas
        # y que tienen estados activos (no cancelados ni completados)
        return Event.objects.filter(
            start_datetime__date__gte=date.today(),  # Desde hoy
            start_datetime__date__lte=end_date,       # Hasta la fecha limite
            status__in=['scheduled', 'confirmed']     # Solo estados activos
        )


class TodayEventsView(generics.ListAPIView):
    """
    Vista para listar eventos del dia actual

    Devuelve todos los eventos programados o confirmados
    que estan programados para hoy.

    Util para mostrar la agenda del dia en el dashboard.
    """

    # Serializador para los resultados
    serializer_class = EventSerializer

    def get_queryset(self):
        """
        Construye el queryset de eventos de hoy

        Returns:
            QuerySet: Eventos del dia actual con estados activos
        """
        # Filtrar eventos donde la fecha de inicio es hoy
        # y el estado es activo
        return Event.objects.filter(
            start_datetime__date=date.today(),    # Solo eventos de hoy
            status__in=['scheduled', 'confirmed'] # Solo estados activos
        )


class DeadlineListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear plazos legales

    Esta vista maneja:
        - GET: Lista todos los plazos con filtrado, busqueda y ordenamiento
        - POST: Crea un nuevo plazo en el sistema

    Filtros disponibles:
        - case_id: Filtrar por ID del caso
        - priority: Filtrar por nivel de prioridad
        - status: Filtrar por estado del plazo
        - assigned_to_id: Filtrar por usuario asignado

    Campos de busqueda:
        - title: Buscar en el titulo
        - description: Buscar en la descripcion
        - case_number: Buscar por numero de caso
    """

    # Queryset base: todos los plazos
    queryset = Deadline.objects.all()

    # Configuracion de backends de filtrado
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Campos para filtrado exacto
    filterset_fields = ['case_id', 'priority', 'status', 'assigned_to_id']

    # Campos para busqueda de texto
    search_fields = ['title', 'description', 'case_number']

    # Campos disponibles para ordenamiento
    ordering_fields = ['due_date', 'priority', 'created_at']

    # Ordenamiento predeterminado: por fecha de vencimiento, luego por prioridad descendente
    ordering = ['due_date', '-priority']

    def get_serializer_class(self):
        """
        Selecciona el serializador segun el metodo HTTP

        Returns:
            class: Clase del serializador apropiado
        """
        # Usar serializador de creacion para POST
        if self.request.method == 'POST':
            return DeadlineCreateSerializer
        # Usar serializador completo para GET
        return DeadlineSerializer


class DeadlineDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un plazo especifico

    Operaciones HTTP soportadas:
        - GET: Obtiene los detalles del plazo
        - PUT/PATCH: Actualiza el plazo
        - DELETE: Elimina el plazo

    El plazo se identifica por su UUID en la URL.
    """

    # Queryset base: todos los plazos
    queryset = Deadline.objects.all()

    # Serializador para operaciones de lectura y actualizacion
    serializer_class = DeadlineSerializer

    # Campo para buscar el plazo en la URL
    lookup_field = 'id'


class CompleteDeadlineView(APIView):
    """
    Vista para marcar un plazo como completado

    Esta vista personalizada maneja la accion especifica de completar
    un plazo, registrando quien y cuando lo completo.

    Endpoint: POST /deadlines/<uuid:id>/complete/
    """

    def post(self, request, id):
        """
        Marca el plazo especificado como completado

        Args:
            request: Objeto de solicitud HTTP con datos del usuario
            id: UUID del plazo a completar

        Returns:
            Response: Plazo actualizado o mensaje de error
        """
        try:
            # Intentar obtener el plazo por su ID
            deadline = Deadline.objects.get(id=id)
        except Deadline.DoesNotExist:
            # Si no existe, retornar error 404
            return Response(
                {'error': 'Plazo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Actualizar el estado del plazo a completado
        deadline.status = 'completed'

        # Registrar la fecha y hora de completado (con zona horaria)
        deadline.completed_at = timezone.now()

        # Registrar el ID del usuario que completo el plazo
        deadline.completed_by_id = request.user.id

        # Guardar los cambios en la base de datos
        deadline.save()

        # Retornar el plazo actualizado serializado
        return Response(DeadlineSerializer(deadline).data)


class ExtendDeadlineView(APIView):
    """
    Vista para extender la fecha de vencimiento de un plazo

    Permite cambiar la fecha de vencimiento de un plazo existente
    y marca el plazo con estado 'extended'.

    Endpoint: POST /deadlines/<uuid:id>/extend/
    Body: {"new_due_date": "YYYY-MM-DD"}
    """

    def post(self, request, id):
        """
        Extiende el plazo a una nueva fecha de vencimiento

        Args:
            request: Objeto de solicitud con new_due_date en el body
            id: UUID del plazo a extender

        Returns:
            Response: Plazo actualizado o mensaje de error
        """
        try:
            # Intentar obtener el plazo por su ID
            deadline = Deadline.objects.get(id=id)
        except Deadline.DoesNotExist:
            # Si no existe, retornar error 404
            return Response(
                {'error': 'Plazo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Obtener la nueva fecha de vencimiento del cuerpo de la solicitud
        new_due_date = request.data.get('new_due_date')

        # Validar que se proporciono la nueva fecha
        if not new_due_date:
            return Response(
                {'error': 'new_due_date es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Actualizar la fecha de vencimiento
        deadline.due_date = new_due_date

        # Cambiar el estado a 'extended' para indicar que fue extendido
        deadline.status = 'extended'

        # Guardar los cambios
        deadline.save()

        # Retornar el plazo actualizado
        return Response(DeadlineSerializer(deadline).data)


class UpcomingDeadlinesView(generics.ListAPIView):
    """
    Vista para listar plazos proximos a vencer

    Devuelve los plazos pendientes que vencen dentro de un
    numero especificado de dias.

    Parametros de consulta:
        - days: Numero de dias hacia adelante (default: 7)

    Ejemplo:
        GET /deadlines/upcoming/?days=30  -> Plazos de los proximos 30 dias
    """

    # Serializador para los resultados
    serializer_class = DeadlineSerializer

    def get_queryset(self):
        """
        Construye el queryset de plazos proximos

        Returns:
            QuerySet: Plazos pendientes dentro del rango de fechas
        """
        # Obtener parametro de dias, default 7
        days = int(self.request.query_params.get('days', 7))

        # Calcular fecha limite
        end_date = date.today() + timedelta(days=days)

        # Filtrar plazos pendientes dentro del rango
        return Deadline.objects.filter(
            due_date__gte=date.today(),  # Vencen hoy o despues
            due_date__lte=end_date,       # Vencen antes de la fecha limite
            status='pending'              # Solo plazos pendientes
        )


class OverdueDeadlinesView(generics.ListAPIView):
    """
    Vista para listar plazos vencidos

    Devuelve todos los plazos que estan en estado pendiente
    pero cuya fecha de vencimiento ya paso.

    Util para identificar plazos que requieren atencion urgente.
    """

    # Serializador para los resultados
    serializer_class = DeadlineSerializer

    def get_queryset(self):
        """
        Construye el queryset de plazos vencidos

        Returns:
            QuerySet: Plazos pendientes con fecha de vencimiento pasada
        """
        # Filtrar plazos cuya fecha de vencimiento ya paso
        # y que aun estan en estado pendiente
        return Deadline.objects.filter(
            due_date__lt=date.today(),  # Fecha de vencimiento antes de hoy
            status='pending'             # Aun en estado pendiente
        )


class MyDeadlinesView(generics.ListAPIView):
    """
    Vista para listar plazos asignados al usuario actual

    Devuelve todos los plazos pendientes que estan asignados
    al usuario que hace la solicitud.

    Util para que cada usuario vea su lista personal de pendientes.
    """

    # Serializador para los resultados
    serializer_class = DeadlineSerializer

    def get_queryset(self):
        """
        Construye el queryset de plazos del usuario actual

        Returns:
            QuerySet: Plazos pendientes asignados al usuario actual
        """
        # Filtrar plazos asignados al usuario actual
        # request.user.id contiene el ID del usuario autenticado
        return Deadline.objects.filter(
            assigned_to_id=self.request.user.id,  # Asignados al usuario actual
            status='pending'                       # Solo pendientes
        )


class CalculateDeadlineView(APIView):
    """
    Vista para calcular fechas de vencimiento

    Calcula una fecha de vencimiento basandose en una fecha inicial
    y un numero de dias habiles, considerando fines de semana y
    festivos de la jurisdiccion especificada.

    Endpoint: POST /deadlines/calculate/
    Body: {
        "start_date": "YYYY-MM-DD",
        "business_days": 10,
        "jurisdiction": "optional"
    }

    Util para calcular plazos legales que se cuentan en dias habiles.
    """

    def post(self, request):
        """
        Calcula la fecha de vencimiento basada en dias habiles

        Args:
            request: Solicitud con start_date, business_days y jurisdiction

        Returns:
            Response: Resultado del calculo con la fecha de vencimiento
        """
        # Validar los datos de entrada usando el serializador
        serializer = CalculateDeadlineSerializer(data=request.data)

        # raise_exception=True: lanza excepcion si la validacion falla
        # Esto retorna automaticamente un error 400 con los detalles
        serializer.is_valid(raise_exception=True)

        # Extraer los datos validados del serializador
        start_date = serializer.validated_data['start_date']
        business_days = serializer.validated_data['business_days']
        jurisdiction = serializer.validated_data.get('jurisdiction', '')

        # Usar el metodo del modelo HolidayCalendar para calcular la fecha
        # Este metodo suma dias habiles saltando fines de semana y festivos
        due_date = HolidayCalendar.add_business_days(start_date, business_days, jurisdiction)

        # Construir el diccionario de resultado
        result = {
            'start_date': start_date,        # Fecha de inicio proporcionada
            'business_days': business_days,  # Dias habiles solicitados
            'due_date': due_date,            # Fecha de vencimiento calculada
            'jurisdiction': jurisdiction,    # Jurisdiccion utilizada
        }

        # Retornar el resultado serializado
        return Response(DeadlineCalculationResultSerializer(result).data)


class HolidayCalendarListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear dias festivos

    Operaciones HTTP:
        - GET: Lista todos los dias festivos con filtrado
        - POST: Crea un nuevo dia festivo

    Filtros disponibles:
        - year: Filtrar por anio
        - jurisdiction: Filtrar por jurisdiccion
        - is_national: Filtrar festivos nacionales/locales
    """

    # Queryset base: todos los festivos
    queryset = HolidayCalendar.objects.all()

    # Serializador para lectura y escritura
    serializer_class = HolidayCalendarSerializer

    # Backend de filtrado
    filter_backends = [DjangoFilterBackend]

    # Campos disponibles para filtrado
    filterset_fields = ['year', 'jurisdiction', 'is_national']


class HolidayCalendarDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un festivo especifico

    Operaciones HTTP:
        - GET: Obtiene los detalles del festivo
        - PUT/PATCH: Actualiza el festivo
        - DELETE: Elimina el festivo
    """

    # Queryset base: todos los festivos
    queryset = HolidayCalendar.objects.all()

    # Serializador para operaciones
    serializer_class = HolidayCalendarSerializer

    # Campo para identificar el festivo en la URL
    lookup_field = 'id'


class CheckBusinessDayView(APIView):
    """
    Vista para verificar si una fecha es dia habil

    Comprueba si una fecha especifica es dia habil, festivo
    o fin de semana para una jurisdiccion dada.

    Endpoint: GET /holidays/check-business-day/?date=YYYY-MM-DD&jurisdiction=optional

    Retorna informacion detallada sobre el tipo de dia.
    """

    def get(self, request):
        """
        Verifica el tipo de dia para una fecha especifica

        Args:
            request: Solicitud con parametros 'date' y 'jurisdiction' opcionales

        Returns:
            Response: Informacion sobre si es dia habil, festivo o fin de semana
        """
        # Obtener el parametro de fecha del query string
        check_date_str = request.query_params.get('date')

        # Obtener la jurisdiccion (opcional, default cadena vacia)
        jurisdiction = request.query_params.get('jurisdiction', '')

        # Validar que se proporciono la fecha
        if not check_date_str:
            return Response(
                {'error': 'date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Intentar parsear la fecha en formato YYYY-MM-DD
            check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
        except ValueError:
            # Si el formato es invalido, retornar error
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar si es dia habil usando el metodo del modelo
        is_business = HolidayCalendar.is_business_day(check_date, jurisdiction)

        # Verificar si es festivo usando el metodo del modelo
        is_holiday = HolidayCalendar.is_holiday(check_date, jurisdiction)

        # Construir y retornar la respuesta con toda la informacion
        return Response({
            'date': check_date,                    # Fecha verificada
            'is_business_day': is_business,        # Es dia habil?
            'is_holiday': is_holiday,              # Es festivo?
            'is_weekend': check_date.weekday() >= 5,  # Es fin de semana?
        })


# ============================================================================
# VISTAS DE NOTIFICACIONES
# Endpoints para procesamiento y envio de notificaciones automaticas
# ============================================================================

class ProcessEventRemindersView(APIView):
    """
    Vista para procesar recordatorios de eventos

    Esta vista procesa y envia recordatorios para eventos proximos
    a todos los asistentes configurados.

    Endpoint: POST /notifications/process-events/

    Uso: Llamado periodicamente por un cron job o tarea programada
    cada 5-15 minutos para enviar recordatorios oportunos.
    """

    def post(self, request):
        """
        Procesa y envia recordatorios de eventos proximos

        Returns:
            Response: Resumen del procesamiento
        """
        from .notifications import process_event_reminders

        results = process_event_reminders()

        return Response({
            'message': 'Recordatorios de eventos procesados',
            'events_processed': results.get('events_processed', 0),
            'notifications_sent': results.get('notifications_sent', 0),
            'errors': results.get('errors', [])
        })


class ProcessDeadlineRemindersView(APIView):
    """
    Vista para procesar recordatorios de plazos

    Esta vista procesa y envia recordatorios para plazos
    proximos a vencer o ya vencidos.

    Endpoint: POST /notifications/process-deadlines/

    Uso: Llamado diariamente por un cron job para enviar
    alertas de plazos a los usuarios asignados.
    """

    def post(self, request):
        """
        Procesa y envia recordatorios de plazos

        Returns:
            Response: Resumen del procesamiento
        """
        from .notifications import process_deadline_reminders

        results = process_deadline_reminders()

        return Response({
            'message': 'Recordatorios de plazos procesados',
            'deadlines_processed': results.get('deadlines_processed', 0),
            'notifications_sent': results.get('notifications_sent', 0),
            'errors': results.get('errors', [])
        })


class CheckOverdueDeadlinesView(APIView):
    """
    Vista para verificar y actualizar plazos vencidos

    Esta vista verifica todos los plazos pendientes con fecha
    de vencimiento pasada y actualiza su estado a 'missed'.

    Endpoint: POST /notifications/check-overdue/

    Uso: Llamado diariamente al inicio del dia para mantener
    los estados de plazos actualizados.
    """

    def post(self, request):
        """
        Verifica y actualiza plazos vencidos

        Returns:
            Response: Resumen de la verificacion
        """
        from .notifications import check_and_update_overdue_deadlines

        results = check_and_update_overdue_deadlines()

        return Response({
            'message': 'Verificacion de plazos vencidos completada',
            'checked': results.get('checked', 0),
            'updated_to_missed': results.get('updated_to_missed', 0),
            'errors': results.get('errors', [])
        })


class SendEventNotificationView(APIView):
    """
    Vista para enviar notificacion manual de evento

    Permite enviar una notificacion inmediata sobre un evento
    especifico a todos sus asistentes.

    Endpoint: POST /events/<uuid:id>/notify/
    """

    def post(self, request, id):
        """
        Envia notificacion de un evento especifico

        Args:
            request: Solicitud HTTP
            id: UUID del evento

        Returns:
            Response: Resultado del envio
        """
        from .notifications import send_event_reminder

        try:
            event = Event.objects.get(id=id)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Evento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        notifications_sent = 0
        errors = []

        # Enviar notificacion a cada asistente
        for attendee_id in event.attendees:
            user_info = {
                'id': attendee_id,
                'name': 'Usuario',
                'email': None
            }
            result = send_event_reminder(event, user_info)
            if 'error' not in result:
                notifications_sent += 1
            else:
                errors.append(result['error'])

        return Response({
            'message': 'Notificaciones enviadas',
            'event_id': str(event.id),
            'notifications_sent': notifications_sent,
            'errors': errors
        })


class SendDeadlineNotificationView(APIView):
    """
    Vista para enviar notificacion manual de plazo

    Permite enviar una notificacion inmediata sobre un plazo
    especifico al usuario asignado.

    Endpoint: POST /deadlines/<uuid:id>/notify/
    """

    def post(self, request, id):
        """
        Envia notificacion de un plazo especifico

        Args:
            request: Solicitud HTTP
            id: UUID del plazo

        Returns:
            Response: Resultado del envio
        """
        from .notifications import send_deadline_reminder

        try:
            deadline = Deadline.objects.get(id=id)
        except Deadline.DoesNotExist:
            return Response(
                {'error': 'Plazo no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not deadline.assigned_to_id:
            return Response(
                {'error': 'El plazo no tiene usuario asignado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = {
            'id': str(deadline.assigned_to_id),
            'name': deadline.assigned_to_name or 'Usuario',
            'email': None
        }

        is_overdue = deadline.is_overdue
        result = send_deadline_reminder(deadline, user_info, is_overdue)

        if 'error' in result:
            return Response(
                {'error': result['error']},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'message': 'Notificacion enviada',
            'deadline_id': str(deadline.id),
            'result': result
        })
