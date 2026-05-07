"""
models.py - Modelos de datos para el Servicio de Documentos

Este archivo define los modelos de Django que representan la estructura de la base de datos
para el sistema de gestion de documentos legales. Incluye:
- Document: Modelo principal para almacenar documentos legales
- DocumentVersion: Historial de versiones de documentos
- DocumentAccessLog: Registro de auditoria de accesos y acciones
- DocumentShare: Permisos de comparticion de documentos
- Folder: Estructura de carpetas para organizar documentos

Autor: Equipo de Desarrollo LegalFlow
"""

# Importacion del modulo uuid para generar identificadores unicos universales
import uuid

# Importacion del modulo os para operaciones del sistema operativo (rutas de archivos)
import os

# Importacion del ORM de Django para definir modelos de base de datos
from django.db import models

# Importacion de la configuracion de Django para acceder a variables de settings
from django.conf import settings

# Importacion de SearchVectorField para busqueda full-text en PostgreSQL
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


def document_upload_path(instance, filename):
    """
    Genera la ruta de subida para documentos.

    Esta funcion determina donde se almacenara el archivo en el sistema de archivos.
    Si el documento esta asociado a un caso, se guarda en una carpeta especifica del caso.
    De lo contrario, se guarda en una carpeta general de documentos.

    Args:
        instance: Instancia del modelo Document que se esta guardando
        filename: Nombre original del archivo subido

    Returns:
        str: Ruta donde se almacenara el archivo
    """
    # Extraer la extension del archivo dividiendo por el punto y tomando el ultimo elemento
    ext = filename.split('.')[-1]

    # Si el documento tiene un caso asociado, guardar en la carpeta del caso
    if instance.case_id:
        # Formato: cases/{id_caso}/documents/{id_documento}.{extension}
        return f"cases/{instance.case_id}/documents/{instance.id}.{ext}"

    # Si no tiene caso asociado, guardar en carpeta general
    # Formato: documents/{id_documento}.{extension}
    return f"documents/{instance.id}.{ext}"


def version_upload_path(instance, filename):
    """
    Genera la ruta de subida para versiones de documentos.

    Las versiones se guardan en una subcarpeta del documento original,
    organizadas por numero de version.

    Args:
        instance: Instancia del modelo DocumentVersion
        filename: Nombre original del archivo

    Returns:
        str: Ruta donde se almacenara la version del archivo
    """
    # Extraer la extension del archivo
    ext = filename.split('.')[-1]

    # Formato: documents/{id_documento}/versions/{numero_version}.{extension}
    return f"documents/{instance.document.id}/versions/{instance.version_number}.{ext}"


