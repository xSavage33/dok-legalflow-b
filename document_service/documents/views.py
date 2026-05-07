"""
views.py - Vistas del API REST para el Servicio de Documentos

Este archivo contiene todas las vistas (endpoints) del API REST para la gestion
de documentos legales. Implementa operaciones CRUD (Crear, Leer, Actualizar, Eliminar)
para documentos, versiones, comparticiones y carpetas.

Las vistas utilizan Django REST Framework para proporcionar:
- Listado y creacion de documentos
- Detalle, actualizacion y eliminacion de documentos
- Descarga de archivos
- Control de versiones
- Registro de auditoria
- Comparticion de documentos
- Organizacion por carpetas

Autor: Equipo de Desarrollo LegalFlow
"""

# Importacion del modulo hashlib para calcular checksums SHA-256
import hashlib

# Importacion de logging para registro de eventos
import logging

# Importacion de clases genericas de DRF para vistas basadas en clases
from rest_framework import generics, status, filters

# Importacion del cliente IAM para verificacion de permisos
from .iam_client import check_document_permission, check_permission

# Importacion del modulo de cifrado
from .encryption import encrypt_file, decrypt_file, encrypt_file_stream

# Logger para este modulo
logger = logging.getLogger(__name__)

# Importacion de la clase Response para enviar respuestas HTTP
from rest_framework.response import Response

# Importacion de APIView para vistas personalizadas
from rest_framework.views import APIView

# Importacion de parsers para manejar archivos subidos (multipart/form-data)
from rest_framework.parsers import MultiPartParser, FormParser

# Importacion del backend de filtrado de django-filter
from django_filters.rest_framework import DjangoFilterBackend

# Importacion de FileResponse para enviar archivos como respuesta HTTP
from django.http import FileResponse

# Importacion de get_object_or_404 para obtener objetos o devolver 404
from django.shortcuts import get_object_or_404

# Importacion de timezone para manejo de fechas con zona horaria
from django.utils import timezone

# Importacion de los modelos del servicio de documentos
from .models import Document, DocumentVersion, DocumentAccessLog, DocumentShare, Folder

# Importacion de todos los serializadores necesarios
from .serializers import (
    DocumentListSerializer,      # Serializador para lista de documentos
    DocumentDetailSerializer,    # Serializador para detalle de documento
    DocumentUploadSerializer,    # Serializador para subida de documentos
    DocumentUpdateSerializer,    # Serializador para actualizacion de documentos
    DocumentVersionSerializer,   # Serializador para versiones
    DocumentAccessLogSerializer, # Serializador para registros de acceso
    DocumentShareSerializer,     # Serializador para comparticiones
    FolderSerializer,           # Serializador para carpetas
    NewVersionSerializer,        # Serializador para nueva version
    ShareDocumentSerializer,     # Serializador para compartir documento
)


def get_client_ip(request):
    """
    Obtiene la direccion IP del cliente desde la solicitud HTTP.

    Esta funcion maneja tanto conexiones directas como conexiones a traves
    de proxies (usando el encabezado X-Forwarded-For).

    Args:
        request: Objeto de solicitud HTTP de Django

    Returns:
        str: Direccion IP del cliente
    """
    # Intentar obtener la IP del encabezado X-Forwarded-For (usado por proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        # Si hay multiples IPs (por varios proxies), tomar la primera
        ip = x_forwarded_for.split(',')[0]
    else:
        # Si no hay proxy, usar REMOTE_ADDR directamente
        ip = request.META.get('REMOTE_ADDR')

    return ip


def log_document_access(document, user, action, request, details=None):
    """
    Crea un registro de acceso en el log de auditoria para un documento.

    Esta funcion se llama cada vez que un usuario realiza una accion sobre
    un documento, creando un registro completo para auditoria.

    Args:
        document: Instancia del documento accedido
        user: Usuario que realiza la accion
        action: Tipo de accion (view, download, upload, etc.)
        request: Objeto de solicitud HTTP para obtener IP y User-Agent
        details: Diccionario opcional con detalles adicionales de la accion
    """
    # Crear un nuevo registro de acceso en la base de datos
    DocumentAccessLog.objects.create(
        document=document,                           # Documento accedido
        action=action,                               # Tipo de accion realizada
        user_id=user.id,                            # ID del usuario
        user_email=user.email,                      # Email del usuario
        user_role=user.role,                        # Rol del usuario
        ip_address=get_client_ip(request),          # IP del cliente
        user_agent=request.META.get('HTTP_USER_AGENT', ''),  # Navegador/cliente
        details=details or {}                        # Detalles adicionales o dict vacio
    )


def calculate_checksum(file):
    """
    Calcula el checksum SHA-256 de un archivo.

    El checksum se usa para verificar la integridad del archivo
    y detectar si ha sido modificado o corrompido.

    Args:
        file: Objeto de archivo de Django con metodo chunks()

    Returns:
        str: Hash SHA-256 del archivo en formato hexadecimal (64 caracteres)
    """
    # Crear un objeto hash SHA-256
    sha256_hash = hashlib.sha256()

    # Iterar sobre los chunks del archivo para manejar archivos grandes
    for chunk in file.chunks():
        # Actualizar el hash con cada chunk
        sha256_hash.update(chunk)

    # Retornar el hash en formato hexadecimal
    return sha256_hash.hexdigest()


class DocumentListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear documentos.

    GET: Lista todos los documentos con soporte para filtrado, busqueda y ordenamiento.
    POST: Crea un nuevo documento con archivo adjunto.

    Esta vista utiliza parsers especiales para manejar la subida de archivos
    en formato multipart/form-data.
    """

    # QuerySet base que incluye todos los documentos
    queryset = Document.objects.all()

    # Parsers para manejar subida de archivos
    parser_classes = [MultiPartParser, FormParser]

    # Backends de filtrado habilitados
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Campos disponibles para filtrado exacto
    filterset_fields = ['case_id', 'category', 'status', 'is_confidential', 'created_by_id']

    # Campos en los que se puede buscar texto
    search_fields = ['name', 'description', 'original_filename', 'tags']

    # Campos por los que se puede ordenar
    ordering_fields = ['created_at', 'updated_at', 'name', 'file_size']

    # Ordenamiento por defecto: mas recientes primero
    ordering = ['-created_at']

    def get_serializer_class(self):
        """
        Determina que serializador usar segun el metodo HTTP.

        Returns:
            class: Clase del serializador apropiado
        """
        # Para POST (crear), usar el serializador de subida
        if self.request.method == 'POST':
            return DocumentUploadSerializer

        # Para GET (listar), usar el serializador de lista
        return DocumentListSerializer

    def perform_create(self, serializer):
        """
        Logica personalizada al crear un documento.

        Se ejecuta despues de que el serializador valida los datos
        pero antes de enviar la respuesta.

        Incluye cifrado automatico del archivo antes de almacenarlo.

        Args:
            serializer: Serializador con datos validados
        """
        from django.core.files.base import ContentFile

        # Guardar el documento inicialmente para obtener la instancia
        document = serializer.save()

        # Calcular el checksum SHA-256 del archivo original (antes de cifrar)
        original_checksum = calculate_checksum(document.file)

        # Cifrar el archivo antes de almacenarlo
        try:
            # Leer el contenido del archivo
            document.file.seek(0)
            original_content = document.file.read()
            original_size = len(original_content)

            # Cifrar el contenido
            encrypted_content, encryption_metadata = encrypt_file(original_content)

            # Crear nuevo archivo con contenido cifrado
            encrypted_file = ContentFile(
                encrypted_content,
                name=document.file.name
            )

            # Actualizar el documento con el archivo cifrado
            document.file = encrypted_file
            document.file_size = original_size  # Mantener tamano original para referencia
            document.checksum = original_checksum  # Checksum del archivo original
            document.encryption_status = 'at_rest'  # Marcar como cifrado en reposo

            # Guardar metadatos de cifrado
            if not document.metadata:
                document.metadata = {}
            document.metadata['encryption'] = {
                'status': 'encrypted',
                'algorithm': 'AES-256-GCM',
                'original_size': original_size,
                'encrypted_size': len(encrypted_content),
                'metadata': encryption_metadata
            }

            document.save()

            logger.info(f"Documento {document.id} cifrado exitosamente")

        except Exception as e:
            # Si falla el cifrado, guardar sin cifrar pero registrar el error
            logger.error(f"Error al cifrar documento {document.id}: {str(e)}")
            document.checksum = original_checksum
            document.encryption_status = 'none'
            document.save()

        # Crear la version inicial (version 1) en el historial de versiones
        # Esto permite que cuando se suban nuevas versiones, la original quede registrada
        DocumentVersion.objects.create(
            document=document,
            version_number=1,
            file=document.file,
            file_size=document.file_size,
            checksum=document.checksum,
            changes_description='Version inicial del documento',
            created_by_id=self.request.user.id,
            created_by_name=self.request.user.email
        )

        # Registrar la accion de subida en el log de auditoria
        log_document_access(
            document,
            self.request.user,
            'upload',
            self.request,
            {
                'original_filename': document.original_filename,
                'encrypted': document.encryption_status == 'at_rest'
            }
        )

        # Extraer texto del documento para busqueda full-text (en background)
        # Esto indexa el contenido del documento para permitir busquedas
        try:
            document.extract_and_index_text()
            logger.info(f"Texto extraido e indexado para documento {document.id}")
        except Exception as e:
            # No fallamos la creacion si la extraccion falla
            logger.warning(f"No se pudo extraer texto de documento {document.id}: {str(e)}")


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar un documento especifico.

    GET: Obtiene los detalles completos de un documento.
    PUT/PATCH: Actualiza los campos del documento.
    DELETE: Elimina el documento.

    Todas las acciones son registradas en el log de auditoria.
    """

    # QuerySet base con todos los documentos
    queryset = Document.objects.all()

    # Campo usado para buscar el documento en la URL
    lookup_field = 'id'

    def get_serializer_class(self):
        """
        Determina que serializador usar segun el metodo HTTP.

        Returns:
            class: Clase del serializador apropiado
        """
        # Para PUT o PATCH (actualizar), usar el serializador de actualizacion
        if self.request.method in ['PUT', 'PATCH']:
            return DocumentUpdateSerializer

        # Para GET (detalle), usar el serializador de detalle
        return DocumentDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Obtiene los detalles de un documento.

        Sobrescribe el metodo base para agregar registro de auditoria
        y verificacion de permisos con IAM Service.

        Args:
            request: Solicitud HTTP
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave

        Returns:
            Response: Respuesta con datos del documento
        """
        # Obtener el documento primero para verificar permisos
        document = self.get_object()

        # Verificar permisos con IAM Service
        if not check_document_permission(request.user, document, 'view'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permiso para ver este documento")

        # Llamar al metodo retrieve() de la clase padre
        response = super().retrieve(request, *args, **kwargs)

        # Registrar la visualizacion en el log
        log_document_access(document, request.user, 'view', request)

        return response

    def perform_update(self, serializer):
        """
        Logica personalizada al actualizar un documento.

        Detecta cambios de estado para registrarlos apropiadamente.

        Args:
            serializer: Serializador con datos validados
        """
        # Guardar el estado anterior antes de actualizar
        old_status = self.get_object().status

        # Guardar los cambios
        document = serializer.save()

        # Verificar si el estado cambio
        if old_status != document.status:
            # Si cambio el estado, registrar como cambio de estado
            log_document_access(
                document,
                self.request.user,
                'status_change',
                self.request,
                {'old_status': old_status, 'new_status': document.status}
            )
        else:
            # Si no cambio el estado, registrar como actualizacion general
            log_document_access(document, self.request.user, 'update', self.request)

    def perform_destroy(self, instance):
        """
        Logica personalizada al eliminar un documento.

        Registra la eliminacion en el log antes de eliminar el documento.

        Args:
            instance: Instancia del documento a eliminar
        """
        # Registrar la eliminacion en el log (antes de eliminar)
        log_document_access(instance, self.request.user, 'delete', self.request)

        # Eliminar el documento
        instance.delete()


class DocumentDownloadView(APIView):
    """
    Vista para descargar un archivo de documento.

    Permite descargar el archivo asociado a un documento,
    registrando la descarga en el log de auditoria.
    Incluye verificacion de permisos con IAM Service y
    descifrado automatico de archivos cifrados.
    """

    def get(self, request, id):
        """
        Maneja la solicitud GET para descargar un documento.

        Verifica permisos con IAM Service, descifra el archivo
        si esta cifrado, y registra la descarga en el log.

        Args:
            request: Solicitud HTTP
            id: UUID del documento a descargar

        Returns:
            FileResponse: Respuesta con el archivo para descarga
        """
        from django.http import HttpResponse
        from io import BytesIO

        # Obtener el documento o devolver 404 si no existe
        document = get_object_or_404(Document, id=id)

        # Verificar permisos con IAM Service
        if not check_document_permission(request.user, document, 'download'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permiso para descargar este documento")

        # Registrar la descarga en el log de auditoria
        log_document_access(document, request.user, 'download', request)

        # Verificar si el documento esta cifrado
        if document.encryption_status in ['at_rest', 'full']:
            try:
                # Leer el contenido cifrado
                document.file.seek(0)
                encrypted_content = document.file.read()

                # Descifrar el contenido
                decrypted_content = decrypt_file(encrypted_content)

                # Crear respuesta con el contenido descifrado
                response = HttpResponse(
                    decrypted_content,
                    content_type=document.mime_type or 'application/octet-stream'
                )
                response['Content-Disposition'] = f'attachment; filename="{document.original_filename}"'
                response['Content-Length'] = len(decrypted_content)

                return response

            except Exception as e:
                logger.error(f"Error al descifrar documento {id}: {str(e)}")
                # Si falla el descifrado, intentar enviar el archivo normal
                document.file.seek(0)

        # Para archivos no cifrados, enviar directamente
        response = FileResponse(
            document.file,                    # Archivo a enviar
            as_attachment=True,               # Forzar descarga (no mostrar en navegador)
            filename=document.original_filename  # Nombre del archivo para el usuario
        )

        return response


class DocumentVersionListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear versiones de un documento.

    GET: Lista todas las versiones de un documento especifico.
    POST: Crea una nueva version subiendo un nuevo archivo.
    """

    # Serializador para versiones de documento
    serializer_class = DocumentVersionSerializer

    # Parsers para manejar subida de archivos
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """
        Obtiene las versiones filtradas por documento.

        Returns:
            QuerySet: Versiones del documento especificado en la URL
        """
        # Obtener el ID del documento de los parametros de la URL
        document_id = self.kwargs['document_id']

        # Filtrar versiones por documento
        return DocumentVersion.objects.filter(document_id=document_id)

    def create(self, request, *args, **kwargs):
        """
        Crea una nueva version del documento.

        Este metodo maneja toda la logica de versionamiento:
        - Valida el archivo subido
        - Crea el registro de version
        - Actualiza el documento principal
        - Registra la accion en el log

        Args:
            request: Solicitud HTTP con el archivo
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave

        Returns:
            Response: Respuesta con datos de la nueva version
        """
        # Obtener el ID del documento de la URL
        document_id = self.kwargs['document_id']

        # Obtener el documento o devolver 404
        document = get_object_or_404(Document, id=document_id)

        # Validar los datos de la nueva version
        serializer = NewVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extraer los datos validados
        file = serializer.validated_data['file']
        changes_description = serializer.validated_data.get('changes_description', '')

        # Calcular el nuevo numero de version
        new_version_number = document.current_version + 1

        # Crear el registro de la nueva version
        version = DocumentVersion.objects.create(
            document=document,                    # Documento padre
            version_number=new_version_number,    # Numero de version
            file=file,                            # Archivo de esta version
            file_size=file.size,                  # Tamano del archivo
            checksum=calculate_checksum(file),    # Hash para integridad
            changes_description=changes_description,  # Descripcion de cambios
            created_by_id=request.user.id,        # ID del usuario
            created_by_name=request.user.email    # Email del usuario
        )

        # Actualizar el documento principal con la nueva version
        document.current_version = new_version_number  # Incrementar version
        document.file = file                           # Actualizar archivo
        document.file_size = file.size                 # Actualizar tamano
        document.checksum = version.checksum           # Actualizar checksum
        document.last_modified_by_id = request.user.id         # Usuario que modifico
        document.last_modified_by_name = request.user.email    # Nombre del usuario
        document.save()

        # Registrar la creacion de version en el log
        log_document_access(
            document,
            request.user,
            'version_created',
            request,
            {'version': new_version_number, 'changes': changes_description}
        )

        # Devolver la respuesta con la nueva version creada
        return Response(
            DocumentVersionSerializer(version).data,
            status=status.HTTP_201_CREATED
        )


