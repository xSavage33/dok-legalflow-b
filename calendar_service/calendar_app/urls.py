"""
urls.py - Configuracion de rutas URL del servicio de calendario

Este archivo define todas las rutas URL disponibles en la API del
servicio de calendario. Cada ruta mapea una URL especifica a una
vista que maneja la solicitud.

Estructura de las rutas:

    Eventos (/events/):
        - GET/POST /events/ - Listar/Crear eventos
        - GET /events/upcoming/ - Eventos proximos
        - GET /events/today/ - Eventos de hoy
        - GET/PUT/PATCH/DELETE /events/<uuid:id>/ - Detalle de evento

    Plazos (/deadlines/):
        - GET/POST /deadlines/ - Listar/Crear plazos
        - GET /deadlines/upcoming/ - Plazos proximos
        - GET /deadlines/overdue/ - Plazos vencidos
        - GET /deadlines/my/ - Mis plazos
        - POST /deadlines/calculate/ - Calcular fecha de vencimiento
        - GET/PUT/PATCH/DELETE /deadlines/<uuid:id>/ - Detalle de plazo
        - POST /deadlines/<uuid:id>/complete/ - Completar plazo
        - POST /deadlines/<uuid:id>/extend/ - Extender plazo

    Festivos (/holidays/):
        - GET/POST /holidays/ - Listar/Crear festivos
        - GET/PUT/PATCH/DELETE /holidays/<uuid:id>/ - Detalle de festivo
        - GET /holidays/check-business-day/ - Verificar dia habil

Autor: Equipo LegalFlow
Fecha de creacion: 2024
"""

# Importacion de la funcion path de Django para definir rutas URL
# path() es la forma moderna de definir URLs en Django (reemplaza a url())
from django.urls import path

# Importacion del modulo views que contiene todas las vistas de la aplicacion
# El punto (.) indica que es una importacion relativa del mismo paquete
from . import views