class Document(models.Model):
    """
    Modelo principal para documentos legales.

    Este modelo almacena toda la informacion relacionada con un documento legal,
    incluyendo metadatos, informacion de seguridad, y campos de auditoria.

    Attributes:
        id: Identificador unico UUID del documento
        name: Nombre del documento
        description: Descripcion detallada del documento
        category: Categoria del documento (contrato, demanda, etc.)
        status: Estado actual del documento (borrador, aprobado, etc.)
        file: Archivo fisico del documento
        original_filename: Nombre original del archivo subido
        file_size: Tamano del archivo en bytes
        mime_type: Tipo MIME del archivo
        checksum: Hash SHA-256 para verificar integridad
        current_version: Numero de version actual
        case_id: ID del caso legal asociado (opcional)
        parent_document_id: ID del documento padre para documentos vinculados
        is_confidential: Indica si el documento es confidencial
        is_privileged: Indica si tiene privilegio abogado-cliente
        encryption_status: Estado de cifrado del documento
        tags: Etiquetas para clasificacion
        metadata: Metadatos personalizados en formato JSON
        created_by_id: ID del usuario que creo el documento
        created_by_name: Nombre del usuario que creo el documento
        last_modified_by_id: ID del ultimo usuario que modifico el documento
        last_modified_by_name: Nombre del ultimo usuario que modifico
        created_at: Fecha y hora de creacion
        updated_at: Fecha y hora de ultima actualizacion
    """

    # Opciones de categoria para documentos legales
    # Cada tupla contiene (valor_interno, etiqueta_mostrada)
    CATEGORY_CHOICES = [
        ('pleading', 'Escrito/Demanda'),        # Documentos de demanda o escritos legales
        ('contract', 'Contrato'),                # Contratos legales
        ('evidence', 'Evidencia'),               # Evidencia para casos
        ('correspondence', 'Correspondencia'),   # Cartas y comunicaciones
        ('court_order', 'Orden Judicial'),       # Ordenes emitidas por tribunales
        ('motion', 'Mocion'),                    # Mociones legales
        ('brief', 'Memorial'),                   # Memoriales o briefs
        ('discovery', 'Descubrimiento'),         # Documentos de descubrimiento
        ('exhibit', 'Anexo'),                    # Anexos y exhibiciones
        ('invoice', 'Factura'),                  # Facturas de servicios
        ('receipt', 'Recibo'),                   # Recibos de pago
        ('power_of_attorney', 'Poder'),          # Poderes notariales
        ('identification', 'Identificacion'),    # Documentos de identidad
        ('other', 'Otro'),                       # Otros documentos
    ]

    # Opciones de estado del documento en el flujo de trabajo
    STATUS_CHOICES = [
        ('draft', 'Borrador'),                   # Documento en borrador
        ('pending_review', 'Pendiente Revision'), # Esperando revision
        ('approved', 'Aprobado'),                # Aprobado para uso
        ('filed', 'Radicado'),                   # Presentado oficialmente
        ('archived', 'Archivado'),               # Archivado/inactivo
    ]

    # Campo ID: Identificador unico universal (UUID) como clave primaria
    # primary_key=True indica que es la clave primaria de la tabla
    # default=uuid.uuid4 genera automaticamente un UUID al crear el registro
    # editable=False impide que se modifique despues de creado
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Nombre del documento con maximo 255 caracteres
    name = models.CharField(max_length=255)

    # Descripcion del documento, puede estar vacia (blank=True)
    description = models.TextField(blank=True)

    # Categoria del documento, limitada a las opciones definidas
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    # Estado del documento con valor por defecto 'draft' (borrador)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # ========== Informacion del archivo ==========

    # Campo de archivo que usa la funcion document_upload_path para determinar la ruta
    file = models.FileField(upload_to=document_upload_path)

    # Nombre original del archivo tal como lo subio el usuario
    original_filename = models.CharField(max_length=255)

    # Tamano del archivo en bytes (BigIntegerField para archivos grandes)
    file_size = models.BigIntegerField(default=0)

    # Tipo MIME del archivo (ej: application/pdf, image/jpeg)
    mime_type = models.CharField(max_length=100, blank=True)

    # Hash SHA-256 del archivo para verificar integridad
    checksum = models.CharField(max_length=64, blank=True)

    # ========== Control de versiones ==========

    # Numero de la version actual del documento
    current_version = models.IntegerField(default=1)

    # ========== Relaciones con otros modelos ==========

    # ID del caso legal asociado (puede ser nulo para documentos independientes)
    # db_index=True crea un indice para mejorar rendimiento de busquedas
    case_id = models.UUIDField(db_index=True, null=True, blank=True)

    # ID del documento padre para documentos vinculados/relacionados
    parent_document_id = models.UUIDField(null=True, blank=True)

    # ========== Seguridad y privacidad ==========

    # Indica si el documento es confidencial
    is_confidential = models.BooleanField(default=False)

    # Indica si el documento tiene privilegio abogado-cliente
    is_privileged = models.BooleanField(default=False)

    # Estado de cifrado del documento con opciones predefinidas
    encryption_status = models.CharField(max_length=20, default='none', choices=[
        ('none', 'Sin cifrar'),           # Sin cifrado
        ('at_rest', 'Cifrado en reposo'), # Cifrado cuando esta almacenado
        ('full', 'Cifrado completo'),     # Cifrado en todo momento
    ])

    # ========== Metadatos ==========

    # Lista de etiquetas para clasificacion, almacenada como JSON
    tags = models.JSONField(default=list, blank=True)

    # Metadatos personalizados adicionales en formato JSON
    metadata = models.JSONField(default=dict, blank=True)

    # ========== Busqueda Full-Text ==========

    # Contenido de texto extraido del documento para busqueda
    # Este campo almacena el texto plano extraido del contenido del archivo
    text_content = models.TextField(blank=True, default='')

    # Vector de busqueda de PostgreSQL para busqueda full-text eficiente
    # Este campo es indexado con GIN para busquedas rapidas
    search_vector = SearchVectorField(null=True, blank=True)

    # Indica si el texto ya fue extraido del documento
    text_extracted = models.BooleanField(default=False)

    # ========== Campos de auditoria ==========

    # ID del usuario que creo el documento
    created_by_id = models.UUIDField(db_index=True)

    # Nombre del usuario que creo el documento (para mostrar sin consultas adicionales)
    created_by_name = models.CharField(max_length=255)

    # ID del ultimo usuario que modifico el documento
    last_modified_by_id = models.UUIDField(null=True, blank=True)

    # Nombre del ultimo usuario que modifico el documento
    last_modified_by_name = models.CharField(max_length=255, blank=True)

    # Fecha y hora de creacion (se establece automaticamente al crear)
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha y hora de ultima actualizacion (se actualiza automaticamente)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadatos del modelo Document.

        Define configuraciones adicionales como el nombre de la tabla,
        el ordenamiento por defecto, y los indices de la base de datos.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'documents'

        # Ordenamiento por defecto: mas recientes primero
        ordering = ['-created_at']

        # Indices para mejorar el rendimiento de consultas frecuentes
        indexes = [
            models.Index(fields=['case_id']),       # Busquedas por caso
            models.Index(fields=['category']),       # Busquedas por categoria
            models.Index(fields=['status']),         # Busquedas por estado
            models.Index(fields=['created_by_id']),  # Busquedas por creador
            GinIndex(fields=['search_vector']),      # Indice GIN para busqueda full-text
        ]

    def __str__(self):
        """
        Representacion en cadena del documento.

        Returns:
            str: Nombre del documento con su version actual
        """
        return f"{self.name} (v{self.current_version})"

    def save(self, *args, **kwargs):
        """
        Metodo personalizado para guardar el documento.

        Antes de guardar, actualiza automaticamente el tamano del archivo,
        el nombre original y el tipo MIME si no estan establecidos.

        Args:
            *args: Argumentos posicionales adicionales
            **kwargs: Argumentos de palabra clave adicionales
        """
        # Si hay un archivo asociado
        if self.file:
            # Actualizar el tamano del archivo
            self.file_size = self.file.size

            # Si no hay nombre original, usar el nombre del archivo
            if not self.original_filename:
                self.original_filename = self.file.name

            # Detectar y establecer el tipo MIME si no esta definido
            if not self.mime_type:
                import mimetypes
                # Obtener el nombre del archivo
                filename = self.original_filename or self.file.name
                # Detectar el tipo MIME basado en la extension
                mime_type, _ = mimetypes.guess_type(filename)
                self.mime_type = mime_type or 'application/octet-stream'

        # Llamar al metodo save() de la clase padre para guardar en la BD
        super().save(*args, **kwargs)

    def extract_and_index_text(self):
        """
        Extrae el texto del documento y actualiza el vector de busqueda.

        Esta funcion debe llamarse despues de guardar el documento para
        extraer el contenido de texto e indexarlo para busqueda full-text.
        """
        from .text_extraction import extract_text
        from django.contrib.postgres.search import SearchVector

        try:
            # Leer el contenido del archivo
            self.file.seek(0)
            file_content = self.file.read()
            self.file.seek(0)

            # Extraer texto del archivo
            text = extract_text(file_content, self.mime_type, self.original_filename)

            if text:
                self.text_content = text
                self.text_extracted = True
                self.save(update_fields=['text_content', 'text_extracted'])

                # Actualizar el vector de busqueda usando SQL directo
                # Esto combina nombre, descripcion y contenido con diferentes pesos
                Document.objects.filter(pk=self.pk).update(
                    search_vector=(
                        SearchVector('name', weight='A') +
                        SearchVector('description', weight='B') +
                        SearchVector('text_content', weight='C')
                    )
                )

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error extrayendo texto de documento {self.id}: {str(e)}")

    def update_search_vector(self):
        """
        Actualiza solo el vector de busqueda sin re-extraer el texto.

        Util cuando se modifica el nombre o descripcion del documento.
        """
        from django.contrib.postgres.search import SearchVector

        Document.objects.filter(pk=self.pk).update(
            search_vector=(
                SearchVector('name', weight='A') +
                SearchVector('description', weight='B') +
                SearchVector('text_content', weight='C')
            )
        )