class DocumentVersionDownloadView(APIView):
    """
    Vista para descargar una version especifica de un documento.

    Permite descargar versiones anteriores de un documento
    para revision o comparacion.
    """

    def get(self, request, document_id, version_number):
        """
        Maneja la solicitud GET para descargar una version especifica.

        Args:
            request: Solicitud HTTP
            document_id: UUID del documento
            version_number: Numero de la version a descargar

        Returns:
            FileResponse: Respuesta con el archivo de la version
        """
        # Obtener el documento o devolver 404
        document = get_object_or_404(Document, id=document_id)

        # Obtener la version especifica o devolver 404
        version = get_object_or_404(
            DocumentVersion,
            document=document,
            version_number=version_number
        )

        # Registrar la descarga de la version en el log
        log_document_access(
            document,
            request.user,
            'download',
            request,
            {'version': version_number}  # Incluir numero de version en detalles
        )

        # Crear el nombre del archivo incluyendo el numero de version
        # Formato: nombre_v1.extension
        filename = f"{document.name}_v{version_number}.{document.original_filename.split('.')[-1]}"

        # Devolver la respuesta de archivo
        response = FileResponse(
            version.file,
            as_attachment=True,
            filename=filename
        )

        return response


class DocumentAccessLogView(generics.ListAPIView):
    """
    Vista para obtener los registros de acceso de un documento.

    Muestra el historial completo de acciones realizadas sobre
    un documento especifico (visualizaciones, descargas, cambios, etc.).
    """

    # Serializador para registros de acceso
    serializer_class = DocumentAccessLogSerializer

    def get_queryset(self):
        """
        Obtiene los registros de acceso filtrados por documento.

        Returns:
            QuerySet: Registros de acceso del documento especificado
        """
        # Obtener el ID del documento de la URL
        document_id = self.kwargs['document_id']

        # Filtrar registros por documento
        return DocumentAccessLog.objects.filter(document_id=document_id)


