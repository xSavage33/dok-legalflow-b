"""
Modulo de Modelos del Servicio de Casos Legales (Matter Service)

Este archivo define los modelos de base de datos para el sistema de gestion de casos legales.
Incluye los siguientes modelos principales:
- Case: Modelo principal que representa un caso/asunto legal
- CaseParty: Partes involucradas en un caso (demandantes, demandados, testigos, etc.)
- CaseDate: Fechas importantes asociadas a un caso (audiencias, plazos, juicios, etc.)
- CaseNote: Notas internas y comentarios sobre un caso
- CaseTask: Tareas asociadas a un caso

Cada modelo utiliza UUID como clave primaria para mayor seguridad y compatibilidad
con arquitecturas de microservicios distribuidos.

Autor: Equipo de Desarrollo LegalFlow
"""

# Importacion del modulo uuid para generar identificadores unicos universales
# UUID se utiliza como clave primaria en todos los modelos para evitar colisiones
# y mejorar la seguridad al no exponer IDs secuenciales
import uuid

# Importacion del modulo de modelos de Django ORM
# Este modulo proporciona las clases base para definir modelos de base de datos
from django.db import models


class Case(models.Model):
    """
    Modelo principal que representa un caso o asunto legal.

    Este modelo almacena toda la informacion relacionada con un caso legal,
    incluyendo datos del cliente, informacion del tribunal, abogados asignados,
    informacion financiera y fechas importantes.

    Atributos:
        id: Identificador unico del caso (UUID)
        case_number: Numero de caso unico generado automaticamente
        title: Titulo descriptivo del caso
        description: Descripcion detallada del caso
        case_type: Tipo de caso (civil, penal, laboral, etc.)
        status: Estado actual del caso (activo, pendiente, cerrado, etc.)
        priority: Prioridad del caso (baja, media, alta, urgente)
        client_id: Referencia al cliente en el servicio IAM
        lead_attorney_id: ID del abogado principal asignado
        billing_type: Tipo de facturacion (por hora, tarifa fija, etc.)
    """

    # Definicion de opciones para el tipo de caso
    # Cada tupla contiene (valor_interno, etiqueta_mostrada)
    CASE_TYPE_CHOICES = [
        ('civil', 'Civil'),                    # Casos de derecho civil
        ('criminal', 'Penal'),                 # Casos de derecho penal/criminal
        ('labor', 'Laboral'),                  # Casos de derecho laboral
        ('commercial', 'Comercial'),           # Casos de derecho comercial
        ('administrative', 'Administrativo'),  # Casos de derecho administrativo
        ('family', 'Familia'),                 # Casos de derecho de familia
        ('constitutional', 'Constitucional'),  # Casos de derecho constitucional
        ('tax', 'Tributario'),                 # Casos de derecho tributario
        ('other', 'Otro'),                     # Otros tipos de casos
    ]

    # Definicion de opciones para el estado del caso
    STATUS_CHOICES = [
        ('active', 'Activo'),       # Caso actualmente en tramite
        ('pending', 'Pendiente'),   # Caso en espera de accion
        ('on_hold', 'En Espera'),   # Caso temporalmente pausado
        ('on_appeal', 'En Apelación'),  # Caso en proceso de apelacion
        ('closed', 'Cerrado'),      # Caso finalizado
        ('archived', 'Archivado'),  # Caso archivado (eliminacion logica)
    ]

    # Definicion de opciones para la prioridad del caso
    PRIORITY_CHOICES = [
        ('low', 'Baja'),        # Prioridad baja - puede esperar
        ('medium', 'Media'),    # Prioridad media - atencion normal
        ('high', 'Alta'),       # Prioridad alta - requiere atencion pronta
        ('urgent', 'Urgente'),  # Prioridad urgente - atencion inmediata
    ]

    # Campo de identificador unico (UUID) como clave primaria
    # primary_key=True indica que este campo es la clave primaria
    # default=uuid.uuid4 genera automaticamente un UUID version 4
    # editable=False impide que el campo sea modificado despues de creado
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Numero de caso unico - se genera automaticamente en el metodo save()
    # unique=True garantiza que no haya duplicados
    case_number = models.CharField(max_length=50, unique=True)

    # Titulo descriptivo del caso
    title = models.CharField(max_length=255)

    # Descripcion detallada del caso - blank=True permite valores vacios
    description = models.TextField(blank=True)

    # Tipo de caso con opciones predefinidas
    case_type = models.CharField(max_length=20, choices=CASE_TYPE_CHOICES)

    # Estado del caso con valor predeterminado 'activo'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Prioridad del caso con valor predeterminado 'media'
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # --- Informacion del cliente ---

    # ID del cliente que referencia al servicio de autenticacion (IAM)
    # db_index=True crea un indice para busquedas rapidas
    client_id = models.UUIDField(db_index=True)

    # Nombre del cliente almacenado localmente para evitar consultas al servicio IAM
    client_name = models.CharField(max_length=255)

    # Correo electronico del cliente - opcional
    client_email = models.EmailField(blank=True)

    # Telefono del cliente - opcional
    client_phone = models.CharField(max_length=20, blank=True)

    # --- Informacion del tribunal ---

    # Jurisdiccion donde se tramita el caso (ej: "Juzgado Civil de Lima")
    jurisdiction = models.CharField(max_length=100, blank=True)

    # Nombre del tribunal o juzgado
    court = models.CharField(max_length=255, blank=True)

    # Nombre del juez asignado al caso
    judge = models.CharField(max_length=255, blank=True)

    # Numero de expediente en el tribunal
    court_case_number = models.CharField(max_length=100, blank=True)

    # --- Abogados asignados ---

    # ID del abogado principal responsable del caso
    # null=True permite valores nulos en la base de datos
    lead_attorney_id = models.UUIDField(db_index=True, null=True, blank=True)

    # Lista de IDs de abogados adicionales asignados al caso
    # JSONField almacena una lista de UUIDs como JSON
    # default=list crea una lista vacia por defecto
    assigned_attorneys = models.JSONField(default=list, blank=True)

    # --- Informacion financiera ---

    # Tipo de facturacion con opciones predefinidas
    billing_type = models.CharField(max_length=20, default='hourly', choices=[
        ('hourly', 'Por Hora'),          # Facturacion por hora trabajada
        ('fixed', 'Tarifa Fija'),        # Tarifa fija acordada
        ('contingency', 'Contingencia'), # Pago basado en resultado (porcentaje)
        ('mixed', 'Mixto'),              # Combinacion de metodos
    ])

    # Valor estimado del caso
    # max_digits=15 permite hasta 15 digitos totales
    # decimal_places=2 permite 2 decimales (centavos)
    estimated_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Monto del anticipo o retenedor pagado por el cliente
    retainer_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # --- Fechas importantes ---

    # Fecha de apertura del caso - obligatoria
    opened_date = models.DateField()

    # Fecha de cierre del caso - se establece cuando el caso se cierra
    closed_date = models.DateField(null=True, blank=True)

    # Fecha limite de prescripcion - importante para no perder plazos legales
    statute_of_limitations = models.DateField(null=True, blank=True)

    # --- Metadatos ---

    # Etiquetas para categorizar y buscar casos
    # Se almacenan como lista JSON (ej: ["urgente", "cliente-vip"])
    tags = models.JSONField(default=list, blank=True)

    # Notas generales sobre el caso
    notes = models.TextField(blank=True)

    # ID del usuario que creo el registro
    created_by_id = models.UUIDField(db_index=True)

    # Fecha y hora de creacion - se establece automaticamente
    # auto_now_add=True establece la fecha al crear el registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha y hora de ultima actualizacion
    # auto_now=True actualiza la fecha cada vez que se guarda
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Clase Meta que define opciones de configuracion del modelo.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'cases'

        # Ordenamiento predeterminado por fecha de creacion descendente
        # El signo menos indica orden descendente (mas reciente primero)
        ordering = ['-created_at']

        # Indices de base de datos para optimizar consultas frecuentes
        indexes = [
            models.Index(fields=['case_number']),  # Indice para buscar por numero de caso
            models.Index(fields=['client_id']),    # Indice para filtrar por cliente
            models.Index(fields=['status']),       # Indice para filtrar por estado
            models.Index(fields=['case_type']),    # Indice para filtrar por tipo
        ]

    def __str__(self):
        """
        Representacion en texto del caso.
        Se utiliza en el panel de administracion y para depuracion.

        Returns:
            str: Cadena con formato "NUMERO_CASO - TITULO"
        """
        return f"{self.case_number} - {self.title}"

    def save(self, *args, **kwargs):
        """
        Metodo personalizado para guardar el caso.
        Genera automaticamente el numero de caso si no existe.

        El formato del numero de caso es: LF-ANIO-NUMERO
        Ejemplo: LF-2024-00001

        Args:
            *args: Argumentos posicionales para el metodo save() padre
            **kwargs: Argumentos de palabra clave para el metodo save() padre
        """
        # Verificar si el caso no tiene numero asignado
        if not self.case_number:
            # Importar datetime para obtener el ano actual
            import datetime

            # Obtener el ano actual
            year = datetime.datetime.now().year

            # Buscar el ultimo caso creado en el ano actual
            # Filtrar por casos cuyo numero comienza con "LF-{ano}"
            # Ordenar descendentemente para obtener el mas reciente
            last_case = Case.objects.filter(
                case_number__startswith=f"LF-{year}"
            ).order_by('-case_number').first()

            # Si existe un caso previo en el ano, incrementar el numero
            if last_case:
                # Extraer el numero del ultimo caso (parte despues del ultimo guion)
                last_num = int(last_case.case_number.split('-')[-1])
                # Incrementar el numero en 1
                new_num = last_num + 1
            else:
                # Si es el primer caso del ano, comenzar en 1
                new_num = 1

            # Generar el numero de caso con formato de 5 digitos
            # :05d formatea el numero con ceros a la izquierda hasta 5 digitos
            self.case_number = f"LF-{year}-{new_num:05d}"

        # Llamar al metodo save() de la clase padre para guardar el registro
        super().save(*args, **kwargs)