class DocumentVersion(models.Model):
    """
    Modelo para el historial de versiones de documentos.

    Cada vez que se actualiza un documento, se crea una nueva version
    para mantener un historial completo de cambios.

    Attributes:
        id: Identificador unico UUID de la version
        document: Referencia al documento padre
        version_number: Numero secuencial de la version
        file: Archivo de esta version especifica
        file_size: Tamano del archivo en bytes
        checksum: Hash SHA-256 para verificar integridad
        changes_description: Descripcion de los cambios realizados
        created_by_id: ID del usuario que creo esta version
        created_by_name: Nombre del usuario que creo esta version
        created_at: Fecha y hora de creacion de la version
    """

    # Identificador unico UUID para la version
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el documento padre
    # on_delete=CASCADE elimina las versiones si se elimina el documento
    # related_name='versions' permite acceder desde Document como document.versions
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')

    # Numero secuencial de la version (1, 2, 3, etc.)
    version_number = models.IntegerField()

    # Archivo de esta version especifica
    file = models.FileField(upload_to=version_upload_path)

    # Tamano del archivo en bytes
    file_size = models.BigIntegerField(default=0)

    # Hash SHA-256 para verificar integridad del archivo
    checksum = models.CharField(max_length=64, blank=True)

    # Descripcion de los cambios realizados en esta version
    changes_description = models.TextField(blank=True)

    # ID del usuario que creo esta version
    created_by_id = models.UUIDField()

    # Nombre del usuario que creo esta version
    created_by_name = models.CharField(max_length=255)

    # Fecha y hora de creacion de la version
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadatos del modelo DocumentVersion.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'document_versions'

        # Ordenamiento por defecto: version mas reciente primero
        ordering = ['-version_number']

        # Restriccion de unicidad: no puede haber dos versiones con el mismo numero
        # para el mismo documento
        unique_together = ['document', 'version_number']

    def __str__(self):
        """
        Representacion en cadena de la version.

        Returns:
            str: Nombre del documento con el numero de version
        """
        return f"{self.document.name} - v{self.version_number}"