class DocumentShareView(generics.ListCreateAPIView):
    """
    Vista para gestionar la comparticion de documentos.

    GET: Lista todos los permisos de comparticion de un documento.
    POST: Comparte un documento con un usuario.
    """

    # Serializador para comparticiones
    serializer_class = DocumentShareSerializer

    def get_queryset(self):
        """
        Obtiene las comparticiones filtradas por documento.

        Returns:
            QuerySet: Comparticiones del documento especificado
        """
        # Obtener el ID del documento de la URL
        document_id = self.kwargs['document_id']

        # Filtrar comparticiones por documento
        return DocumentShare.objects.filter(document_id=document_id)

    def create(self, request, *args, **kwargs):
        """
        Comparte un documento con un usuario.

        Si ya existe una comparticion con el usuario, se actualiza.
        Si no existe, se crea una nueva.

        Args:
            request: Solicitud HTTP con datos de comparticion
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave

        Returns:
            Response: Respuesta con datos de la comparticion
        """
        # Obtener el ID del documento de la URL
        document_id = self.kwargs['document_id']

        # Obtener el documento o devolver 404
        document = get_object_or_404(Document, id=document_id)

        # Validar los datos de comparticion
        serializer = ShareDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Crear o actualizar la comparticion
        # update_or_create busca por document y shared_with_user_id
        # Si encuentra, actualiza. Si no, crea nuevo registro.
        share, created = DocumentShare.objects.update_or_create(
            document=document,
            shared_with_user_id=serializer.validated_data['shared_with_user_id'],
            defaults={
                'shared_with_email': serializer.validated_data['shared_with_email'],
                'permission': serializer.validated_data['permission'],
                'expires_at': serializer.validated_data.get('expires_at'),
                'shared_by_id': request.user.id,
                'shared_by_name': request.user.email
            }
        )

        # Registrar la comparticion en el log
        log_document_access(
            document,
            request.user,
            'share',
            request,
            {
                'shared_with': serializer.validated_data['shared_with_email'],
                'permission': serializer.validated_data['permission']
            }
        )

        # Devolver respuesta con codigo apropiado
        # 201 si se creo, 200 si se actualizo
        return Response(
            DocumentShareSerializer(share).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class DocumentShareDeleteView(generics.DestroyAPIView):
    """
    Vista para eliminar un permiso de comparticion.

    Permite revocar el acceso de un usuario a un documento compartido.
    """

    # Serializador para comparticiones
    serializer_class = DocumentShareSerializer

    # Campo usado para buscar la comparticion en la URL
    lookup_field = 'id'

    def get_queryset(self):
        """
        Obtiene las comparticiones filtradas por documento.

        Returns:
            QuerySet: Comparticiones del documento especificado
        """
        # Obtener el ID del documento de la URL
        document_id = self.kwargs['document_id']

        # Filtrar comparticiones por documento
        return DocumentShare.objects.filter(document_id=document_id)


class DocumentByCaseView(generics.ListAPIView):
    """
    Vista para listar todos los documentos de un caso especifico.

    Proporciona una forma rapida de obtener todos los documentos
    asociados a un caso legal particular.
    """

    # Serializador para lista de documentos
    serializer_class = DocumentListSerializer

    # Backends para busqueda y ordenamiento
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    # Campos en los que se puede buscar
    search_fields = ['name', 'description']

    # Ordenamiento por defecto: mas recientes primero
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Obtiene los documentos filtrados por caso.

        Returns:
            QuerySet: Documentos del caso especificado
        """
        # Obtener el ID del caso de la URL
        case_id = self.kwargs['case_id']

        # Filtrar documentos por caso
        return Document.objects.filter(case_id=case_id)


# ========== Vistas de Carpetas ==========

class FolderListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear carpetas.

    GET: Lista las carpetas raiz (sin padre) con opcion de filtrar por caso.
    POST: Crea una nueva carpeta.
    """

    # QuerySet base: solo carpetas raiz (sin padre)
    queryset = Folder.objects.filter(parent__isnull=True)

    # Serializador para carpetas
    serializer_class = FolderSerializer

    def get_queryset(self):
        """
        Obtiene las carpetas, opcionalmente filtradas por caso.

        Returns:
            QuerySet: Carpetas raiz, filtradas por caso si se especifica
        """
        # Obtener el queryset base
        queryset = super().get_queryset()

        # Verificar si se paso el parametro case_id en la query string
        case_id = self.request.query_params.get('case_id')

        if case_id:
            # Filtrar por caso si se especifico
            queryset = queryset.filter(case_id=case_id)

        return queryset

    def perform_create(self, serializer):
        """
        Logica personalizada al crear una carpeta.

        Asigna automaticamente el usuario creador.

        Args:
            serializer: Serializador con datos validados
        """
        # Guardar la carpeta con el ID del usuario creador
        serializer.save(created_by_id=self.request.user.id)


class FolderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar una carpeta especifica.

    GET: Obtiene los detalles de una carpeta incluyendo sus hijos.
    PUT/PATCH: Actualiza los campos de la carpeta.
    DELETE: Elimina la carpeta y sus hijos (en cascada).
    """

    # QuerySet base con todas las carpetas
    queryset = Folder.objects.all()

    # Serializador para carpetas
    serializer_class = FolderSerializer

    # Campo usado para buscar la carpeta en la URL
    lookup_field = 'id'


class UserAccessLogsView(generics.ListAPIView):
    """
    Vista para obtener los registros de acceso del usuario actual.

    Muestra las ultimas 100 acciones realizadas por el usuario
    autenticado sobre cualquier documento.
    """

    # Serializador para registros de acceso
    serializer_class = DocumentAccessLogSerializer

    def get_queryset(self):
        """
        Obtiene los registros de acceso del usuario actual.

        Returns:
            QuerySet: Ultimos 100 registros de acceso del usuario
        """
        # Filtrar por el ID del usuario autenticado y limitar a 100 registros
        return DocumentAccessLog.objects.filter(user_id=self.request.user.id)[:100]


# ========== Busqueda Avanzada de Documentos ==========

class AdvancedSearchView(APIView):
    """
    Vista para busqueda avanzada de documentos.

    Proporciona capacidades de busqueda mas sofisticadas que incluyen:
    - Busqueda por texto en multiples campos
    - Filtrado por rango de fechas
    - Filtrado por multiples categorias
    - Filtrado por tags especificos
    - Filtrado por metadatos personalizados
    - Combinacion de multiples criterios con operadores AND/OR
    """

    def post(self, request):
        """
        Realiza una busqueda avanzada de documentos.

        El cuerpo de la solicitud puede contener los siguientes campos:
        - query: Texto a buscar en nombre, descripcion y contenido
        - categories: Lista de categorias a incluir
        - statuses: Lista de estados a incluir
        - tags: Lista de tags requeridos
        - case_id: ID del caso especifico
        - created_by_id: ID del usuario creador
        - date_from: Fecha minima de creacion (YYYY-MM-DD)
        - date_to: Fecha maxima de creacion (YYYY-MM-DD)
        - is_confidential: Filtrar por documentos confidenciales
        - is_privileged: Filtrar por documentos con privilegio
        - metadata_filters: Diccionario de filtros de metadatos
        - sort_by: Campo por el cual ordenar
        - sort_order: Orden (asc o desc)

        Args:
            request: Solicitud HTTP con criterios de busqueda

        Returns:
            Response: Lista de documentos que coinciden con los criterios
        """
        # Importar Q para construir consultas complejas
        from django.db.models import Q

        # Iniciar con todos los documentos
        queryset = Document.objects.all()

        # Extraer parametros de busqueda del cuerpo de la solicitud
        data = request.data

        # ========== Busqueda por texto ==========
        query = data.get('query', '').strip()
        if query:
            # Buscar en nombre, descripcion, nombre original y tags
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(original_filename__icontains=query) |
                Q(tags__icontains=query)
            )

        # ========== Filtrado por categorias ==========
        categories = data.get('categories', [])
        if categories:
            # Filtrar documentos que pertenezcan a alguna de las categorias
            queryset = queryset.filter(category__in=categories)

        # ========== Filtrado por estados ==========
        statuses = data.get('statuses', [])
        if statuses:
            # Filtrar documentos que tengan alguno de los estados
            queryset = queryset.filter(status__in=statuses)

        # ========== Filtrado por tags ==========
        tags = data.get('tags', [])
        if tags:
            # Filtrar documentos que contengan todos los tags especificados
            for tag in tags:
                queryset = queryset.filter(tags__icontains=tag)

        # ========== Filtrado por caso ==========
        case_id = data.get('case_id')
        if case_id:
            queryset = queryset.filter(case_id=case_id)

        # ========== Filtrado por usuario creador ==========
        created_by_id = data.get('created_by_id')
        if created_by_id:
            queryset = queryset.filter(created_by_id=created_by_id)

        # ========== Filtrado por rango de fechas ==========
        date_from = data.get('date_from')
        if date_from:
            # Filtrar documentos creados desde esta fecha
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = data.get('date_to')
        if date_to:
            # Filtrar documentos creados hasta esta fecha
            queryset = queryset.filter(created_at__date__lte=date_to)

        # ========== Filtrado por confidencialidad ==========
        is_confidential = data.get('is_confidential')
        if is_confidential is not None:
            queryset = queryset.filter(is_confidential=is_confidential)

        # ========== Filtrado por privilegio ==========
        is_privileged = data.get('is_privileged')
        if is_privileged is not None:
            queryset = queryset.filter(is_privileged=is_privileged)

        # ========== Filtrado por metadatos ==========
        metadata_filters = data.get('metadata_filters', {})
        if metadata_filters:
            # Filtrar por campos de metadatos especificos
            for key, value in metadata_filters.items():
                queryset = queryset.filter(metadata__contains={key: value})

        # ========== Filtrado por tipo MIME ==========
        mime_types = data.get('mime_types', [])
        if mime_types:
            queryset = queryset.filter(mime_type__in=mime_types)

        # ========== Filtrado por tamano de archivo ==========
        min_size = data.get('min_file_size')
        if min_size:
            queryset = queryset.filter(file_size__gte=min_size)

        max_size = data.get('max_file_size')
        if max_size:
            queryset = queryset.filter(file_size__lte=max_size)

        # ========== Ordenamiento ==========
        sort_by = data.get('sort_by', 'created_at')
        sort_order = data.get('sort_order', 'desc')

        # Campos permitidos para ordenamiento
        allowed_sort_fields = ['created_at', 'updated_at', 'name', 'file_size', 'category']

        if sort_by in allowed_sort_fields:
            # Aplicar orden descendente si se especifica
            if sort_order == 'desc':
                sort_by = f'-{sort_by}'
            queryset = queryset.order_by(sort_by)

        # ========== Paginacion ==========
        page = int(data.get('page', 1))
        page_size = int(data.get('page_size', 20))

        # Limitar page_size a un maximo de 100
        page_size = min(page_size, 100)

        # Calcular offset
        offset = (page - 1) * page_size

        # Contar total antes de paginar
        total_count = queryset.count()

        # Aplicar paginacion
        queryset = queryset[offset:offset + page_size]

        # Serializar resultados
        documents = DocumentListSerializer(queryset, many=True).data

        # Retornar respuesta con resultados y metadatos de paginacion
        return Response({
            'results': documents,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })


# ========== Firma Digital de Documentos ==========

class DocumentSignatureView(APIView):
    """
    Vista para firmar digitalmente un documento.

    Implementa firma digital usando criptografia asimetrica:
    - Genera un hash SHA-256 del contenido del documento
    - Firma el hash con la clave privada del usuario
    - Almacena la firma y metadatos en el documento
    """

    def post(self, request, id):
        """
        Firma digitalmente un documento.

        Args:
            request: Solicitud HTTP con datos de firma
            id: UUID del documento a firmar

        Returns:
            Response: Confirmacion de la firma con metadatos
        """
        # Importaciones necesarias para firma digital
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.backends import default_backend
        import base64
        from datetime import datetime

        # Obtener el documento o devolver 404
        document = get_object_or_404(Document, id=id)

        # Calcular el hash SHA-256 del archivo
        document.file.seek(0)
        file_hash = hashlib.sha256(document.file.read()).hexdigest()
        document.file.seek(0)

        # Generar par de claves RSA para la firma (en produccion esto vendria del usuario)
        # En un sistema real, el usuario tendria su propia clave privada
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Obtener clave publica
        public_key = private_key.public_key()

        # Firmar el hash del documento
        signature = private_key.sign(
            file_hash.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Convertir firma a base64 para almacenamiento
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        # Serializar clave publica para verificacion futura
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        # Crear metadatos de la firma
        signature_data = {
            'signed': True,
            'signed_by_id': str(request.user.id),
            'signed_by_name': request.user.email,
            'signed_at': timezone.now().isoformat(),
            'signature': signature_b64,
            'public_key': public_key_pem,
            'file_hash': file_hash,
            'algorithm': 'RSA-SHA256',
            'key_size': 2048
        }

        # Actualizar metadatos del documento con la informacion de firma
        current_metadata = document.metadata or {}
        current_metadata['digital_signature'] = signature_data
        document.metadata = current_metadata
        document.save()

        # Registrar la firma en el log de auditoria
        log_document_access(
            document,
            request.user,
            'update',
            request,
            {'action': 'digital_signature', 'file_hash': file_hash}
        )

        return Response({
            'message': 'Documento firmado digitalmente',
            'document_id': str(document.id),
            'document_name': document.name,
            'file_hash': file_hash,
            'signed_by': request.user.email,
            'signed_at': signature_data['signed_at'],
            'algorithm': 'RSA-SHA256'
        }, status=status.HTTP_200_OK)


class VerifySignatureView(APIView):
    """
    Vista para verificar la firma digital de un documento.

    Verifica que:
    - El documento tenga una firma digital
    - La firma sea valida
    - El contenido del documento no haya sido modificado
    """

    def get(self, request, id):
        """
        Verifica la firma digital de un documento.

        Args:
            request: Solicitud HTTP
            id: UUID del documento a verificar

        Returns:
            Response: Resultado de la verificacion de firma
        """
        # Importaciones necesarias para verificacion
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        # Obtener el documento o devolver 404
        document = get_object_or_404(Document, id=id)

        # Verificar si el documento tiene firma digital
        signature_data = document.metadata.get('digital_signature', {}) if document.metadata else {}

        if not signature_data.get('signed'):
            return Response({
                'verified': False,
                'message': 'El documento no tiene firma digital',
                'document_id': str(document.id),
                'document_name': document.name
            }, status=status.HTTP_200_OK)

        try:
            # Calcular hash actual del archivo
            document.file.seek(0)
            current_hash = hashlib.sha256(document.file.read()).hexdigest()
            document.file.seek(0)

            # Obtener hash almacenado
            stored_hash = signature_data.get('file_hash')

            # Verificar integridad del archivo
            if current_hash != stored_hash:
                return Response({
                    'verified': False,
                    'message': 'El documento ha sido modificado despues de firmarse',
                    'document_id': str(document.id),
                    'document_name': document.name,
                    'stored_hash': stored_hash,
                    'current_hash': current_hash
                }, status=status.HTTP_200_OK)

            # Cargar clave publica
            public_key_pem = signature_data.get('public_key')
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode(),
                backend=default_backend()
            )

            # Decodificar firma
            signature = base64.b64decode(signature_data.get('signature'))

            # Verificar firma
            public_key.verify(
                signature,
                stored_hash.encode(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )

            return Response({
                'verified': True,
                'message': 'La firma digital es valida',
                'document_id': str(document.id),
                'document_name': document.name,
                'signed_by': signature_data.get('signed_by_name'),
                'signed_at': signature_data.get('signed_at'),
                'algorithm': signature_data.get('algorithm'),
                'file_hash': current_hash
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'verified': False,
                'message': f'Error al verificar la firma: {str(e)}',
                'document_id': str(document.id),
                'document_name': document.name
            }, status=status.HTTP_200_OK)


# ========== Busqueda Full-Text de Documentos ==========

class FullTextSearchView(APIView):
    """
    Vista para busqueda full-text en el contenido de documentos.

    Utiliza la funcionalidad de busqueda full-text de PostgreSQL para
    buscar texto dentro del contenido de los documentos, no solo en
    los metadatos.

    Caracteristicas:
    - Busqueda en contenido extraido de PDF, Word, Excel, etc.
    - Ranking de relevancia
    - Resaltado de fragmentos coincidentes
    - Soporte para operadores de busqueda (AND, OR, NOT)
    """

    def post(self, request):
        """
        Realiza una busqueda full-text en los documentos.

        El cuerpo de la solicitud puede contener:
        - query: Texto a buscar (requerido)
        - search_type: Tipo de busqueda ('plain', 'phrase', 'websearch')
        - case_id: ID del caso para filtrar (opcional)
        - categories: Lista de categorias para filtrar (opcional)
        - page: Numero de pagina (default: 1)
        - page_size: Tamano de pagina (default: 20, max: 100)

        Args:
            request: Solicitud HTTP con criterios de busqueda

        Returns:
            Response: Lista de documentos con ranking y fragmentos coincidentes
        """
        from django.contrib.postgres.search import (
            SearchQuery, SearchRank, SearchHeadline
        )
        from django.db.models import F

        # Extraer parametros de busqueda
        data = request.data
        query_text = data.get('query', '').strip()

        if not query_text:
            return Response({
                'error': 'Se requiere un texto de busqueda',
                'results': [],
                'total_count': 0
            }, status=status.HTTP_400_BAD_REQUEST)

        # Tipo de busqueda: 'plain', 'phrase', 'websearch'
        search_type = data.get('search_type', 'websearch')

        # Crear el objeto de busqueda con configuracion para espanol
        if search_type == 'phrase':
            search_query = SearchQuery(query_text, search_type='phrase', config='spanish')
        elif search_type == 'websearch':
            search_query = SearchQuery(query_text, search_type='websearch', config='spanish')
        else:
            search_query = SearchQuery(query_text, config='spanish')

        # Iniciar queryset con documentos que tienen texto extraido
        queryset = Document.objects.filter(text_extracted=True)

        # Aplicar filtros adicionales
        case_id = data.get('case_id')
        if case_id:
            queryset = queryset.filter(case_id=case_id)

        categories = data.get('categories', [])
        if categories:
            queryset = queryset.filter(category__in=categories)

        statuses = data.get('statuses', [])
        if statuses:
            queryset = queryset.filter(status__in=statuses)

        # Aplicar busqueda full-text con ranking
        queryset = queryset.filter(search_vector=search_query)
        queryset = queryset.annotate(
            rank=SearchRank(F('search_vector'), search_query)
        ).order_by('-rank')

        # Paginacion
        page = int(data.get('page', 1))
        page_size = min(int(data.get('page_size', 20)), 100)
        offset = (page - 1) * page_size

        # Contar total antes de paginar
        total_count = queryset.count()

        # Aplicar paginacion
        documents = list(queryset[offset:offset + page_size])

        # Preparar resultados con fragmentos resaltados
        results = []
        for doc in documents:
            # Generar fragmento con texto resaltado
            headline = ''
            if doc.text_content:
                try:
                    # Obtener fragmento con coincidencias resaltadas
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT ts_headline(
                                'spanish',
                                %s,
                                websearch_to_tsquery('spanish', %s),
                                'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>'
                            )
                        """, [doc.text_content[:5000], query_text])
                        row = cursor.fetchone()
                        if row:
                            headline = row[0]
                except Exception:
                    # Si falla, usar un fragmento simple
                    headline = doc.text_content[:200] + '...' if len(doc.text_content) > 200 else doc.text_content

            results.append({
                'id': str(doc.id),
                'name': doc.name,
                'description': doc.description,
                'category': doc.category,
                'category_display': doc.get_category_display(),
                'status': doc.status,
                'status_display': doc.get_status_display(),
                'original_filename': doc.original_filename,
                'file_size': doc.file_size,
                'mime_type': doc.mime_type,
                'case_id': str(doc.case_id) if doc.case_id else None,
                'is_confidential': doc.is_confidential,
                'is_privileged': doc.is_privileged,
                'created_at': doc.created_at.isoformat(),
                'created_by_name': doc.created_by_name,
                'rank': doc.rank,
                'headline': headline,
            })

        return Response({
            'results': results,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if total_count > 0 else 0,
            'query': query_text
        })