class CaseParty(models.Model):
    """
    Modelo que representa las partes involucradas en un caso.

    Una parte puede ser cualquier persona o entidad relacionada con el caso,
    como demandantes, demandados, testigos, peritos, abogados de la contraparte, etc.

    Atributos:
        id: Identificador unico de la parte (UUID)
        case: Referencia al caso al que pertenece
        party_type: Tipo de parte (demandante, demandado, testigo, etc.)
        name: Nombre de la parte
        identification: Documento de identidad (DNI, RUC, etc.)
        email: Correo electronico de contacto
        phone: Telefono de contacto
        address: Direccion
        company: Empresa o entidad a la que pertenece
        notes: Notas adicionales sobre la parte
    """

    # Definicion de opciones para el tipo de parte
    PARTY_TYPE_CHOICES = [
        ('plaintiff', 'Demandante'),       # Persona que inicia la demanda
        ('defendant', 'Demandado'),        # Persona demandada
        ('witness', 'Testigo'),            # Testigo del caso
        ('expert', 'Perito'),              # Experto tecnico o profesional
        ('co_counsel', 'Co-abogado'),      # Abogado que colabora en el caso
        ('opposing_counsel', 'Contraparte'), # Abogado de la parte contraria
        ('third_party', 'Tercero'),        # Tercero interesado en el caso
        ('other', 'Otro'),                 # Otro tipo de parte
    ]

    # Identificador unico como clave primaria
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion de clave foranea con el modelo Case
    # on_delete=models.CASCADE elimina las partes si se elimina el caso
    # related_name='parties' permite acceder desde Case como case.parties.all()
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='parties')

    # Tipo de parte con opciones predefinidas
    party_type = models.CharField(max_length=20, choices=PARTY_TYPE_CHOICES)

    # Nombre completo de la parte
    name = models.CharField(max_length=255)

    # Numero de documento de identidad (DNI, pasaporte, RUC, etc.)
    identification = models.CharField(max_length=50, blank=True)

    # Correo electronico de contacto
    email = models.EmailField(blank=True)

    # Numero de telefono de contacto
    phone = models.CharField(max_length=20, blank=True)

    # Direccion fisica
    address = models.TextField(blank=True)

    # Nombre de la empresa o entidad (si aplica)
    company = models.CharField(max_length=255, blank=True)

    # Notas adicionales sobre la parte
    notes = models.TextField(blank=True)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Configuracion del modelo CaseParty.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'case_parties'

        # Ordenar por tipo de parte y luego por nombre
        ordering = ['party_type', 'name']

        # Nombre plural para el panel de administracion
        verbose_name_plural = 'Case parties'

    def __str__(self):
        """
        Representacion en texto de la parte.

        Returns:
            str: Cadena con formato "TIPO_PARTE: NOMBRE"
        """
        # get_party_type_display() devuelve la etiqueta legible del tipo de parte
        return f"{self.get_party_type_display()}: {self.name}"


