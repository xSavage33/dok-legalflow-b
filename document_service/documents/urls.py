"""
urls.py - Configuracion de URLs para el Servicio de Documentos

Este archivo define todas las rutas (endpoints) del API REST para el servicio
de documentos. Cada ruta mapea una URL a una vista especifica que maneja
las solicitudes HTTP.

Estructura de URLs:
- /documents/ - Operaciones CRUD de documentos
- /documents/<id>/ - Detalle de un documento especifico
- /documents/<id>/download/ - Descarga de archivo
- /documents/<document_id>/versions/ - Control de versiones
- /documents/<document_id>/access-log/ - Registro de auditoria
- /documents/<document_id>/shares/ - Comparticion de documentos
- /cases/<case_id>/documents/ - Documentos por caso
- /folders/ - Organizacion en carpetas
- /my-access-logs/ - Historial de acceso del usuario

Autor: Equipo de Desarrollo LegalFlow
"""

# Importacion de la funcion path para definir rutas de URL
from django.urls import path

# Importacion del modulo de vistas para acceder a todas las clases de vista
from . import views

# Lista de patrones de URL para la aplicacion de documentos
# Cada elemento es una tupla con: (patron_url, vista, nombre_ruta)
urlpatterns = [

    # ========================================================================
    # ENDPOINTS DE DOCUMENTOS
    # ========================================================================

    # Endpoint: /documents/
    # Metodos HTTP: GET (listar), POST (crear)
    # GET: Lista todos los documentos con filtrado, busqueda y paginacion
    # POST: Crea un nuevo documento con archivo adjunto
    path(
        'documents/',
        views.DocumentListCreateView.as_view(),
        name='document_list_create'
    ),

    # Endpoint: /documents/<uuid:id>/
    # Metodos HTTP: GET (detalle), PUT/PATCH (actualizar), DELETE (eliminar)
    # <uuid:id> captura un UUID valido de la URL y lo pasa a la vista
    # GET: Obtiene todos los detalles de un documento incluyendo versiones y shares
    # PUT/PATCH: Actualiza los campos del documento (no el archivo)
    # DELETE: Elimina el documento y todas sus versiones
    path(
        'documents/<uuid:id>/',
        views.DocumentDetailView.as_view(),
        name='document_detail'
    ),

    # Endpoint: /documents/<uuid:id>/download/
    # Metodos HTTP: GET
    # Descarga el archivo del documento actual (ultima version)
    # Retorna el archivo con el nombre original y fuerza descarga
    path(
        'documents/<uuid:id>/download/',
        views.DocumentDownloadView.as_view(),
        name='document_download'
    ),

    # ========================================================================
    # ENDPOINTS DE VERSIONES DE DOCUMENTOS
    # ========================================================================

    # Endpoint: /documents/<uuid:document_id>/versions/
    # Metodos HTTP: GET (listar versiones), POST (crear nueva version)
    # GET: Lista todas las versiones del documento
    # POST: Crea una nueva version subiendo un nuevo archivo
    path(
        'documents/<uuid:document_id>/versions/',
        views.DocumentVersionListCreateView.as_view(),
        name='document_versions'
    ),

    # Endpoint: /documents/<uuid:document_id>/versions/<int:version_number>/download/
    # Metodos HTTP: GET
    # <int:version_number> captura el numero de version como entero
    # Descarga una version especifica del documento
    # Util para obtener versiones anteriores del archivo
    path(
        'documents/<uuid:document_id>/versions/<int:version_number>/download/',
        views.DocumentVersionDownloadView.as_view(),
        name='version_download'
    ),

    # ========================================================================
    # ENDPOINTS DE REGISTRO DE ACCESO (AUDITORIA)
    # ========================================================================

    # Endpoint: /documents/<uuid:document_id>/access-log/
    # Metodos HTTP: GET
    # Lista el historial de accesos y acciones sobre un documento
    # Incluye: visualizaciones, descargas, actualizaciones, etc.
    path(
        'documents/<uuid:document_id>/access-log/',
        views.DocumentAccessLogView.as_view(),
        name='document_access_log'
    ),

    # ========================================================================
    # ENDPOINTS DE COMPARTICION DE DOCUMENTOS
    # ========================================================================

    # Endpoint: /documents/<uuid:document_id>/shares/
    # Metodos HTTP: GET (listar shares), POST (crear share)
    # GET: Lista todos los permisos de comparticion del documento
    # POST: Comparte el documento con un usuario (crea o actualiza permiso)
    path(
        'documents/<uuid:document_id>/shares/',
        views.DocumentShareView.as_view(),
        name='document_shares'
    ),

    # Endpoint: /documents/<uuid:document_id>/shares/<uuid:id>/
    # Metodos HTTP: DELETE
    # Elimina un permiso de comparticion especifico
    # Revoca el acceso del usuario al documento
    path(
        'documents/<uuid:document_id>/shares/<uuid:id>/',
        views.DocumentShareDeleteView.as_view(),
        name='document_share_delete'
    ),

    # ========================================================================
    # ENDPOINTS DE DOCUMENTOS POR CASO
    # ========================================================================

    # Endpoint: /cases/<uuid:case_id>/documents/
    # Metodos HTTP: GET
    # Lista todos los documentos asociados a un caso legal especifico
    # Soporta busqueda y ordenamiento
    path(
        'cases/<uuid:case_id>/documents/',
        views.DocumentByCaseView.as_view(),
        name='case_documents'
    ),

    # ========================================================================
    # ENDPOINTS DE CARPETAS
    # ========================================================================

    # Endpoint: /folders/
    # Metodos HTTP: GET (listar), POST (crear)
    # GET: Lista las carpetas raiz (sin padre)
    #      Se puede filtrar por caso con ?case_id=<uuid>
    # POST: Crea una nueva carpeta
    path(
        'folders/',
        views.FolderListCreateView.as_view(),
        name='folder_list_create'
    ),

    # Endpoint: /folders/<uuid:id>/
    # Metodos HTTP: GET (detalle), PUT/PATCH (actualizar), DELETE (eliminar)
    # GET: Obtiene los detalles de una carpeta incluyendo sus hijos
    # PUT/PATCH: Actualiza los campos de la carpeta
    # DELETE: Elimina la carpeta y sus subcarpetas en cascada
    path(
        'folders/<uuid:id>/',
        views.FolderDetailView.as_view(),
        name='folder_detail'
    ),

    # ========================================================================
    # ENDPOINTS DE FIRMA DIGITAL
    # ========================================================================

    # Endpoint: /documents/<uuid:id>/sign/
    # Metodos HTTP: POST
    # Firma digitalmente un documento usando criptografia RSA-SHA256
    # Genera un hash del documento y lo firma con clave privada
    path(
        'documents/<uuid:id>/sign/',
        views.DocumentSignatureView.as_view(),
        name='document_sign'
    ),

    # Endpoint: /documents/<uuid:id>/verify-signature/
    # Metodos HTTP: GET
    # Verifica la firma digital de un documento
    # Comprueba que el documento no haya sido modificado despues de firmarse
    path(
        'documents/<uuid:id>/verify-signature/',
        views.VerifySignatureView.as_view(),
        name='document_verify_signature'
    ),

    # ========================================================================
    # ENDPOINTS DE BUSQUEDA AVANZADA
    # ========================================================================

    # Endpoint: /documents/search/advanced/
    # Metodos HTTP: POST
    # Busqueda avanzada con multiples criterios de filtrado:
    # - Texto en nombre, descripcion, tags
    # - Rango de fechas de creacion
    # - Multiples categorias y estados
    # - Filtros de metadatos personalizados
    # - Filtros de tamano de archivo
    path(
        'documents/search/advanced/',
        views.AdvancedSearchView.as_view(),
        name='document_advanced_search'
    ),

    # ========================================================================
    # ENDPOINTS DE BUSQUEDA FULL-TEXT
    # ========================================================================

    # Endpoint: /documents/search/fulltext/
    # Metodos HTTP: POST
    # Busqueda full-text en el contenido de los documentos
    # Busca dentro de PDFs, Word, Excel, etc.
    # Soporta operadores de busqueda avanzados
    path(
        'documents/search/fulltext/',
        views.FullTextSearchView.as_view(),
        name='document_fulltext_search'
    ),

    # Endpoint: /documents/<uuid:id>/extract-text/
    # Metodos HTTP: POST
    # Extrae el texto de un documento especifico para indexarlo
    path(
        'documents/<uuid:id>/extract-text/',
        views.ExtractTextView.as_view(),
        name='document_extract_text'
    ),

    # Endpoint: /documents/extract-text/bulk/
    # Metodos HTTP: POST
    # Extrae texto de multiples documentos en batch
    # Util para indexar documentos existentes
    path(
        'documents/extract-text/bulk/',
        views.BulkExtractTextView.as_view(),
        name='document_extract_text_bulk'
    ),

    # Endpoint: /documents/reindex/
    # Metodos HTTP: POST
    # Reindexar vectores de busqueda de documentos
    # Util despues de cambios en metadatos
    path(
        'documents/reindex/',
        views.ReindexSearchView.as_view(),
        name='document_reindex'
    ),

    # ========================================================================
    # ENDPOINTS DE USUARIO
    # ========================================================================

    # Endpoint: /my-access-logs/
    # Metodos HTTP: GET
    # Lista las ultimas 100 acciones realizadas por el usuario autenticado
    # Permite al usuario ver su propio historial de actividad
    path(
        'my-access-logs/',
        views.UserAccessLogsView.as_view(),
        name='user_access_logs'
    ),
]
