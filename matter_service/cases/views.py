"""
Modulo de Vistas del Servicio de Casos Legales (Matter Service)

Este archivo contiene todas las vistas (views) de la API REST para el manejo de casos legales.
Las vistas utilizan Django REST Framework para proporcionar endpoints CRUD y funcionalidades
adicionales como filtrado, busqueda y estadisticas.

Vistas principales incluidas:
- CaseListCreateView: Listar y crear casos
- CaseDetailView: Ver, actualizar y eliminar un caso especifico
- CaseByNumberView: Buscar caso por numero de expediente
- CaseStatisticsView: Obtener estadisticas de casos
- Vistas para Partes, Fechas, Notas y Tareas de casos

El modulo implementa control de acceso basado en roles (RBAC) para filtrar
los casos segun los permisos del usuario autenticado.

Autor: Equipo de Desarrollo LegalFlow
"""

# Importacion de clases genericas de Django REST Framework
# - generics: Proporciona vistas basadas en clases para operaciones CRUD comunes
# - status: Codigos de estado HTTP estandar (200, 201, 404, etc.)
# - filters: Backends de filtrado para busqueda y ordenamiento
from rest_framework import generics, status, filters

# Clase Response para construir respuestas HTTP personalizadas
from rest_framework.response import Response

# Clase base APIView para crear vistas personalizadas con control total
from rest_framework.views import APIView

# Backend de filtrado de django-filters para filtros avanzados
from django_filters.rest_framework import DjangoFilterBackend

# Funciones de agregacion y objetos Q para consultas complejas
# - Count: Cuenta registros en consultas de agregacion
# - Q: Permite construir consultas OR y AND complejas
from django.db.models import Count, Q

# Utilidades de zona horaria de Django
from django.utils import timezone

# Importacion de los modelos de la aplicacion
from .models import Case, CaseParty, CaseDate, CaseNote, CaseTask

# Importacion de todos los serializadores necesarios
# Cada serializador transforma objetos Python a JSON y viceversa
from .serializers import (
    CaseListSerializer,        # Serializador para listado de casos (datos minimos)
    CaseDetailSerializer,      # Serializador para detalle de caso (datos completos)
    CaseCreateSerializer,      # Serializador para crear nuevos casos
    CaseUpdateSerializer,      # Serializador para actualizar casos existentes
    CasePartySerializer,       # Serializador para partes del caso
    CaseDateSerializer,        # Serializador para fechas del caso
    CaseNoteSerializer,        # Serializador para notas del caso
    CaseTaskSerializer,        # Serializador para tareas del caso
    CaseStatisticsSerializer,  # Serializador para estadisticas
)

# Importacion del filtro personalizado para casos
from .filters import CaseFilter

# Importacion del modulo de notificaciones
from .notifications import (
    send_case_created_notification,
    send_case_status_changed_notification,
)


class CaseListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todos los casos y crear nuevos casos.

    Esta vista hereda de ListCreateAPIView que proporciona:
    - GET: Lista todos los casos con paginacion, filtrado y busqueda
    - POST: Crea un nuevo caso

    Los casos se filtran automaticamente segun el rol del usuario:
    - Administradores y socios: Ven todos los casos
    - Clientes: Solo ven sus propios casos
    - Abogados asociados y paralegales: Solo ven casos asignados

    Atributos de clase:
        queryset: Conjunto de datos base (todos los casos)
        filter_backends: Lista de backends de filtrado habilitados
        filterset_class: Clase de filtro personalizada
        search_fields: Campos habilitados para busqueda de texto
        ordering_fields: Campos por los que se puede ordenar
        ordering: Ordenamiento predeterminado
    """

    # Queryset base - obtiene todos los casos de la base de datos
    queryset = Case.objects.all()

    # Backends de filtrado habilitados para esta vista
    # - DjangoFilterBackend: Permite filtrar por campos especificos (ej: ?status=active)
    # - SearchFilter: Permite busqueda de texto libre (ej: ?search=demanda)
    # - OrderingFilter: Permite ordenar resultados (ej: ?ordering=-created_at)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Clase de filtro personalizada definida en filters.py
    filterset_class = CaseFilter

    # Campos en los que se puede buscar texto
    # La busqueda es case-insensitive y busca coincidencias parciales
    search_fields = ['case_number', 'title', 'client_name', 'court']

    # Campos por los cuales se pueden ordenar los resultados
    ordering_fields = ['created_at', 'opened_date', 'case_number', 'title', 'status', 'priority']

    # Ordenamiento predeterminado (mas reciente primero)
    ordering = ['-created_at']

    def get_serializer_class(self):
        """
        Selecciona el serializador apropiado segun el metodo HTTP.

        Para POST (crear) usa CaseCreateSerializer con campos de entrada.
        Para GET (listar) usa CaseListSerializer con campos de salida minimos.

        Returns:
            class: Clase del serializador a utilizar
        """
        # Si el metodo es POST, usar el serializador de creacion
        if self.request.method == 'POST':
            return CaseCreateSerializer
        # Para GET y otros metodos, usar el serializador de lista
        return CaseListSerializer

    def get_queryset(self):
        """
        Filtra el queryset base segun los permisos del usuario.

        Implementa control de acceso basado en roles (RBAC):
        - admin/partner: Acceso completo a todos los casos
        - client: Solo ve sus propios casos (filtro por client_id)
        - associate/paralegal: Ve casos donde es abogado principal,
          esta asignado, o creo el caso

        Returns:
            QuerySet: Queryset filtrado segun permisos del usuario
        """
        # Obtener el queryset base de la clase padre
        queryset = super().get_queryset()

        # Obtener el usuario autenticado de la solicitud
        user = self.request.user

        # Filtrar segun el rol del usuario
        if user.role == 'client':
            # Los clientes solo ven sus propios casos
            queryset = queryset.filter(client_id=user.id)
        elif user.role not in ['admin', 'partner']:
            # Abogados asociados y paralegales ven solo casos asignados
            # Se usa Q objects para crear una consulta OR
            queryset = queryset.filter(
                Q(lead_attorney_id=user.id) |                    # Es abogado principal
                Q(assigned_attorneys__contains=[str(user.id)]) | # Esta en lista de asignados
                Q(created_by_id=user.id)                         # Creo el caso
            )

        # Retornar el queryset filtrado
        return queryset

    def perform_create(self, serializer):
        """
        Logica personalizada al crear un caso.

        Guarda el caso y envia notificacion al cliente.

        Args:
            serializer: Serializador con datos validados
        """
        # Guardar el caso
        case = serializer.save()

        # Enviar notificacion al cliente
        send_case_created_notification(case)


class CaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un caso especifico.

    Esta vista hereda de RetrieveUpdateDestroyAPIView que proporciona:
    - GET: Obtiene los detalles completos de un caso
    - PUT/PATCH: Actualiza un caso existente
    - DELETE: Elimina (archiva) un caso

    Nota: La eliminacion es "soft delete" - cambia el estado a 'archived'
    en lugar de eliminar fisicamente el registro.

    Atributos de clase:
        queryset: Conjunto de datos base
        lookup_field: Campo usado para buscar el caso (UUID)
    """

    # Queryset base con todos los casos
    queryset = Case.objects.all()

    # Campo para buscar el caso - por defecto busca por 'id' (UUID)
    lookup_field = 'id'

    def get_serializer_class(self):
        """
        Selecciona el serializador segun el metodo HTTP.

        PUT/PATCH usan CaseUpdateSerializer para validar campos actualizables.
        GET usa CaseDetailSerializer para mostrar informacion completa.

        Returns:
            class: Clase del serializador a utilizar
        """
        # Para actualizaciones usar el serializador de actualizacion
        if self.request.method in ['PUT', 'PATCH']:
            return CaseUpdateSerializer
        # Para lectura usar el serializador de detalle completo
        return CaseDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Implementa eliminacion logica (soft delete) del caso.

        En lugar de eliminar fisicamente el registro de la base de datos,
        cambia el estado del caso a 'archived'. Esto preserva los datos
        historicos mientras oculta el caso de las vistas normales.

        Args:
            request: Objeto de solicitud HTTP
            *args: Argumentos posicionales adicionales
            **kwargs: Argumentos de palabra clave adicionales

        Returns:
            Response: Respuesta JSON con mensaje de confirmacion
        """
        # Obtener el objeto caso usando el metodo heredado
        case = self.get_object()

        # Cambiar el estado a 'archived' en lugar de eliminar
        case.status = 'archived'

        # Guardar los cambios en la base de datos
        case.save()

        # Retornar respuesta de exito con mensaje en espanol
        return Response({'message': 'Caso archivado exitosamente.'})

    def perform_update(self, serializer):
        """
        Logica personalizada al actualizar un caso.

        Detecta cambios de estado para enviar notificaciones al cliente.

        Args:
            serializer: Serializador con datos validados
        """
        # Obtener el estado anterior
        old_status = self.get_object().status

        # Guardar los cambios
        case = serializer.save()

        # Si el estado cambio, enviar notificacion
        if old_status != case.status:
            send_case_status_changed_notification(case, old_status, case.status)


class CaseByNumberView(generics.RetrieveAPIView):
    """
    Vista para obtener un caso por su numero de expediente.

    Esta vista permite buscar un caso usando el numero de caso
    (ej: LF-2024-00001) en lugar del UUID, lo cual es mas
    conveniente para usuarios finales.

    Atributos de clase:
        queryset: Conjunto de datos base
        serializer_class: Serializador para la respuesta
        lookup_field: Campo de busqueda (case_number)
    """

    # Queryset base con todos los casos
    queryset = Case.objects.all()

    # Usar serializador de detalle para mostrar informacion completa
    serializer_class = CaseDetailSerializer

    # Buscar por el campo case_number en lugar de id
    lookup_field = 'case_number'


class CaseStatisticsView(APIView):
    """
    Vista para obtener estadisticas de casos.

    Esta vista calcula y retorna metricas agregadas sobre los casos,
    incluyendo totales por estado, tipo y prioridad. Las estadisticas
    se filtran segun los permisos del usuario.

    Metricas incluidas:
    - Total de casos
    - Casos activos, pendientes y cerrados
    - Distribucion por tipo de caso
    - Distribucion por prioridad
    """

    def get(self, request):
        """
        Maneja solicitudes GET para obtener estadisticas.

        Calcula las estadisticas sobre el conjunto de casos
        que el usuario tiene permiso de ver.

        Args:
            request: Objeto de solicitud HTTP con usuario autenticado

        Returns:
            Response: Respuesta JSON con las estadisticas calculadas
        """
        # Obtener el usuario autenticado
        user = request.user

        # Comenzar con todos los casos
        queryset = Case.objects.all()

        # Filtrar segun el rol del usuario (misma logica que CaseListCreateView)
        if user.role == 'client':
            # Clientes solo ven estadisticas de sus propios casos
            queryset = queryset.filter(client_id=user.id)
        elif user.role not in ['admin', 'partner']:
            # Abogados y paralegales ven estadisticas de casos asignados
            queryset = queryset.filter(
                Q(lead_attorney_id=user.id) |
                Q(assigned_attorneys__contains=[str(user.id)]) |
                Q(created_by_id=user.id)
            )

        # Construir diccionario con todas las estadisticas
        stats = {
            # Contar total de casos
            'total_cases': queryset.count(),

            # Contar casos por cada estado individual
            'active_cases': queryset.filter(status='active').count(),
            'pending_cases': queryset.filter(status='pending').count(),
            'closed_cases': queryset.filter(status='closed').count(),

            # Agrupar y contar por tipo de caso
            # values() agrupa por el campo, annotate() cuenta cada grupo
            # values_list() extrae pares (tipo, conteo), dict() los convierte
            'by_type': dict(queryset.values('case_type').annotate(count=Count('id')).values_list('case_type', 'count')),

            # Agrupar y contar por prioridad
            'by_priority': dict(queryset.values('priority').annotate(count=Count('id')).values_list('priority', 'count')),
        }

        # Serializar las estadisticas para validacion y formato
        serializer = CaseStatisticsSerializer(stats)

        # Retornar las estadisticas serializadas
        return Response(serializer.data)


# ============================================================================
# VISTAS DE PARTES DEL CASO (CaseParty Views)
# ============================================================================

class CasePartyListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear partes asociadas a un caso.

    Maneja las partes involucradas en un caso especifico (demandantes,
    demandados, testigos, etc.). El caso se identifica por el UUID
    en la URL.

    Endpoints:
    - GET /cases/{case_id}/parties/ - Lista todas las partes del caso
    - POST /cases/{case_id}/parties/ - Crea una nueva parte
    """

    # Serializador para partes del caso
    serializer_class = CasePartySerializer

    def get_queryset(self):
        """
        Filtra las partes para mostrar solo las del caso especificado.

        El case_id se obtiene de los parametros de la URL (kwargs).

        Returns:
            QuerySet: Partes filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Filtrar partes que pertenecen a este caso
        return CaseParty.objects.filter(case_id=case_id)

    def perform_create(self, serializer):
        """
        Crea una nueva parte asociandola al caso especificado.

        Este metodo se llama despues de validar los datos del serializador.
        Obtiene el caso y lo pasa al serializador para crear la relacion.

        Args:
            serializer: Instancia del serializador con datos validados
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Obtener el objeto Case de la base de datos
        case = Case.objects.get(id=case_id)

        # Guardar la nueva parte asociandola al caso
        serializer.save(case=case)


class CasePartyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar una parte especifica.

    Permite operaciones CRUD sobre una parte individual de un caso.

    Endpoints:
    - GET /cases/{case_id}/parties/{id}/ - Ver detalle de la parte
    - PUT/PATCH /cases/{case_id}/parties/{id}/ - Actualizar la parte
    - DELETE /cases/{case_id}/parties/{id}/ - Eliminar la parte
    """

    # Serializador para partes del caso
    serializer_class = CasePartySerializer

    # Campo de busqueda para la parte individual
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra las partes por el caso especificado en la URL.

        Asegura que solo se puedan acceder partes del caso correcto.

        Returns:
            QuerySet: Partes filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Retornar partes filtradas por caso
        return CaseParty.objects.filter(case_id=case_id)


# ============================================================================
# VISTAS DE FECHAS DEL CASO (CaseDate Views)
# ============================================================================

class CaseDateListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear fechas importantes de un caso.

    Maneja eventos y fechas clave como audiencias, plazos,
    juicios, reuniones, etc.

    Endpoints:
    - GET /cases/{case_id}/dates/ - Lista todas las fechas del caso
    - POST /cases/{case_id}/dates/ - Crea una nueva fecha/evento
    """

    # Serializador para fechas del caso
    serializer_class = CaseDateSerializer

    def get_queryset(self):
        """
        Filtra las fechas para mostrar solo las del caso especificado.

        Returns:
            QuerySet: Fechas filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Filtrar fechas que pertenecen a este caso
        return CaseDate.objects.filter(case_id=case_id)

    def perform_create(self, serializer):
        """
        Crea una nueva fecha asociandola al caso especificado.

        Args:
            serializer: Instancia del serializador con datos validados
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Obtener el objeto Case
        case = Case.objects.get(id=case_id)

        # Guardar la nueva fecha asociandola al caso
        serializer.save(case=case)


class CaseDateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar una fecha especifica.

    Endpoints:
    - GET /cases/{case_id}/dates/{id}/ - Ver detalle de la fecha
    - PUT/PATCH /cases/{case_id}/dates/{id}/ - Actualizar la fecha
    - DELETE /cases/{case_id}/dates/{id}/ - Eliminar la fecha
    """

    # Serializador para fechas del caso
    serializer_class = CaseDateSerializer

    # Campo de busqueda
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra las fechas por el caso especificado.

        Returns:
            QuerySet: Fechas filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Retornar fechas filtradas por caso
        return CaseDate.objects.filter(case_id=case_id)


# ============================================================================
# VISTAS DE NOTAS DEL CASO (CaseNote Views)
# ============================================================================

class CaseNoteListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear notas de un caso.

    Las notas pueden ser publicas o privadas. Las notas privadas
    solo son visibles para su autor.

    Endpoints:
    - GET /cases/{case_id}/notes/ - Lista notas (respetando privacidad)
    - POST /cases/{case_id}/notes/ - Crea una nueva nota
    """

    # Serializador para notas del caso
    serializer_class = CaseNoteSerializer

    def get_queryset(self):
        """
        Filtra las notas respetando la privacidad.

        Muestra todas las notas publicas mas las notas privadas
        que pertenecen al usuario actual.

        Returns:
            QuerySet: Notas filtradas por case_id y privacidad
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Obtener el usuario autenticado
        user = self.request.user

        # Obtener todas las notas del caso
        queryset = CaseNote.objects.filter(case_id=case_id)

        # Filtrar para mostrar:
        # - Notas publicas (is_private=False), O
        # - Notas privadas del usuario actual (author_id=user.id)
        queryset = queryset.filter(
            Q(is_private=False) | Q(author_id=user.id)
        )

        # Retornar el queryset filtrado
        return queryset

    def perform_create(self, serializer):
        """
        Crea una nueva nota con los datos del autor automaticamente.

        Asigna automaticamente el ID y nombre del autor basandose
        en el usuario autenticado.

        Args:
            serializer: Instancia del serializador con datos validados
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Obtener el objeto Case
        case = Case.objects.get(id=case_id)

        # Obtener el usuario autenticado
        user = self.request.user

        # Guardar la nota con datos del autor
        # getattr obtiene el email del usuario o 'Unknown' si no existe
        serializer.save(
            case=case,
            author_id=user.id,
            author_name=getattr(user, 'email', 'Unknown')
        )


class CaseNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar una nota especifica.

    Endpoints:
    - GET /cases/{case_id}/notes/{id}/ - Ver detalle de la nota
    - PUT/PATCH /cases/{case_id}/notes/{id}/ - Actualizar la nota
    - DELETE /cases/{case_id}/notes/{id}/ - Eliminar la nota
    """

    # Serializador para notas del caso
    serializer_class = CaseNoteSerializer

    # Campo de busqueda
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra las notas por el caso especificado.

        Returns:
            QuerySet: Notas filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Retornar notas filtradas por caso
        return CaseNote.objects.filter(case_id=case_id)


# ============================================================================
# VISTAS DE TAREAS DEL CASO (CaseTask Views)
# ============================================================================

class CaseTaskListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear tareas de un caso.

    Incluye filtrado por estado, prioridad y usuario asignado,
    asi como ordenamiento por fecha de vencimiento y prioridad.

    Endpoints:
    - GET /cases/{case_id}/tasks/ - Lista tareas con filtros
    - POST /cases/{case_id}/tasks/ - Crea una nueva tarea
    """

    # Serializador para tareas del caso
    serializer_class = CaseTaskSerializer

    # Backends de filtrado habilitados
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    # Campos habilitados para filtrado directo
    # Permite: ?status=pending&priority=high&assigned_to_id={uuid}
    filterset_fields = ['status', 'priority', 'assigned_to_id']

    # Campos habilitados para ordenamiento
    ordering_fields = ['due_date', 'priority', 'created_at']

    # Ordenamiento predeterminado: por fecha de vencimiento, luego por prioridad
    ordering = ['due_date', '-priority']

    def get_queryset(self):
        """
        Filtra las tareas para mostrar solo las del caso especificado.

        Returns:
            QuerySet: Tareas filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Filtrar tareas del caso
        return CaseTask.objects.filter(case_id=case_id)

    def perform_create(self, serializer):
        """
        Crea una nueva tarea asociandola al caso y al creador.

        Asigna automaticamente el ID del usuario que crea la tarea.

        Args:
            serializer: Instancia del serializador con datos validados
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Obtener el objeto Case
        case = Case.objects.get(id=case_id)

        # Obtener el usuario autenticado
        user = self.request.user

        # Guardar la tarea con el caso y el ID del creador
        serializer.save(case=case, created_by_id=user.id)


class CaseTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar una tarea especifica.

    Incluye logica especial para marcar automaticamente la fecha
    de completado cuando el estado cambia a 'completed'.

    Endpoints:
    - GET /cases/{case_id}/tasks/{id}/ - Ver detalle de la tarea
    - PUT/PATCH /cases/{case_id}/tasks/{id}/ - Actualizar la tarea
    - DELETE /cases/{case_id}/tasks/{id}/ - Eliminar la tarea
    """

    # Serializador para tareas del caso
    serializer_class = CaseTaskSerializer

    # Campo de busqueda
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra las tareas por el caso especificado.

        Returns:
            QuerySet: Tareas filtradas por case_id
        """
        # Obtener el ID del caso desde la URL
        case_id = self.kwargs['case_id']

        # Retornar tareas filtradas por caso
        return CaseTask.objects.filter(case_id=case_id)

    def perform_update(self, serializer):
        """
        Actualiza una tarea con logica especial para completado.

        Si el estado cambia a 'completed', automaticamente establece
        la fecha y hora de completado (completed_at) al momento actual.

        Args:
            serializer: Instancia del serializador con datos validados
        """
        # Verificar si el nuevo estado es 'completed'
        if serializer.validated_data.get('status') == 'completed':
            # Guardar con la fecha de completado actual
            serializer.save(completed_at=timezone.now())
        else:
            # Guardar normalmente sin modificar completed_at
            serializer.save()


class TaskListView(generics.ListAPIView):
    """
    Vista para listar todas las tareas asignadas al usuario actual.

    Esta vista muestra las tareas del usuario a traves de todos
    los casos, permitiendo ver su carga de trabajo completa.

    Endpoints:
    - GET /tasks/ - Lista tareas asignadas al usuario autenticado
    """

    # Serializador para tareas del caso
    serializer_class = CaseTaskSerializer

    # Backends de filtrado habilitados
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    # Campos habilitados para filtrado
    filterset_fields = ['status', 'priority']

    # Campos habilitados para ordenamiento
    ordering_fields = ['due_date', 'priority', 'created_at']

    # Ordenamiento predeterminado
    ordering = ['due_date', '-priority']

    def get_queryset(self):
        """
        Obtiene las tareas asignadas al usuario autenticado.

        Filtra todas las tareas donde assigned_to_id coincide
        con el ID del usuario actual.

        Returns:
            QuerySet: Tareas asignadas al usuario actual
        """
        # Obtener el usuario autenticado
        user = self.request.user

        # Retornar tareas asignadas a este usuario
        return CaseTask.objects.filter(assigned_to_id=user.id)


class ClientCasesView(generics.ListAPIView):
    """
    Vista para listar todos los casos de un cliente especifico.

    Permite a los administradores y abogados ver todos los casos
    asociados a un cliente particular.

    Endpoints:
    - GET /clients/{client_id}/cases/ - Lista casos del cliente
    """

    # Serializador de lista para mostrar informacion resumida
    serializer_class = CaseListSerializer

    def get_queryset(self):
        """
        Filtra los casos por el cliente especificado en la URL.

        El client_id se obtiene de los parametros de la URL.

        Returns:
            QuerySet: Casos filtrados por client_id
        """
        # Obtener el ID del cliente desde la URL
        client_id = self.kwargs['client_id']

        # Retornar casos donde client_id coincide
        return Case.objects.filter(client_id=client_id)
