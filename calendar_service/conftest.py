"""
Configuracion de fixtures para pruebas del Calendar Service.
"""

import pytest
import uuid
from datetime import date, time, timedelta
from rest_framework.test import APIClient


class MockUser:
    """Clase mock que simula un usuario autenticado."""
    def __init__(self, user_id=None, email='test@example.com', role='associate'):
        self.id = user_id or uuid.uuid4()
        self.email = email
        self.role = role
        self.is_authenticated = True


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mock_user():
    return MockUser(role='associate')


@pytest.fixture
def mock_admin_user():
    return MockUser(email='admin@example.com', role='admin')


@pytest.fixture
def authenticated_client(api_client, mock_user):
    api_client.force_authenticate(user=mock_user)
    return api_client


@pytest.fixture
def admin_client(api_client, mock_admin_user):
    api_client.force_authenticate(user=mock_admin_user)
    return api_client


@pytest.fixture
def sample_event(db, mock_user):
    """Crea y retorna un evento de prueba."""
    from calendar_app.models import Event

    return Event.objects.create(
        title='Reunion de Prueba',
        description='Descripcion del evento',
        event_type='meeting',
        start_date=date.today(),
        start_time=time(10, 0),
        end_date=date.today(),
        end_time=time(11, 0),
        location='Sala de Reuniones',
        case_id=uuid.uuid4(),
        case_number='LF-2024-00001',
        created_by_id=mock_user.id,
        created_by_name=mock_user.email,
    )


@pytest.fixture
def sample_deadline(db, mock_user):
    """Crea y retorna un plazo de prueba."""
    from calendar_app.models import Deadline

    return Deadline.objects.create(
        title='Plazo de Apelacion',
        description='Presentar recurso de apelacion',
        case_id=uuid.uuid4(),
        case_number='LF-2024-00001',
        due_date=date.today() + timedelta(days=15),
        priority='high',
        status='pending',
        assigned_to_id=mock_user.id,
        assigned_to_name=mock_user.email,
        created_by_id=mock_user.id,
    )


@pytest.fixture
def sample_holiday(db):
    """Crea y retorna un dia feriado de prueba."""
    from calendar_app.models import HolidayCalendar

    return HolidayCalendar.objects.create(
        name='Dia de la Independencia',
        date=date(2024, 7, 28),
        is_national=True,
        jurisdiction='Peru',
    )
