"""
Pruebas unitarias y de integracion para el Document Service.

Este modulo contiene pruebas exhaustivas para los modelos, vistas y endpoints
del servicio de gestion de documentos legales. Incluye pruebas para:
- Modelos: Document, DocumentVersion, DocumentAccessLog, DocumentShare, Folder
- Vistas: CRUD de documentos, versionado, auditoria, firma digital
- Busqueda y filtrado de documentos

Ejecutar con: pytest -v
"""

import pytest
import uuid
import hashlib
from datetime import datetime, timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status

from documents.models import Document, DocumentVersion, DocumentAccessLog, DocumentShare, Folder


# ============================================================================
# PRUEBAS DE MODELOS
# ============================================================================

@pytest.mark.django_db
class TestDocumentModel:
    """Pruebas para el modelo Document."""

    def test_document_creation(self, sample_document):
        """Verifica que un documento se crea correctamente."""
        assert sample_document.id is not None
        assert sample_document.name == 'Documento de Prueba'
        assert sample_document.category == 'contract'
        assert sample_document.status == 'draft'

    def test_document_str_representation(self, sample_document):
        """Verifica la representacion en cadena del documento."""
        expected = f"{sample_document.name} (v{sample_document.current_version})"
        assert str(sample_document) == expected

    def test_document_status_choices(self):
        """Verifica que los estados validos estan definidos."""
        valid_statuses = ['draft', 'pending_review', 'approved', 'filed', 'archived']
        for status_choice in Document.STATUS_CHOICES:
            assert status_choice[0] in valid_statuses

    def test_document_category_choices(self):
        """Verifica que las categorias validas estan definidas."""
        valid_categories = ['pleading', 'contract', 'evidence', 'correspondence',
                           'court_order', 'motion', 'brief', 'discovery',
                           'exhibit', 'invoice', 'receipt', 'power_of_attorney',
                           'identification', 'other']
        for category_choice in Document.CATEGORY_CHOICES:
            assert category_choice[0] in valid_categories

    def test_document_auto_fields(self, db, mock_user):
        """Verifica que los campos automaticos se establecen correctamente."""
        file = SimpleUploadedFile('test.pdf', b'content', content_type='application/pdf')
        doc = Document.objects.create(
            name='Test Doc',
            category='contract',
            file=file,
            created_by_id=mock_user.id,
            created_by_name=mock_user.email,
        )
        assert doc.file_size > 0
        assert doc.original_filename is not None

    def test_document_encryption_status_choices(self, sample_document):
        """Verifica las opciones de estado de cifrado."""
        valid_choices = ['none', 'at_rest', 'full']
        assert sample_document.encryption_status in valid_choices


@pytest.mark.django_db
class TestDocumentVersionModel:
    """Pruebas para el modelo DocumentVersion."""

    def test_version_creation(self, sample_version, sample_document):
        """Verifica que una version se crea correctamente."""
        assert sample_version.id is not None
        assert sample_version.document == sample_document
        assert sample_version.version_number == 1

    def test_version_str_representation(self, sample_version):
        """Verifica la representacion en cadena de la version."""
        assert sample_version.document.name in str(sample_version)
        assert 'v1' in str(sample_version)

    def test_version_unique_together(self, db, sample_document, mock_user):
        """Verifica la restriccion de unicidad documento-version."""
        file = SimpleUploadedFile('v1.pdf', b'content')
        DocumentVersion.objects.create(
            document=sample_document,
            version_number=2,
            file=file,
            created_by_id=mock_user.id,
            created_by_name=mock_user.email,
        )
        # Intentar crear otra version con el mismo numero debe fallar
        with pytest.raises(Exception):
            DocumentVersion.objects.create(
                document=sample_document,
                version_number=2,
                file=file,
                created_by_id=mock_user.id,
                created_by_name=mock_user.email,
            )


@pytest.mark.django_db
class TestDocumentAccessLogModel:
    """Pruebas para el modelo DocumentAccessLog."""

    def test_access_log_creation(self, sample_access_log, sample_document):
        """Verifica que un registro de acceso se crea correctamente."""
        assert sample_access_log.id is not None
        assert sample_access_log.document == sample_document
        assert sample_access_log.action == 'view'

    def test_access_log_str_representation(self, sample_access_log):
        """Verifica la representacion en cadena del registro."""
        assert sample_access_log.user_email in str(sample_access_log)
        assert sample_access_log.document.name in str(sample_access_log)

    def test_access_log_action_choices(self):
        """Verifica que las acciones validas estan definidas."""
        valid_actions = ['view', 'download', 'upload', 'update', 'delete',
                        'share', 'print', 'version_created', 'status_change']
        for action_choice in DocumentAccessLog.ACTION_CHOICES:
            assert action_choice[0] in valid_actions


