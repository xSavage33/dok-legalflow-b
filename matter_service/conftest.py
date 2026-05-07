"""
Configuracion de fixtures para pruebas del Matter Service.

Este archivo define fixtures reutilizables para pytest que proporcionan
objetos de prueba comunes como clientes API, usuarios simulados y casos de prueba.
"""

import pytest
import uuid
from datetime import date
from unittest.mock import MagicMock
from rest_framework.test import APIClient


class MockUser:
    """
    Clase mock que simula un usuario autenticado.

    Se utiliza para pruebas sin depender del servicio IAM real.
    """
    def __init__(self, user_id=None, email='test@example.com', role='associate'):
        self.id = user_id or uuid.uuid4()
        self.email = email
        self.role = role
        self.is_authenticated = True


@pytest.fixture
def api_client():
    """Retorna una instancia del cliente API de Django REST Framework."""
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
def mock_client_user():
    """Retorna un usuario mock con rol de cliente."""
    return MockUser(email='client@example.com', role='client')


@pytest.fixture
def authenticated_client(api_client, mock_user):
    """
    Retorna un cliente API autenticado con un usuario mock.

    Configura el cliente para simular autenticacion sin JWT real.
    """
    api_client.force_authenticate(user=mock_user)
    return api_client


@pytest.fixture
def admin_client(api_client, mock_admin_user):
    """Retorna un cliente API autenticado como administrador."""
    api_client.force_authenticate(user=mock_admin_user)
    return api_client


@pytest.fixture
def client_user_client(api_client, mock_client_user):
    """Retorna un cliente API autenticado como cliente."""
    api_client.force_authenticate(user=mock_client_user)
    return api_client


@pytest.fixture
def case_data(mock_user):
    """Retorna datos validos para crear un caso de prueba."""
    return {
        'title': 'Caso de Prueba vs. Demandado',
        'description': 'Descripcion del caso de prueba',
        'case_type': 'civil',
        'status': 'active',
        'priority': 'medium',
        'client_id': str(uuid.uuid4()),
        'client_name': 'Cliente de Prueba',
        'client_email': 'cliente@example.com',
        'jurisdiction': 'Juzgado Civil de Lima',
        'court': 'Primer Juzgado Civil',
        'opened_date': str(date.today()),
        'billing_type': 'hourly',
        'created_by_id': str(mock_user.id),
    }


@pytest.fixture
def sample_case(db, mock_user):
    """Crea y retorna un caso de prueba en la base de datos."""
    from cases.models import Case

    return Case.objects.create(
        title='Caso de Prueba',
        description='Descripcion del caso de prueba',
        case_type='civil',
        status='active',
        priority='medium',
        client_id=uuid.uuid4(),
        client_name='Cliente de Prueba',
        client_email='cliente@example.com',
        jurisdiction='Juzgado Civil',
        court='Primer Juzgado',
        opened_date=date.today(),
        billing_type='hourly',
        lead_attorney_id=mock_user.id,
        created_by_id=mock_user.id,
    )


@pytest.fixture
def sample_party(db, sample_case):
    """Crea y retorna una parte de prueba asociada a un caso."""
    from cases.models import CaseParty

    return CaseParty.objects.create(
        case=sample_case,
        party_type='plaintiff',
        name='Demandante de Prueba',
        identification='12345678',
        email='demandante@example.com',
        phone='999888777',
    )


@pytest.fixture
def sample_date(db, sample_case):
    """Crea y retorna una fecha de prueba asociada a un caso."""
    from cases.models import CaseDate

    return CaseDate.objects.create(
        case=sample_case,
        date_type='hearing',
        title='Audiencia de Prueba',
        description='Audiencia programada para el caso',
        date=date.today(),
        location='Sala 1',
    )


@pytest.fixture
def sample_note(db, sample_case, mock_user):
    """Crea y retorna una nota de prueba asociada a un caso."""
    from cases.models import CaseNote

    return CaseNote.objects.create(
        case=sample_case,
        author_id=mock_user.id,
        author_name='Test User',
        content='Esta es una nota de prueba',
        is_private=False,
    )


@pytest.fixture
def sample_task(db, sample_case, mock_user):
    """Crea y retorna una tarea de prueba asociada a un caso."""
    from cases.models import CaseTask

    return CaseTask.objects.create(
        case=sample_case,
        title='Tarea de Prueba',
        description='Descripcion de la tarea',
        status='pending',
        priority='medium',
        assigned_to_id=mock_user.id,
        assigned_to_name='Test User',
        due_date=date.today(),
        created_by_id=mock_user.id,
    )