class DocumentAccessLog(models.Model):
    """
    Registro de auditoria para accesos y acciones sobre documentos.

    Este modelo mantiene un registro completo de todas las acciones
    realizadas sobre los documentos para fines de auditoria y seguridad.

    Attributes:
        id: Identificador unico UUID del registro
        document: Documento al que se accedio
        action: Tipo de accion realizada
        user_id: ID del usuario que realizo la accion
        user_email: Email del usuario
        user_role: Rol del usuario en el sistema
        ip_address: Direccion IP desde donde se realizo la accion
        user_agent: Informacion del navegador/cliente
        details: Detalles adicionales de la accion en formato JSON
        timestamp: Fecha y hora de la accion
    """

    # Opciones de tipos de accion para el registro de auditoria
    ACTION_CHOICES = [
        ('view', 'Visualizado'),             # Documento visto
        ('download', 'Descargado'),          # Documento descargado
        ('upload', 'Subido'),                 # Documento subido
        ('update', 'Actualizado'),           # Documento actualizado
        ('delete', 'Eliminado'),             # Documento eliminado
        ('share', 'Compartido'),             # Documento compartido
        ('print', 'Impreso'),                # Documento impreso
        ('version_created', 'Version creada'), # Nueva version creada
        ('status_change', 'Cambio de estado'), # Cambio de estado del documento
    ]

    # Identificador unico UUID del registro de acceso
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el documento accedido
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_logs')

    # Tipo de accion realizada (limitado a las opciones definidas)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # ID del usuario que realizo la accion
    user_id = models.UUIDField(db_index=True)

    # Email del usuario para referencia rapida
    user_email = models.EmailField()

    # Rol del usuario en el momento de la accion
    user_role = models.CharField(max_length=50)

    # Direccion IP desde donde se realizo la accion (puede ser nula)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Cadena User-Agent del navegador/cliente
    user_agent = models.TextField(blank=True)

    # Detalles adicionales de la accion en formato JSON
    details = models.JSONField(default=dict, blank=True)

    # Marca de tiempo de cuando ocurrio la accion
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadatos del modelo DocumentAccessLog.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'document_access_logs'

        # Ordenamiento por defecto: mas recientes primero
        ordering = ['-timestamp']

        # Indices para consultas frecuentes de auditoria
        indexes = [
            models.Index(fields=['document', 'timestamp']),  # Historial por documento
            models.Index(fields=['user_id', 'timestamp']),   # Historial por usuario
            models.Index(fields=['action', 'timestamp']),    # Historial por tipo de accion
        ]

    def __str__(self):
        """
        Representacion en cadena del registro de acceso.

        Returns:
            str: Descripcion de la accion realizada
        """
        # get_action_display() obtiene la etiqueta legible de la accion
        return f"{self.user_email} {self.get_action_display()} {self.document.name}"