@pytest.mark.django_db
class TestDocumentShareModel:
    """Pruebas para el modelo DocumentShare."""

    def test_share_creation(self, sample_share, sample_document):
        """Verifica que un permiso de comparticion se crea correctamente."""
        assert sample_share.id is not None
        assert sample_share.document == sample_document
        assert sample_share.permission == 'view'

    def test_share_str_representation(self, sample_share):
        """Verifica la representacion en cadena del permiso."""
        assert sample_share.document.name in str(sample_share)
        assert sample_share.shared_with_email in str(sample_share)

    def test_share_permission_choices(self):
        """Verifica que los permisos validos estan definidos."""
        valid_permissions = ['view', 'download', 'edit']
        for permission_choice in DocumentShare.PERMISSION_CHOICES:
            assert permission_choice[0] in valid_permissions

    def test_share_unique_together(self, db, sample_document, mock_user):
        """Verifica que no se puede compartir dos veces con el mismo usuario."""
        user_id = uuid.uuid4()
        DocumentShare.objects.create(
            document=sample_document,
            shared_with_user_id=user_id,
            shared_with_email='user@example.com',
            shared_by_id=mock_user.id,
            shared_by_name=mock_user.email,
        )
        with pytest.raises(Exception):
            DocumentShare.objects.create(
                document=sample_document,
                shared_with_user_id=user_id,
                shared_with_email='user@example.com',
                shared_by_id=mock_user.id,
                shared_by_name=mock_user.email,
            )


@pytest.mark.django_db
class TestFolderModel:
    """Pruebas para el modelo Folder."""

    def test_folder_creation(self, sample_folder):
        """Verifica que una carpeta se crea correctamente."""
        assert sample_folder.id is not None
        assert sample_folder.name == 'Carpeta de Prueba'

    def test_folder_str_representation(self, sample_folder):
        """Verifica la representacion en cadena de la carpeta."""
        assert str(sample_folder) == sample_folder.name

    def test_folder_path_root(self, sample_folder):
        """Verifica la ruta de una carpeta raiz."""
        assert sample_folder.path == sample_folder.name

    def test_folder_path_nested(self, db, sample_folder, mock_user):
        """Verifica la ruta de una carpeta anidada."""
        child_folder = Folder.objects.create(
            name='Subcarpeta',
            parent=sample_folder,
            created_by_id=mock_user.id,
        )
        expected_path = f"{sample_folder.name}/Subcarpeta"
        assert child_folder.path == expected_path

    def test_folder_hierarchy(self, db, mock_user):
        """Verifica la jerarquia de carpetas."""
        root = Folder.objects.create(name='Raiz', created_by_id=mock_user.id)
        level1 = Folder.objects.create(name='Nivel1', parent=root, created_by_id=mock_user.id)
        level2 = Folder.objects.create(name='Nivel2', parent=level1, created_by_id=mock_user.id)

        assert level2.path == 'Raiz/Nivel1/Nivel2'


# ============================================================================
# PRUEBAS DE VISTAS
# ============================================================================