class CaseDate(models.Model):
    """
    Modelo que representa fechas importantes asociadas a un caso.

    Este modelo almacena eventos y fechas clave del caso como audiencias,
    plazos, juicios, reuniones, mediaciones, etc.

    Atributos:
        id: Identificador unico de la fecha (UUID)
        case: Referencia al caso al que pertenece
        date_type: Tipo de fecha/evento
        title: Titulo del evento
        description: Descripcion detallada
        date: Fecha del evento
        time: Hora del evento (opcional)
        location: Ubicacion del evento
        is_completed: Indica si el evento ya ocurrio
        reminder_sent: Indica si se envio recordatorio
    """

    # Definicion de opciones para el tipo de fecha/evento
    DATE_TYPE_CHOICES = [
        ('hearing', 'Audiencia'),      # Audiencia judicial
        ('deadline', 'Plazo'),         # Fecha limite o plazo procesal
        ('filing', 'Presentacion'),    # Presentacion de documentos
        ('trial', 'Juicio'),           # Fecha de juicio oral
        ('meeting', 'Reunion'),        # Reunion con cliente o equipo
        ('deposition', 'Deposicion'),  # Declaracion jurada
        ('mediation', 'Mediacion'),    # Sesion de mediacion
        ('arbitration', 'Arbitraje'),  # Sesion de arbitraje
        ('other', 'Otro'),             # Otro tipo de evento
    ]

    # Identificador unico como clave primaria
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el caso
    # related_name='dates' permite acceder como case.dates.all()
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='dates')

    # Tipo de fecha/evento
    date_type = models.CharField(max_length=20, choices=DATE_TYPE_CHOICES)

    # Titulo descriptivo del evento
    title = models.CharField(max_length=255)

    # Descripcion detallada del evento
    description = models.TextField(blank=True)

    # Fecha del evento
    date = models.DateField()

    # Hora del evento (opcional)
    time = models.TimeField(null=True, blank=True)

    # Ubicacion donde se llevara a cabo el evento
    location = models.CharField(max_length=255, blank=True)

    # Indica si el evento ya se completo
    is_completed = models.BooleanField(default=False)

    # Indica si ya se envio el recordatorio automatico
    reminder_sent = models.BooleanField(default=False)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Configuracion del modelo CaseDate.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'case_dates'

        # Ordenar por fecha y hora (eventos mas proximos primero)
        ordering = ['date', 'time']

    def __str__(self):
        """
        Representacion en texto de la fecha del caso.

        Returns:
            str: Cadena con formato "NUMERO_CASO - TITULO (FECHA)"
        """
        return f"{self.case.case_number} - {self.title} ({self.date})"