class DocumentShare(models.Model):
    """
    Modelo para permisos de comparticion de documentos.

    Permite compartir documentos con otros usuarios con diferentes
    niveles de permiso y fechas de expiracion opcionales.

    Attributes:
        id: Identificador unico UUID del permiso
        document: Documento compartido
        shared_with_user_id: ID del usuario con quien se comparte
        shared_with_email: Email del usuario con quien se comparte
        permission: Nivel de permiso otorgado
        shared_by_id: ID del usuario que compartio el documento
        shared_by_name: Nombre del usuario que compartio
        expires_at: Fecha de expiracion del permiso (opcional)
        created_at: Fecha de creacion del permiso
    """

    # Opciones de niveles de permiso para compartir
    PERMISSION_CHOICES = [
        ('view', 'Ver'),          # Solo puede ver el documento
        ('download', 'Descargar'), # Puede descargar el documento
        ('edit', 'Editar'),        # Puede editar el documento
    ]

    # Identificador unico UUID del permiso de comparticion
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con el documento que se comparte
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='shares')

    # ID del usuario con quien se comparte el documento
    shared_with_user_id = models.UUIDField(db_index=True)

    # Email del usuario con quien se comparte
    shared_with_email = models.EmailField()

    # Nivel de permiso otorgado (por defecto: solo ver)
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')

    # ID del usuario que compartio el documento
    shared_by_id = models.UUIDField()

    # Nombre del usuario que compartio el documento
    shared_by_name = models.CharField(max_length=255)

    # Fecha de expiracion del permiso (opcional, puede ser nula)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Fecha de creacion del permiso
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadatos del modelo DocumentShare.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'document_shares'

        # Restriccion: un documento solo puede compartirse una vez con cada usuario
        unique_together = ['document', 'shared_with_user_id']

    def __str__(self):
        """
        Representacion en cadena del permiso de comparticion.

        Returns:
            str: Descripcion del documento y con quien se comparte
        """
        return f"{self.document.name} shared with {self.shared_with_email}"


class Folder(models.Model):
    """
    Modelo para estructura de carpetas para organizar documentos.

    Permite crear una jerarquia de carpetas similar a un sistema de archivos
    para organizar los documentos de manera logica.

    Attributes:
        id: Identificador unico UUID de la carpeta
        name: Nombre de la carpeta
        description: Descripcion de la carpeta
        parent: Carpeta padre (para jerarquia)
        case_id: ID del caso asociado (opcional)
        color: Color de la carpeta en formato hexadecimal
        created_by_id: ID del usuario que creo la carpeta
        created_at: Fecha de creacion
        updated_at: Fecha de ultima actualizacion
    """

    # Identificador unico UUID de la carpeta
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Nombre de la carpeta
    name = models.CharField(max_length=255)

    # Descripcion opcional de la carpeta
    description = models.TextField(blank=True)

    # Referencia a la carpeta padre (permite crear jerarquias)
    # 'self' indica que es una relacion con el mismo modelo
    # null=True y blank=True permiten carpetas raiz sin padre
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    # ID del caso legal asociado a esta carpeta
    case_id = models.UUIDField(db_index=True, null=True, blank=True)

    # Color de la carpeta en formato hexadecimal (por defecto gris)
    color = models.CharField(max_length=7, default='#6B7280')

    # ID del usuario que creo la carpeta
    created_by_id = models.UUIDField()

    # Fecha de creacion de la carpeta
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion de la carpeta
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadatos del modelo Folder.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'folders'

        # Ordenamiento por defecto: alfabetico por nombre
        ordering = ['name']

    def __str__(self):
        """
        Representacion en cadena de la carpeta.

        Returns:
            str: Nombre de la carpeta
        """
        return self.name

    @property
    def path(self):
        """
        Obtiene la ruta completa de la carpeta.

        Esta propiedad calcula recursivamente la ruta desde la carpeta raiz
        hasta esta carpeta, separando cada nivel con '/'.

        Returns:
            str: Ruta completa de la carpeta (ej: "Casos/2024/Contratos")
        """
        # Si tiene carpeta padre, concatenar la ruta del padre con el nombre actual
        if self.parent:
            return f"{self.parent.path}/{self.name}"

        # Si es carpeta raiz, retornar solo el nombre
        return self.name
