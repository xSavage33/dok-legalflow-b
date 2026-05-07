"""
Configuracion de fixtures para pruebas del Billing Service.
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
def sample_invoice(db, mock_user):
    """Crea y retorna una factura de prueba."""
    from billing.models import Invoice

    return Invoice.objects.create(
        client_id=uuid.uuid4(),
        client_name='Cliente de Prueba',
        client_email='cliente@example.com',
        case_id=uuid.uuid4(),
        case_number='LF-2024-00001',
        subtotal=Decimal('1000.00'),
        tax_rate=Decimal('18.00'),
        tax_amount=Decimal('180.00'),
        total=Decimal('1180.00'),
        status='draft',
        due_date=date.today() + timedelta(days=30),
        created_by_id=mock_user.id,
        created_by_name=mock_user.email,
    )


@pytest.fixture
def sample_invoice_item(db, sample_invoice):
    """Crea y retorna un item de factura de prueba."""
    from billing.models import InvoiceItem

    return InvoiceItem.objects.create(
        invoice=sample_invoice,
        description='Servicios legales',
        quantity=Decimal('10.00'),
        unit_price=Decimal('100.00'),
        amount=Decimal('1000.00'),
        item_type='service',
    )


@pytest.fixture
def sample_payment(db, sample_invoice, mock_user):
    """Crea y retorna un pago de prueba."""
    from billing.models import Payment

    return Payment.objects.create(
        invoice=sample_invoice,
        amount=Decimal('500.00'),
        payment_method='transfer',
        reference_number='REF-001',
        payment_date=date.today(),
        recorded_by_id=mock_user.id,
        recorded_by_name=mock_user.email,
    )