class CaseNote(models.Model):
    """
    Modelo que representa notas y comentarios internos sobre un caso.

    Las notas pueden ser publicas (visibles para todo el equipo) o privadas
    (solo visibles para el autor). Son utiles para documentar el progreso,
    decisiones importantes o comunicaciones internas.

    Atributos:
        id: Identificador unico de la nota (UUID)
        case: Referencia al caso al que pertenece
        author_id: ID del autor de la nota
        author_name: Nombre del autor (almacenado localmente)
        content: Contenido de la nota
        is_private: Indica si la nota es privada
    """

    # Identificador unico como clave primaria
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el caso
    # related_name='case_notes' para evitar conflicto con el campo 'notes' del modelo Case
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='case_notes')

    # ID del usuario autor de la nota (referencia al servicio IAM)
    author_id = models.UUIDField(db_index=True)

    # Nombre del autor almacenado localmente para evitar consultas al IAM
    author_name = models.CharField(max_length=255)

    # Contenido de la nota
    content = models.TextField()

    # Indica si la nota es privada (solo visible para el autor)
    is_private = models.BooleanField(default=False)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Configuracion del modelo CaseNote.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'case_notes'

        # Ordenar por fecha de creacion descendente (notas mas recientes primero)
        ordering = ['-created_at']

    def __str__(self):
        """
        Representacion en texto de la nota.

        Returns:
            str: Cadena descriptiva de la nota
        """
        return f"Note on {self.case.case_number} by {self.author_name}"


