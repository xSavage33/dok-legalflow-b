"""
Configuracion de fixtures para pruebas del Document Service.

Este archivo define fixtures reutilizables para pytest que proporcionan
objetos de prueba para documentos, versiones, y registros de auditoria.
"""

import pytest
import uuid
from io import BytesIO
from unittest.mock import MagicMock
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile


class MockUser:
    """
    Clase mock que simula un usuario autenticado.
    """
    def __init__(self, user_id=None, email='test@example.com', role='associate'):
        self.id = user_id or uuid.uuid4()
        self.email = email
        self.role = role
        self.is_authenticated = True


@pytest.fixture
def api_client():
    """Retorna una instancia del cliente API."""
    return APIClient()


@pytest.fixture
def mock_user():
    """Retorna un usuario mock con rol de abogado asociado."""
    return MockUser(role='associate')


@pytest.fixture
def mock_admin_user():
    """Retorna un usuario mock con rol de administrador."""
    return MockUser(email='admin@example.com', role='admin')


@pytest.fixture
def authenticated_client(api_client, mock_user):
    """Retorna un cliente API autenticado."""
    api_client.force_authenticate(user=mock_user)
    return api_client


@pytest.fixture
def admin_client(api_client, mock_admin_user):
    """Retorna un cliente API autenticado como administrador."""
    api_client.force_authenticate(user=mock_admin_user)
    return api_client


@pytest.fixture
def sample_file():
    """Crea y retorna un archivo de prueba."""
    content = b'Este es el contenido del documento de prueba.'
    return SimpleUploadedFile(
        name='documento_prueba.pdf',
        content=content,
        content_type='application/pdf'
    )


@pytest.fixture
def sample_document(db, mock_user, sample_file):
    """Crea y retorna un documento de prueba en la base de datos."""
    from documents.models import Document

    return Document.objects.create(
        name='Documento de Prueba',
        description='Descripcion del documento de prueba',
        category='contract',
        status='draft',
        file=sample_file,
        original_filename='documento_prueba.pdf',
        file_size=len(sample_file.read()),
        mime_type='application/pdf',
        checksum='abc123def456',
        case_id=uuid.uuid4(),
        created_by_id=mock_user.id,
        created_by_name=mock_user.email,
    )


@pytest.fixture
def sample_version(db, sample_document, mock_user, sample_file):
    """Crea y retorna una version de documento de prueba."""
    from documents.models import DocumentVersion

    return DocumentVersion.objects.create(
        document=sample_document,
        version_number=1,
        file=sample_file,
        file_size=len(sample_file.read()),
        checksum='abc123def456',
        changes_description='Version inicial',
        created_by_id=mock_user.id,
        created_by_name=mock_user.email,
    )


@pytest.fixture
def sample_access_log(db, sample_document, mock_user):
    """Crea y retorna un registro de acceso de prueba."""
    from documents.models import DocumentAccessLog

    return DocumentAccessLog.objects.create(
        document=sample_document,
        action='view',
        user_id=mock_user.id,
        user_email=mock_user.email,
        user_role=mock_user.role,
        ip_address='127.0.0.1',
        user_agent='Mozilla/5.0 Test',
    )


@pytest.fixture
def sample_share(db, sample_document, mock_user):
    """Crea y retorna un permiso de comparticion de prueba."""
    from documents.models import DocumentShare

    return DocumentShare.objects.create(
        document=sample_document,
        shared_with_user_id=uuid.uuid4(),
        shared_with_email='shared@example.com',
        permission='view',
        shared_by_id=mock_user.id,
        shared_by_name=mock_user.email,
    )


@pytest.fixture
def sample_folder(db, mock_user):
    """Crea y retorna una carpeta de prueba."""
    from documents.models import Folder

    return Folder.objects.create(
        name='Carpeta de Prueba',
        description='Carpeta para pruebas',
        case_id=uuid.uuid4(),
        created_by_id=mock_user.id,
    )