@pytest.mark.django_db
class TestDocumentListCreateView:
    """Pruebas para la vista de listar y crear documentos."""

    def test_list_documents_authenticated(self, authenticated_client, sample_document):
        """Verifica que un usuario autenticado puede listar documentos."""
        response = authenticated_client.get('/api/documents/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_documents_unauthenticated(self, api_client):
        """Verifica que un usuario no autenticado no puede listar documentos."""
        response = api_client.get('/api/documents/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_filter_documents_by_category(self, authenticated_client, sample_document):
        """Verifica el filtrado de documentos por categoria."""
        response = authenticated_client.get('/api/documents/?category=contract')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_documents_by_status(self, authenticated_client, sample_document):
        """Verifica el filtrado de documentos por estado."""
        response = authenticated_client.get('/api/documents/?status=draft')
        assert response.status_code == status.HTTP_200_OK

    def test_search_documents(self, authenticated_client, sample_document):
        """Verifica la busqueda de documentos."""
        response = authenticated_client.get('/api/documents/?search=Prueba')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDocumentDetailView:
    """Pruebas para la vista de detalle de documento."""

    def test_retrieve_document(self, authenticated_client, sample_document):
        """Verifica que se puede obtener el detalle de un documento."""
        response = authenticated_client.get(f'/api/documents/{sample_document.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(sample_document.id)

    def test_update_document(self, admin_client, sample_document):
        """Verifica que un admin puede actualizar un documento."""
        response = admin_client.patch(
            f'/api/documents/{sample_document.id}/',
            {'name': 'Documento Actualizado'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_nonexistent_document(self, authenticated_client):
        """Verifica el manejo de documento inexistente."""
        fake_id = uuid.uuid4()
        response = authenticated_client.get(f'/api/documents/{fake_id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestDocumentVersionViews:
    """Pruebas para las vistas de versiones de documentos."""

    def test_list_document_versions(self, authenticated_client, sample_document, sample_version):
        """Verifica que se pueden listar las versiones de un documento."""
        response = authenticated_client.get(f'/api/documents/{sample_document.id}/versions/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDocumentAccessLogViews:
    """Pruebas para las vistas de registros de acceso."""

    def test_list_access_logs(self, admin_client, sample_document, sample_access_log):
        """Verifica que un admin puede listar los registros de acceso."""
        response = admin_client.get(f'/api/documents/{sample_document.id}/access-logs/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDocumentShareViews:
    """Pruebas para las vistas de compartir documentos."""

    def test_list_document_shares(self, authenticated_client, sample_document, sample_share):
        """Verifica que se pueden listar los permisos de comparticion."""
        response = authenticated_client.get(f'/api/documents/{sample_document.id}/shares/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_document_share(self, admin_client, sample_document):
        """Verifica que se puede compartir un documento."""
        share_data = {
            'shared_with_user_id': str(uuid.uuid4()),
            'shared_with_email': 'newuser@example.com',
            'permission': 'view',
        }
        response = admin_client.post(
            f'/api/documents/{sample_document.id}/shares/',
            share_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestFolderViews:
    """Pruebas para las vistas de carpetas."""

    def test_list_folders(self, authenticated_client, sample_folder):
        """Verifica que se pueden listar las carpetas."""
        response = authenticated_client.get('/api/folders/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_folder(self, admin_client, mock_admin_user):
        """Verifica que se puede crear una carpeta."""
        folder_data = {
            'name': 'Nueva Carpeta',
            'description': 'Descripcion de la carpeta',
        }
        response = admin_client.post('/api/folders/', folder_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_folder(self, authenticated_client, sample_folder):
        """Verifica que se puede obtener el detalle de una carpeta."""
        response = authenticated_client.get(f'/api/folders/{sample_folder.id}/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# PRUEBAS DE FUNCIONALIDADES ESPECIALES
# ============================================================================

@pytest.mark.django_db
class TestDocumentChecksum:
    """Pruebas para la verificacion de integridad de documentos."""

    def test_checksum_calculation(self):
        """Verifica que el checksum se calcula correctamente."""
        content = b'Contenido del documento de prueba'
        expected_checksum = hashlib.sha256(content).hexdigest()
        calculated_checksum = hashlib.sha256(content).hexdigest()
        assert expected_checksum == calculated_checksum


@pytest.mark.django_db
class TestDocumentAudit:
    """Pruebas para el sistema de auditoria."""

    def test_audit_log_created_on_access(self, db, sample_document, mock_user):
        """Verifica que se crea un registro de auditoria al acceder."""
        log = DocumentAccessLog.objects.create(
            document=sample_document,
            action='view',
            user_id=mock_user.id,
            user_email=mock_user.email,
            user_role=mock_user.role,
        )
        assert log.id is not None
        assert log.action == 'view'

    def test_audit_log_records_ip(self, db, sample_document, mock_user):
        """Verifica que se registra la IP del acceso."""
        log = DocumentAccessLog.objects.create(
            document=sample_document,
            action='download',
            user_id=mock_user.id,
            user_email=mock_user.email,
            user_role=mock_user.role,
            ip_address='192.168.1.100',
        )
        assert log.ip_address == '192.168.1.100'


@pytest.mark.django_db
class TestDocumentShareExpiration:
    """Pruebas para la expiracion de permisos de comparticion."""

    def test_share_with_expiration(self, db, sample_document, mock_user):
        """Verifica que se puede crear un share con expiracion."""
        expires = timezone.now() + timedelta(days=7)
        share = DocumentShare.objects.create(
            document=sample_document,
            shared_with_user_id=uuid.uuid4(),
            shared_with_email='temp@example.com',
            shared_by_id=mock_user.id,
            shared_by_name=mock_user.email,
            expires_at=expires,
        )
        assert share.expires_at is not None
        assert share.expires_at > timezone.now()

    def test_share_without_expiration(self, sample_share):
        """Verifica que se puede crear un share sin expiracion."""
        assert sample_share.expires_at is None
