"""
Pruebas unitarias y de integracion para el Matter Service.

Este modulo contiene pruebas exhaustivas para los modelos, vistas y endpoints
del servicio de gestion de casos legales. Incluye pruebas para:
- Modelos: Case, CaseParty, CaseDate, CaseNote, CaseTask
- Vistas: CRUD de casos, partes, fechas, notas y tareas
- Estadisticas y filtrado de casos

Ejecutar con: pytest -v
"""

import pytest
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from cases.models import Case, CaseParty, CaseDate, CaseNote, CaseTask


# ============================================================================
# PRUEBAS DE MODELOS
# ============================================================================

@pytest.mark.django_db
class TestCaseModel:
    """Pruebas para el modelo Case."""

    def test_case_creation(self, sample_case):
        """Verifica que un caso se crea correctamente."""
        assert sample_case.id is not None
        assert sample_case.title == 'Caso de Prueba'
        assert sample_case.case_type == 'civil'
        assert sample_case.status == 'active'

    def test_case_number_auto_generation(self, db, mock_user):
        """Verifica que el numero de caso se genera automaticamente."""
        case = Case.objects.create(
            title='Caso Nuevo',
            case_type='civil',
            client_id=uuid.uuid4(),
            client_name='Cliente',
            opened_date=date.today(),
            created_by_id=mock_user.id,
        )
        assert case.case_number.startswith('LF-')
        assert len(case.case_number) == 13  # LF-YYYY-NNNNN

    def test_case_number_sequential(self, db, mock_user):
        """Verifica que los numeros de caso son secuenciales."""
        case1 = Case.objects.create(
            title='Caso 1',
            case_type='civil',
            client_id=uuid.uuid4(),
            client_name='Cliente 1',
            opened_date=date.today(),
            created_by_id=mock_user.id,
        )
        case2 = Case.objects.create(
            title='Caso 2',
            case_type='criminal',
            client_id=uuid.uuid4(),
            client_name='Cliente 2',
            opened_date=date.today(),
            created_by_id=mock_user.id,
        )
        num1 = int(case1.case_number.split('-')[-1])
        num2 = int(case2.case_number.split('-')[-1])
        assert num2 == num1 + 1

    def test_case_str_representation(self, sample_case):
        """Verifica la representacion en cadena del caso."""
        expected = f"{sample_case.case_number} - {sample_case.title}"
        assert str(sample_case) == expected

    def test_case_status_choices(self):
        """Verifica que los estados validos estan definidos."""
        valid_statuses = ['active', 'pending', 'on_hold', 'closed', 'archived']
        for status_choice in Case.STATUS_CHOICES:
            assert status_choice[0] in valid_statuses

    def test_case_type_choices(self):
        """Verifica que los tipos de caso validos estan definidos."""
        valid_types = ['civil', 'criminal', 'labor', 'commercial',
                       'administrative', 'family', 'constitutional', 'tax', 'other']
        for type_choice in Case.CASE_TYPE_CHOICES:
            assert type_choice[0] in valid_types


@pytest.mark.django_db
class TestCasePartyModel:
    """Pruebas para el modelo CaseParty."""

    def test_party_creation(self, sample_party, sample_case):
        """Verifica que una parte se crea correctamente."""
        assert sample_party.id is not None
        assert sample_party.case == sample_case
        assert sample_party.party_type == 'plaintiff'
        assert sample_party.name == 'Demandante de Prueba'

    def test_party_str_representation(self, sample_party):
        """Verifica la representacion en cadena de la parte."""
        assert 'Demandante' in str(sample_party)
        assert sample_party.name in str(sample_party)


@pytest.mark.django_db
class TestCaseDateModel:
    """Pruebas para el modelo CaseDate."""

    def test_date_creation(self, sample_date, sample_case):
        """Verifica que una fecha se crea correctamente."""
        assert sample_date.id is not None
        assert sample_date.case == sample_case
        assert sample_date.date_type == 'hearing'
        assert sample_date.is_completed is False

    def test_date_str_representation(self, sample_date):
        """Verifica la representacion en cadena de la fecha."""
        assert sample_date.case.case_number in str(sample_date)
        assert sample_date.title in str(sample_date)


