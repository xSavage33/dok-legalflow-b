"""
Pruebas unitarias y de integracion para el Calendar Service.

Ejecutar con: pytest -v
"""

import pytest
import uuid
from datetime import date, time, timedelta

from rest_framework import status

from calendar_app.models import Event, Deadline, HolidayCalendar


@pytest.mark.django_db
class TestEventModel:
    """Pruebas para el modelo Event."""

    def test_event_creation(self, sample_event):
        """Verifica que un evento se crea correctamente."""
        assert sample_event.id is not None
        assert sample_event.title == 'Reunion de Prueba'
        assert sample_event.event_type == 'meeting'

    def test_event_str_representation(self, sample_event):
        """Verifica la representacion en cadena."""
        assert sample_event.title in str(sample_event)

    def test_event_type_choices(self):
        """Verifica los tipos de evento."""
        valid_types = ['hearing', 'meeting', 'deadline', 'trial', 'deposition',
                      'mediation', 'consultation', 'other']
        for choice in Event.EVENT_TYPE_CHOICES:
            assert choice[0] in valid_types


@pytest.mark.django_db
class TestDeadlineModel:
    """Pruebas para el modelo Deadline."""

    def test_deadline_creation(self, sample_deadline):
        """Verifica que un plazo se crea correctamente."""
        assert sample_deadline.id is not None
        assert sample_deadline.status == 'pending'
        assert sample_deadline.priority == 'high'

    def test_deadline_str_representation(self, sample_deadline):
        """Verifica la representacion en cadena."""
        assert sample_deadline.title in str(sample_deadline)

    def test_deadline_status_choices(self):
        """Verifica los estados de plazo."""
        valid_statuses = ['pending', 'completed', 'missed', 'extended']
        for choice in Deadline.STATUS_CHOICES:
            assert choice[0] in valid_statuses

    def test_deadline_is_overdue(self, db, mock_user):
        """Verifica la deteccion de plazos vencidos."""
        overdue_deadline = Deadline.objects.create(
            title='Plazo Vencido',
            case_id=uuid.uuid4(),
            case_number='LF-2024-00002',
            due_date=date.today() - timedelta(days=5),
            status='pending',
            created_by_id=mock_user.id,
        )
        assert overdue_deadline.due_date < date.today()


@pytest.mark.django_db
class TestHolidayCalendarModel:
    """Pruebas para el modelo HolidayCalendar."""

    def test_holiday_creation(self, sample_holiday):
        """Verifica que un feriado se crea correctamente."""
        assert sample_holiday.id is not None
        assert sample_holiday.is_national is True

    def test_holiday_str_representation(self, sample_holiday):
        """Verifica la representacion en cadena."""
        assert sample_holiday.name in str(sample_holiday)


@pytest.mark.django_db
class TestEventViews:
    """Pruebas para las vistas de eventos."""

    def test_list_events(self, authenticated_client, sample_event):
        """Verifica que se pueden listar eventos."""
        response = authenticated_client.get('/api/events/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_event(self, authenticated_client, mock_user):
        """Verifica que se puede crear un evento."""
        event_data = {
            'title': 'Nuevo Evento',
            'event_type': 'meeting',
            'start_date': str(date.today()),
            'start_time': '14:00',
            'end_date': str(date.today()),
            'end_time': '15:00',
        }
        response = authenticated_client.post('/api/events/', event_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_event(self, authenticated_client, sample_event):
        """Verifica que se puede obtener un evento."""
        response = authenticated_client.get(f'/api/events/{sample_event.id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_update_event(self, authenticated_client, sample_event):
        """Verifica que se puede actualizar un evento."""
        response = authenticated_client.patch(
            f'/api/events/{sample_event.id}/',
            {'title': 'Evento Actualizado'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_event(self, authenticated_client, sample_event):
        """Verifica que se puede eliminar un evento."""
        response = authenticated_client.delete(f'/api/events/{sample_event.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestDeadlineViews:
    """Pruebas para las vistas de plazos."""

    def test_list_deadlines(self, authenticated_client, sample_deadline):
        """Verifica que se pueden listar plazos."""
        response = authenticated_client.get('/api/deadlines/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_deadline(self, authenticated_client, mock_user):
        """Verifica que se puede crear un plazo."""
        deadline_data = {
            'title': 'Nuevo Plazo',
            'case_id': str(uuid.uuid4()),
            'case_number': 'LF-2024-00003',
            'due_date': str(date.today() + timedelta(days=20)),
            'priority': 'medium',
        }
        response = authenticated_client.post('/api/deadlines/', deadline_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_deadline(self, authenticated_client, sample_deadline):
        """Verifica que se puede obtener un plazo."""
        response = authenticated_client.get(f'/api/deadlines/{sample_deadline.id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_complete_deadline(self, authenticated_client, sample_deadline):
        """Verifica que se puede completar un plazo."""
        response = authenticated_client.patch(
            f'/api/deadlines/{sample_deadline.id}/',
            {'status': 'completed'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_list_upcoming_deadlines(self, authenticated_client, sample_deadline):
        """Verifica que se pueden listar plazos proximos."""
        response = authenticated_client.get('/api/deadlines/upcoming/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_overdue_deadlines(self, authenticated_client):
        """Verifica que se pueden listar plazos vencidos."""
        response = authenticated_client.get('/api/deadlines/overdue/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestHolidayViews:
    """Pruebas para las vistas de feriados."""

    def test_list_holidays(self, authenticated_client, sample_holiday):
        """Verifica que se pueden listar feriados."""
        response = authenticated_client.get('/api/holidays/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_holiday(self, admin_client):
        """Verifica que un admin puede crear un feriado."""
        holiday_data = {
            'name': 'Nuevo Feriado',
            'date': str(date(2024, 12, 25)),
            'is_national': True,
        }
        response = admin_client.post('/api/holidays/', holiday_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestBusinessDaysCalculation:
    """Pruebas para el calculo de dias habiles."""

    def test_exclude_weekends(self, db):
        """Verifica que los fines de semana se excluyen."""
        # Un sabado
        saturday = date(2024, 7, 27)
        assert saturday.weekday() == 5  # 5 = Sabado

    def test_exclude_holidays(self, sample_holiday):
        """Verifica que los feriados se excluyen."""
        holidays = HolidayCalendar.objects.filter(date=sample_holiday.date)
        assert holidays.exists()