class ExtractTextView(APIView):
    """
    Vista para extraer texto de un documento manualmente.

    Permite forzar la extraccion de texto de un documento especifico
    para indexarlo en la busqueda full-text.
    """

    def post(self, request, id):
        """
        Extrae texto de un documento y actualiza el indice de busqueda.

        Args:
            request: Solicitud HTTP
            id: UUID del documento

        Returns:
            Response: Resultado de la extraccion
        """
        # Obtener el documento
        document = get_object_or_404(Document, id=id)

        # Verificar permisos
        if not check_permission(request.user, 'documents', 'update'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permiso para extraer texto de documentos")

        # Extraer texto e indexar
        try:
            document.extract_and_index_text()

            return Response({
                'message': 'Texto extraido e indexado exitosamente',
                'document_id': str(document.id),
                'document_name': document.name,
                'text_extracted': document.text_extracted,
                'text_preview': document.text_content[:500] if document.text_content else None,
                'text_length': len(document.text_content) if document.text_content else 0
            })

        except Exception as e:
            logger.error(f"Error extrayendo texto de documento {id}: {str(e)}")
            return Response({
                'error': f'Error al extraer texto: {str(e)}',
                'document_id': str(document.id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkExtractTextView(APIView):
    """
    Vista para extraer texto de multiples documentos.

    Permite procesar todos los documentos que aun no tienen texto
    extraido en un solo proceso batch.
    """

    def post(self, request):
        """
        Extrae texto de todos los documentos sin indexar.

        Args:
            request: Solicitud HTTP con opciones:
                - limit: Numero maximo de documentos a procesar (default: 100)
                - case_id: Filtrar por caso especifico

        Returns:
            Response: Resumen del procesamiento
        """
        # Verificar permisos
        if not check_permission(request.user, 'documents', 'update'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permiso para procesar documentos")

        data = request.data
        limit = min(int(data.get('limit', 100)), 500)
        case_id = data.get('case_id')

        # Obtener documentos sin texto extraido
        queryset = Document.objects.filter(text_extracted=False)

        if case_id:
            queryset = queryset.filter(case_id=case_id)

        documents = list(queryset[:limit])

        processed = 0
        errors = 0
        error_details = []

        for doc in documents:
            try:
                doc.extract_and_index_text()
                if doc.text_extracted:
                    processed += 1
            except Exception as e:
                errors += 1
                error_details.append({
                    'document_id': str(doc.id),
                    'document_name': doc.name,
                    'error': str(e)
                })

        return Response({
            'message': 'Procesamiento de extraccion completado',
            'total_found': len(documents),
            'processed_successfully': processed,
            'errors': errors,
            'error_details': error_details[:10] if error_details else []
        })


class ReindexSearchView(APIView):
    """
    Vista para reindexar los vectores de busqueda de documentos.

    Util despues de actualizar nombres o descripciones de documentos
    para reflejar los cambios en el indice de busqueda.
    """

    def post(self, request):
        """
        Reindexar vectores de busqueda.

        Args:
            request: Solicitud HTTP con opciones:
                - document_id: Reindexar documento especifico
                - case_id: Reindexar todos los documentos de un caso
                - all: Reindexar todos los documentos (requiere admin)

        Returns:
            Response: Resumen del reindexado
        """
        from django.contrib.postgres.search import SearchVector

        data = request.data
        document_id = data.get('document_id')
        case_id = data.get('case_id')
        reindex_all = data.get('all', False)

        if document_id:
            # Reindexar documento especifico
            document = get_object_or_404(Document, id=document_id)
            document.update_search_vector()
            return Response({
                'message': 'Documento reindexado',
                'document_id': str(document.id)
            })

        elif case_id:
            # Reindexar documentos de un caso
            count = Document.objects.filter(case_id=case_id).update(
                search_vector=(
                    SearchVector('name', weight='A') +
                    SearchVector('description', weight='B') +
                    SearchVector('text_content', weight='C')
                )
            )
            return Response({
                'message': f'{count} documentos reindexados',
                'case_id': case_id
            })

        elif reindex_all:
            # Reindexar todos los documentos (solo admin)
            if not request.user.role == 'admin':
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Solo administradores pueden reindexar todos los documentos")

            count = Document.objects.all().update(
                search_vector=(
                    SearchVector('name', weight='A') +
                    SearchVector('description', weight='B') +
                    SearchVector('text_content', weight='C')
                )
            )
            return Response({
                'message': f'{count} documentos reindexados'
            })

        return Response({
            'error': 'Debe especificar document_id, case_id, o all=true'
        }, status=status.HTTP_400_BAD_REQUEST)