class CaseTask(models.Model):
    """
    Modelo que representa tareas asociadas a un caso.

    Las tareas permiten organizar el trabajo del equipo legal,
    asignar responsabilidades y hacer seguimiento del progreso.

    Atributos:
        id: Identificador unico de la tarea (UUID)
        case: Referencia al caso al que pertenece
        title: Titulo de la tarea
        description: Descripcion detallada
        status: Estado de la tarea (pendiente, en progreso, completada, etc.)
        priority: Prioridad de la tarea
        assigned_to_id: ID del usuario asignado
        assigned_to_name: Nombre del usuario asignado
        due_date: Fecha de vencimiento
        completed_at: Fecha y hora de completado
        created_by_id: ID del usuario que creo la tarea
    """

    # Definicion de opciones para el estado de la tarea
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),       # Tarea sin iniciar
        ('in_progress', 'En Progreso'), # Tarea en curso
        ('completed', 'Completada'),    # Tarea finalizada
        ('cancelled', 'Cancelada'),     # Tarea cancelada
    ]

    # Definicion de opciones para la prioridad de la tarea
    PRIORITY_CHOICES = [
        ('low', 'Baja'),        # Puede esperar
        ('medium', 'Media'),    # Prioridad normal
        ('high', 'Alta'),       # Requiere atencion pronta
        ('urgent', 'Urgente'),  # Requiere atencion inmediata
    ]

    # Identificador unico como clave primaria
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el caso
    # related_name='tasks' permite acceder como case.tasks.all()
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='tasks')

    # Titulo de la tarea
    title = models.CharField(max_length=255)

    # Descripcion detallada de la tarea
    description = models.TextField(blank=True)

    # Estado actual de la tarea con valor predeterminado 'pendiente'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Prioridad de la tarea con valor predeterminado 'media'
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # ID del usuario asignado a la tarea (referencia al servicio IAM)
    assigned_to_id = models.UUIDField(db_index=True, null=True, blank=True)

    # Nombre del usuario asignado (almacenado localmente)
    assigned_to_name = models.CharField(max_length=255, blank=True)

    # Fecha de vencimiento de la tarea
    due_date = models.DateField(null=True, blank=True)

    # Fecha y hora en que se completo la tarea
    completed_at = models.DateTimeField(null=True, blank=True)

    # ID del usuario que creo la tarea
    created_by_id = models.UUIDField(db_index=True)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Configuracion del modelo CaseTask.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'case_tasks'

        # Ordenar por fecha de vencimiento, luego por prioridad (descendente), luego por titulo
        # Las tareas urgentes sin fecha aparecen al final, las tareas con fecha proxima primero
        ordering = ['due_date', '-priority', 'title']

    def __str__(self):
        """
        Representacion en texto de la tarea.

        Returns:
            str: Cadena con formato "NUMERO_CASO - TITULO_TAREA"
        """
        return f"{self.case.case_number} - {self.title}"