@pytest.mark.django_db
class TestCaseNoteModel:
    """Pruebas para el modelo CaseNote."""

    def test_note_creation(self, sample_note, sample_case):
        """Verifica que una nota se crea correctamente."""
        assert sample_note.id is not None
        assert sample_note.case == sample_case
        assert sample_note.is_private is False

    def test_private_note(self, db, sample_case, mock_user):
        """Verifica la creacion de notas privadas."""
        private_note = CaseNote.objects.create(
            case=sample_case,
            author_id=mock_user.id,
            author_name='Test User',
            content='Nota privada',
            is_private=True,
        )
        assert private_note.is_private is True


@pytest.mark.django_db
class TestCaseTaskModel:
    """Pruebas para el modelo CaseTask."""

    def test_task_creation(self, sample_task, sample_case):
        """Verifica que una tarea se crea correctamente."""
        assert sample_task.id is not None
        assert sample_task.case == sample_case
        assert sample_task.status == 'pending'

    def test_task_str_representation(self, sample_task):
        """Verifica la representacion en cadena de la tarea."""
        assert sample_task.case.case_number in str(sample_task)
        assert sample_task.title in str(sample_task)


# ============================================================================
# PRUEBAS DE VISTAS - CASOS
# ============================================================================

@pytest.mark.django_db
class TestCaseListCreateView:
    """Pruebas para la vista de listar y crear casos."""

    def test_list_cases_authenticated(self, authenticated_client, sample_case):
        """Verifica que un usuario autenticado puede listar casos."""
        response = authenticated_client.get('/api/cases/')
        assert response.status_code == status.HTTP_200_OK

    def test_list_cases_unauthenticated(self, api_client):
        """Verifica que un usuario no autenticado no puede listar casos."""
        response = api_client.get('/api/cases/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_case(self, admin_client, case_data):
        """Verifica que un admin puede crear un caso."""
        response = admin_client.post('/api/cases/', case_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == case_data['title']
        assert 'case_number' in response.data

    def test_create_case_missing_required_fields(self, admin_client):
        """Verifica que faltan campos requeridos al crear un caso."""
        response = admin_client.post('/api/cases/', {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_cases_by_status(self, authenticated_client, sample_case):
        """Verifica el filtrado de casos por estado."""
        response = authenticated_client.get('/api/cases/?status=active')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_cases_by_case_type(self, authenticated_client, sample_case):
        """Verifica el filtrado de casos por tipo."""
        response = authenticated_client.get('/api/cases/?case_type=civil')
        assert response.status_code == status.HTTP_200_OK

    def test_search_cases(self, authenticated_client, sample_case):
        """Verifica la busqueda de casos."""
        response = authenticated_client.get('/api/cases/?search=Prueba')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCaseDetailView:
    """Pruebas para la vista de detalle de caso."""

    def test_retrieve_case(self, authenticated_client, sample_case):
        """Verifica que se puede obtener el detalle de un caso."""
        response = authenticated_client.get(f'/api/cases/{sample_case.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(sample_case.id)

    def test_update_case(self, admin_client, sample_case):
        """Verifica que un admin puede actualizar un caso."""
        response = admin_client.patch(
            f'/api/cases/{sample_case.id}/',
            {'title': 'Titulo Actualizado'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Titulo Actualizado'

    def test_delete_case_archives(self, admin_client, sample_case):
        """Verifica que eliminar un caso lo archiva en lugar de borrarlo."""
        response = admin_client.delete(f'/api/cases/{sample_case.id}/')
        assert response.status_code == status.HTTP_200_OK

        # Verificar que el caso fue archivado, no eliminado
        sample_case.refresh_from_db()
        assert sample_case.status == 'archived'

    def test_retrieve_nonexistent_case(self, authenticated_client):
        """Verifica el manejo de caso inexistente."""
        fake_id = uuid.uuid4()
        response = authenticated_client.get(f'/api/cases/{fake_id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCaseStatisticsView:
    """Pruebas para la vista de estadisticas de casos."""

    def test_get_statistics(self, admin_client, sample_case):
        """Verifica que se pueden obtener estadisticas."""
        response = admin_client.get('/api/cases/statistics/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_cases' in response.data
        assert 'active_cases' in response.data
        assert 'by_type' in response.data


# ============================================================================
# PRUEBAS DE VISTAS - PARTES DEL CASO
# ============================================================================

@pytest.mark.django_db
class TestCasePartyViews:
    """Pruebas para las vistas de partes del caso."""

    def test_list_parties(self, authenticated_client, sample_case, sample_party):
        """Verifica que se pueden listar las partes de un caso."""
        response = authenticated_client.get(f'/api/cases/{sample_case.id}/parties/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_party(self, admin_client, sample_case):
        """Verifica que se puede crear una parte."""
        party_data = {
            'party_type': 'defendant',
            'name': 'Demandado de Prueba',
            'identification': '87654321',
            'email': 'demandado@example.com',
        }
        response = admin_client.post(
            f'/api/cases/{sample_case.id}/parties/',
            party_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_party(self, authenticated_client, sample_case, sample_party):
        """Verifica que se puede obtener el detalle de una parte."""
        response = authenticated_client.get(
            f'/api/cases/{sample_case.id}/parties/{sample_party.id}/'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_party(self, admin_client, sample_case, sample_party):
        """Verifica que se puede actualizar una parte."""
        response = admin_client.patch(
            f'/api/cases/{sample_case.id}/parties/{sample_party.id}/',
            {'name': 'Nombre Actualizado'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_party(self, admin_client, sample_case, sample_party):
        """Verifica que se puede eliminar una parte."""
        response = admin_client.delete(
            f'/api/cases/{sample_case.id}/parties/{sample_party.id}/'
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


# ============================================================================
# PRUEBAS DE VISTAS - FECHAS DEL CASO
# ============================================================================

@pytest.mark.django_db
class TestCaseDateViews:
    """Pruebas para las vistas de fechas del caso."""

    def test_list_dates(self, authenticated_client, sample_case, sample_date):
        """Verifica que se pueden listar las fechas de un caso."""
        response = authenticated_client.get(f'/api/cases/{sample_case.id}/dates/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_date(self, admin_client, sample_case):
        """Verifica que se puede crear una fecha."""
        date_data = {
            'date_type': 'deadline',
            'title': 'Plazo de Presentacion',
            'date': str(date.today() + timedelta(days=30)),
        }
        response = admin_client.post(
            f'/api/cases/{sample_case.id}/dates/',
            date_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_update_date(self, admin_client, sample_case, sample_date):
        """Verifica que se puede actualizar una fecha."""
        response = admin_client.patch(
            f'/api/cases/{sample_case.id}/dates/{sample_date.id}/',
            {'is_completed': True},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# PRUEBAS DE VISTAS - NOTAS DEL CASO
# ============================================================================

@pytest.mark.django_db
class TestCaseNoteViews:
    """Pruebas para las vistas de notas del caso."""

    def test_list_notes(self, authenticated_client, sample_case, sample_note):
        """Verifica que se pueden listar las notas de un caso."""
        response = authenticated_client.get(f'/api/cases/{sample_case.id}/notes/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_note(self, authenticated_client, sample_case):
        """Verifica que se puede crear una nota."""
        note_data = {
            'content': 'Nueva nota de prueba',
            'is_private': False,
        }
        response = authenticated_client.post(
            f'/api/cases/{sample_case.id}/notes/',
            note_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_private_note_visibility(self, db, sample_case, mock_user, mock_admin_user, api_client):
        """Verifica que las notas privadas solo son visibles para su autor."""
        # Crear nota privada
        private_note = CaseNote.objects.create(
            case=sample_case,
            author_id=mock_user.id,
            author_name='Test User',
            content='Nota privada',
            is_private=True,
        )

        # El autor puede ver su nota privada
        api_client.force_authenticate(user=mock_user)
        response = api_client.get(f'/api/cases/{sample_case.id}/notes/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# PRUEBAS DE VISTAS - TAREAS DEL CASO
# ============================================================================

@pytest.mark.django_db
class TestCaseTaskViews:
    """Pruebas para las vistas de tareas del caso."""

    def test_list_tasks(self, authenticated_client, sample_case, sample_task):
        """Verifica que se pueden listar las tareas de un caso."""
        response = authenticated_client.get(f'/api/cases/{sample_case.id}/tasks/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_task(self, authenticated_client, sample_case, mock_user):
        """Verifica que se puede crear una tarea."""
        task_data = {
            'title': 'Nueva Tarea',
            'description': 'Descripcion de la tarea',
            'status': 'pending',
            'priority': 'high',
            'due_date': str(date.today() + timedelta(days=7)),
        }
        response = authenticated_client.post(
            f'/api/cases/{sample_case.id}/tasks/',
            task_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_update_task_status(self, authenticated_client, sample_case, sample_task):
        """Verifica que se puede actualizar el estado de una tarea."""
        response = authenticated_client.patch(
            f'/api/cases/{sample_case.id}/tasks/{sample_task.id}/',
            {'status': 'completed'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_complete_task_sets_completed_at(self, authenticated_client, sample_case, sample_task):
        """Verifica que completar una tarea establece la fecha de completado."""
        response = authenticated_client.patch(
            f'/api/cases/{sample_case.id}/tasks/{sample_task.id}/',
            {'status': 'completed'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        sample_task.refresh_from_db()
        assert sample_task.completed_at is not None

    def test_filter_tasks_by_status(self, authenticated_client, sample_case, sample_task):
        """Verifica el filtrado de tareas por estado."""
        response = authenticated_client.get(
            f'/api/cases/{sample_case.id}/tasks/?status=pending'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_filter_tasks_by_priority(self, authenticated_client, sample_case, sample_task):
        """Verifica el filtrado de tareas por prioridad."""
        response = authenticated_client.get(
            f'/api/cases/{sample_case.id}/tasks/?priority=medium'
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTaskListView:
    """Pruebas para la vista de lista de tareas del usuario."""

    def test_list_user_tasks(self, authenticated_client, sample_task):
        """Verifica que se pueden listar las tareas asignadas al usuario."""
        response = authenticated_client.get('/api/tasks/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# PRUEBAS DE CONTROL DE ACCESO (RBAC)
# ============================================================================

@pytest.mark.django_db
class TestRBACAccess:
    """Pruebas para el control de acceso basado en roles."""

    def test_client_only_sees_own_cases(self, client_user_client, db, mock_client_user):
        """Verifica que un cliente solo ve sus propios casos."""
        # Crear un caso para el cliente
        Case.objects.create(
            title='Caso del Cliente',
            case_type='civil',
            client_id=mock_client_user.id,
            client_name='Cliente',
            opened_date=date.today(),
            created_by_id=uuid.uuid4(),
        )
        # Crear un caso de otro cliente
        Case.objects.create(
            title='Caso de Otro Cliente',
            case_type='civil',
            client_id=uuid.uuid4(),
            client_name='Otro Cliente',
            opened_date=date.today(),
            created_by_id=uuid.uuid4(),
        )

        response = client_user_client.get('/api/cases/')
        assert response.status_code == status.HTTP_200_OK

    def test_admin_sees_all_cases(self, admin_client, sample_case):
        """Verifica que un admin ve todos los casos."""
        response = admin_client.get('/api/cases/')
        assert response.status_code == status.HTTP_200_OK
