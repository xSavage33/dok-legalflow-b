"""
Configuracion de fixtures para pruebas del Time Tracking Service.
"""

import pytest
import uuid
from datetime import date, timedelta
from decimal import Decimal
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
def sample_time_entry(db, mock_user):
    """Crea y retorna una entrada de tiempo de prueba."""
    from timetracking.models import TimeEntry

    return TimeEntry.objects.create(
        user_id=mock_user.id,
        user_name=mock_user.email,
        case_id=uuid.uuid4(),
        case_number='LF-2024-00001',
        activity_type='research',
        description='Investigacion legal',
        date=date.today(),
        duration_minutes=60,
        hourly_rate=Decimal('150.00'),
        is_billable=True,
        created_by_id=mock_user.id,
    )


@pytest.fixture
def sample_timer(db, mock_user):
    """Crea y retorna un temporizador de prueba."""
    from timetracking.models import Timer
    from django.utils import timezone

    return Timer.objects.create(
        user_id=mock_user.id,
        case_id=uuid.uuid4(),
        case_number='LF-2024-00001',
        activity_type='meeting',
        description='Reunion con cliente',
        start_time=timezone.now(),
        is_running=True,
    )


@pytest.fixture
def sample_user_rate(db, mock_user):
    """Crea y retorna una tarifa de usuario de prueba."""
    from timetracking.models import UserRate

    return UserRate.objects.create(
        user_id=mock_user.id,
        hourly_rate=Decimal('150.00'),
        effective_from=date.today(),
    )