# Lista de patrones de URL para esta aplicacion
# Django itera sobre esta lista para encontrar coincidencias con las URLs solicitadas
urlpatterns = [
    # ============================================================================
    # RUTAS DE EVENTOS (Events)
    # Gestionan los eventos del calendario como audiencias, reuniones, etc.
    # ============================================================================

    # Ruta para listar todos los eventos o crear uno nuevo
    # GET: Retorna lista de eventos (con filtrado, busqueda y paginacion)
    # POST: Crea un nuevo evento
    # URL: /api/calendar/events/
    path(
        'events/',                              # Patron de URL
        views.EventListCreateView.as_view(),    # Vista a ejecutar (convertida a funcion)
        name='event_list_create'                # Nombre para referencia inversa
    ),

    # Ruta para obtener eventos proximos
    # GET: Retorna eventos dentro de los proximos N dias (default 7)
    # Parametro opcional: ?days=14
    # URL: /api/calendar/events/upcoming/
    path(
        'events/upcoming/',
        views.UpcomingEventsView.as_view(),
        name='upcoming_events'
    ),

    # Ruta para obtener eventos del dia actual
    # GET: Retorna todos los eventos programados para hoy
    # URL: /api/calendar/events/today/
    path(
        'events/today/',
        views.TodayEventsView.as_view(),
        name='today_events'
    ),

    # Ruta para operaciones sobre un evento especifico
    # GET: Obtiene los detalles del evento
    # PUT: Actualiza todos los campos del evento
    # PATCH: Actualiza parcialmente el evento
    # DELETE: Elimina el evento
    # <uuid:id>: Captura el UUID del evento de la URL
    # URL: /api/calendar/events/550e8400-e29b-41d4-a716-446655440000/
    path(
        'events/<uuid:id>/',
        views.EventDetailView.as_view(),
        name='event_detail'
    ),

    # ============================================================================
    # RUTAS DE PLAZOS (Deadlines)
    # Gestionan los plazos legales con fechas de vencimiento
    # ============================================================================

    # Ruta para listar todos los plazos o crear uno nuevo
    # GET: Retorna lista de plazos (con filtrado por caso, prioridad, estado)
    # POST: Crea un nuevo plazo
    # URL: /api/calendar/deadlines/
    path(
        'deadlines/',
        views.DeadlineListCreateView.as_view(),
        name='deadline_list_create'
    ),

    # Ruta para obtener plazos proximos a vencer
    # GET: Retorna plazos pendientes dentro de los proximos N dias
    # Parametro opcional: ?days=30
    # URL: /api/calendar/deadlines/upcoming/
    path(
        'deadlines/upcoming/',
        views.UpcomingDeadlinesView.as_view(),
        name='upcoming_deadlines'
    ),

    # Ruta para obtener plazos vencidos
    # GET: Retorna plazos pendientes cuya fecha de vencimiento ya paso
    # Util para alertas y seguimiento de incumplimientos
    # URL: /api/calendar/deadlines/overdue/
    path(
        'deadlines/overdue/',
        views.OverdueDeadlinesView.as_view(),
        name='overdue_deadlines'
    ),

    # Ruta para obtener plazos del usuario actual
    # GET: Retorna plazos asignados al usuario autenticado
    # URL: /api/calendar/deadlines/my/
    path(
        'deadlines/my/',
        views.MyDeadlinesView.as_view(),
        name='my_deadlines'
    ),

    # Ruta para calcular fecha de vencimiento
    # POST: Calcula una fecha de vencimiento basada en dias habiles
    # Body: {"start_date": "2024-01-15", "business_days": 10, "jurisdiction": ""}
    # URL: /api/calendar/deadlines/calculate/
    path(
        'deadlines/calculate/',
        views.CalculateDeadlineView.as_view(),
        name='calculate_deadline'
    ),

    # Ruta para operaciones sobre un plazo especifico
    # GET: Obtiene los detalles del plazo
    # PUT: Actualiza todos los campos del plazo
    # PATCH: Actualiza parcialmente el plazo
    # DELETE: Elimina el plazo
    # URL: /api/calendar/deadlines/550e8400-e29b-41d4-a716-446655440000/
    path(
        'deadlines/<uuid:id>/',
        views.DeadlineDetailView.as_view(),
        name='deadline_detail'
    ),

    # Ruta para marcar un plazo como completado
    # POST: Cambia el estado del plazo a 'completed'
    # Registra quien y cuando completo el plazo
    # URL: /api/calendar/deadlines/550e8400-e29b-41d4-a716-446655440000/complete/
    path(
        'deadlines/<uuid:id>/complete/',
        views.CompleteDeadlineView.as_view(),
        name='complete_deadline'
    ),

    # Ruta para extender la fecha de vencimiento de un plazo
    # POST: Cambia la fecha de vencimiento y marca como 'extended'
    # Body: {"new_due_date": "2024-02-15"}
    # URL: /api/calendar/deadlines/550e8400-e29b-41d4-a716-446655440000/extend/
    path(
        'deadlines/<uuid:id>/extend/',
        views.ExtendDeadlineView.as_view(),
        name='extend_deadline'
    ),

    # ============================================================================
    # RUTAS DE FESTIVOS (Holidays)
    # Gestionan el calendario de dias festivos por jurisdiccion
    # ============================================================================

    # Ruta para listar todos los festivos o crear uno nuevo
    # GET: Retorna lista de festivos (filtrable por anio, jurisdiccion)
    # POST: Crea un nuevo dia festivo
    # URL: /api/calendar/holidays/
    path(
        'holidays/',
        views.HolidayCalendarListCreateView.as_view(),
        name='holiday_list_create'
    ),

    # Ruta para operaciones sobre un festivo especifico
    # GET: Obtiene los detalles del festivo
    # PUT: Actualiza el festivo
    # PATCH: Actualiza parcialmente el festivo
    # DELETE: Elimina el festivo
    # URL: /api/calendar/holidays/550e8400-e29b-41d4-a716-446655440000/
    path(
        'holidays/<uuid:id>/',
        views.HolidayCalendarDetailView.as_view(),
        name='holiday_detail'
    ),

    # Ruta para verificar si una fecha es dia habil
    # GET: Verifica si la fecha es dia habil, festivo o fin de semana
    # Parametros: ?date=2024-01-15&jurisdiction=Bogota
    # Retorna: {is_business_day, is_holiday, is_weekend}
    # URL: /api/calendar/holidays/check-business-day/?date=2024-01-15
    path(
        'holidays/check-business-day/',
        views.CheckBusinessDayView.as_view(),
        name='check_business_day'
    ),

    # ============================================================================
    # RUTAS DE NOTIFICACIONES (Notifications)
    # Endpoints internos para procesamiento de notificaciones automaticas
    # ============================================================================

    # Ruta para procesar recordatorios de eventos
    # POST: Procesa y envia recordatorios de eventos proximos
    # Uso: Llamado por un cron job o tarea programada
    # URL: /api/calendar/notifications/process-events/
    path(
        'notifications/process-events/',
        views.ProcessEventRemindersView.as_view(),
        name='process_event_reminders'
    ),

    # Ruta para procesar recordatorios de plazos
    # POST: Procesa y envia recordatorios de plazos proximos/vencidos
    # Uso: Llamado por un cron job o tarea programada
    # URL: /api/calendar/notifications/process-deadlines/
    path(
        'notifications/process-deadlines/',
        views.ProcessDeadlineRemindersView.as_view(),
        name='process_deadline_reminders'
    ),

    # Ruta para verificar y actualizar plazos vencidos
    # POST: Actualiza el estado de plazos vencidos
    # Uso: Llamado diariamente para mantener estados actualizados
    # URL: /api/calendar/notifications/check-overdue/
    path(
        'notifications/check-overdue/',
        views.CheckOverdueDeadlinesView.as_view(),
        name='check_overdue_deadlines'
    ),

    # Ruta para enviar notificacion manual de evento
    # POST: Envia notificacion de un evento especifico
    # URL: /api/calendar/events/<uuid:id>/notify/
    path(
        'events/<uuid:id>/notify/',
        views.SendEventNotificationView.as_view(),
        name='send_event_notification'
    ),

    # Ruta para enviar notificacion manual de plazo
    # POST: Envia notificacion de un plazo especifico
    # URL: /api/calendar/deadlines/<uuid:id>/notify/
    path(
        'deadlines/<uuid:id>/notify/',
        views.SendDeadlineNotificationView.as_view(),
        name='send_deadline_notification'
    ),
]
