"""
Pruebas unitarias y de integracion para el Time Tracking Service.

Ejecutar con: pytest -v
"""

import pytest
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from timetracking.models import TimeEntry, Timer, UserRate, CaseRate


@pytest.mark.django_db
class TestTimeEntryModel:
    """Pruebas para el modelo TimeEntry."""

    def test_time_entry_creation(self, sample_time_entry):
        """Verifica que una entrada de tiempo se crea correctamente."""
        assert sample_time_entry.id is not None
        assert sample_time_entry.duration_minutes == 60
        assert sample_time_entry.is_billable is True

    def test_time_entry_amount_calculation(self, sample_time_entry):
        """Verifica el calculo del monto facturable."""
        expected_amount = (60 / 60) * Decimal('150.00')
        assert sample_time_entry.amount == expected_amount

    def test_time_entry_str_representation(self, sample_time_entry):
        """Verifica la representacion en cadena."""
        assert sample_time_entry.case_number in str(sample_time_entry)

    def test_activity_type_choices(self):
        """Verifica que los tipos de actividad estan definidos."""
        valid_types = ['research', 'drafting', 'review', 'meeting', 'court',
                      'travel', 'communication', 'administrative', 'other']
        for choice in TimeEntry.ACTIVITY_TYPE_CHOICES:
            assert choice[0] in valid_types


@pytest.mark.django_db
class TestTimerModel:
    """Pruebas para el modelo Timer."""

    def test_timer_creation(self, sample_timer):
        """Verifica que un temporizador se crea correctamente."""
        assert sample_timer.id is not None
        assert sample_timer.is_running is True
        assert sample_timer.start_time is not None

    def test_timer_elapsed_time(self, sample_timer):
        """Verifica el calculo del tiempo transcurrido."""
        elapsed = sample_timer.elapsed_minutes
        assert elapsed >= 0

    def test_timer_stop(self, sample_timer):
        """Verifica que se puede detener el temporizador."""
        sample_timer.is_running = False
        sample_timer.end_time = timezone.now()
        sample_timer.save()
        assert sample_timer.is_running is False


@pytest.mark.django_db
class TestUserRateModel:
    """Pruebas para el modelo UserRate."""

    def test_user_rate_creation(self, sample_user_rate):
        """Verifica que una tarifa de usuario se crea correctamente."""
        assert sample_user_rate.id is not None
        assert sample_user_rate.hourly_rate == Decimal('150.00')


@pytest.mark.django_db
class TestTimeEntryViews:
    """Pruebas para las vistas de entradas de tiempo."""

    def test_list_time_entries(self, authenticated_client, sample_time_entry):
        """Verifica que se pueden listar entradas de tiempo."""
        response = authenticated_client.get('/api/time-entries/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_time_entry(self, authenticated_client, mock_user):
        """Verifica que se puede crear una entrada de tiempo."""
        entry_data = {
            'case_id': str(uuid.uuid4()),
            'case_number': 'LF-2024-00002',
            'activity_type': 'drafting',
            'description': 'Redaccion de contrato',
            'date': str(date.today()),
            'duration_minutes': 90,
            'is_billable': True,
        }
        response = authenticated_client.post('/api/time-entries/', entry_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_time_entry(self, authenticated_client, sample_time_entry):
        """Verifica que se puede obtener una entrada de tiempo."""
        response = authenticated_client.get(f'/api/time-entries/{sample_time_entry.id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_update_time_entry(self, authenticated_client, sample_time_entry):
        """Verifica que se puede actualizar una entrada de tiempo."""
        response = authenticated_client.patch(
            f'/api/time-entries/{sample_time_entry.id}/',
            {'description': 'Descripcion actualizada'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_time_entry(self, authenticated_client, sample_time_entry):
        """Verifica que se puede eliminar una entrada de tiempo."""
        response = authenticated_client.delete(f'/api/time-entries/{sample_time_entry.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_filter_by_case(self, authenticated_client, sample_time_entry):
        """Verifica el filtrado por caso."""
        response = authenticated_client.get(
            f'/api/time-entries/?case_id={sample_time_entry.case_id}'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_date_range(self, authenticated_client, sample_time_entry):
        """Verifica el filtrado por rango de fechas."""
        today = date.today()
        response = authenticated_client.get(
            f'/api/time-entries/?date_from={today}&date_to={today}'
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTimerViews:
    """Pruebas para las vistas de temporizadores."""

    def test_list_timers(self, authenticated_client, sample_timer):
        """Verifica que se pueden listar temporizadores."""
        response = authenticated_client.get('/api/timers/')
        assert response.status_code == status.HTTP_200_OK

    def test_start_timer(self, authenticated_client):
        """Verifica que se puede iniciar un temporizador."""
        timer_data = {
            'case_id': str(uuid.uuid4()),
            'case_number': 'LF-2024-00003',
            'activity_type': 'research',
            'description': 'Investigacion de jurisprudencia',
        }
        response = authenticated_client.post('/api/timers/', timer_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_stop_timer(self, authenticated_client, sample_timer):
        """Verifica que se puede detener un temporizador."""
        response = authenticated_client.post(f'/api/timers/{sample_timer.id}/stop/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTimeEntrySummary:
    """Pruebas para el resumen de tiempo."""

    def test_get_summary(self, admin_client, sample_time_entry):
        """Verifica que se puede obtener el resumen de tiempo."""
        response = admin_client.get('/api/time-entries/summary/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_hours' in response.data or 'total_minutes' in response.data
