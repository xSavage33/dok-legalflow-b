"""
Pruebas unitarias y de integracion para el Billing Service.

Ejecutar con: pytest -v
"""

import pytest
import uuid
from datetime import date, timedelta
from decimal import Decimal

from rest_framework import status

from billing.models import Invoice, InvoiceItem, Payment, ClientRateAgreement


@pytest.mark.django_db
class TestInvoiceModel:
    """Pruebas para el modelo Invoice."""

    def test_invoice_creation(self, sample_invoice):
        """Verifica que una factura se crea correctamente."""
        assert sample_invoice.id is not None
        assert sample_invoice.invoice_number.startswith('INV-')
        assert sample_invoice.status == 'draft'

    def test_invoice_number_auto_generation(self, db, mock_user):
        """Verifica que el numero de factura se genera automaticamente."""
        from billing.models import Invoice

        invoice = Invoice.objects.create(
            client_id=uuid.uuid4(),
            client_name='Cliente',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            due_date=date.today() + timedelta(days=30),
            created_by_id=mock_user.id,
            created_by_name=mock_user.email,
        )
        assert invoice.invoice_number.startswith('INV-')

    def test_invoice_str_representation(self, sample_invoice):
        """Verifica la representacion en cadena."""
        assert sample_invoice.invoice_number in str(sample_invoice)

    def test_invoice_status_choices(self):
        """Verifica los estados de factura."""
        valid_statuses = ['draft', 'sent', 'paid', 'partial', 'overdue', 'cancelled']
        for choice in Invoice.STATUS_CHOICES:
            assert choice[0] in valid_statuses

    def test_invoice_balance_calculation(self, sample_invoice, sample_payment):
        """Verifica el calculo del saldo pendiente."""
        balance = sample_invoice.balance
        expected = sample_invoice.total - sample_payment.amount
        assert balance == expected


@pytest.mark.django_db
class TestInvoiceItemModel:
    """Pruebas para el modelo InvoiceItem."""

    def test_invoice_item_creation(self, sample_invoice_item, sample_invoice):
        """Verifica que un item de factura se crea correctamente."""
        assert sample_invoice_item.id is not None
        assert sample_invoice_item.invoice == sample_invoice
        assert sample_invoice_item.amount == Decimal('1000.00')


@pytest.mark.django_db
class TestPaymentModel:
    """Pruebas para el modelo Payment."""

    def test_payment_creation(self, sample_payment, sample_invoice):
        """Verifica que un pago se crea correctamente."""
        assert sample_payment.id is not None
        assert sample_payment.invoice == sample_invoice
        assert sample_payment.amount == Decimal('500.00')

    def test_payment_method_choices(self):
        """Verifica los metodos de pago."""
        valid_methods = ['cash', 'check', 'transfer', 'card', 'other']
        for choice in Payment.PAYMENT_METHOD_CHOICES:
            assert choice[0] in valid_methods


@pytest.mark.django_db
class TestInvoiceViews:
    """Pruebas para las vistas de facturas."""

    def test_list_invoices(self, authenticated_client, sample_invoice):
        """Verifica que se pueden listar facturas."""
        response = authenticated_client.get('/api/invoices/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_invoice(self, admin_client, mock_admin_user):
        """Verifica que se puede crear una factura."""
        invoice_data = {
            'client_id': str(uuid.uuid4()),
            'client_name': 'Nuevo Cliente',
            'client_email': 'nuevo@example.com',
            'subtotal': '500.00',
            'total': '500.00',
            'due_date': str(date.today() + timedelta(days=30)),
        }
        response = admin_client.post('/api/invoices/', invoice_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_invoice(self, authenticated_client, sample_invoice):
        """Verifica que se puede obtener una factura."""
        response = authenticated_client.get(f'/api/invoices/{sample_invoice.id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_update_invoice(self, admin_client, sample_invoice):
        """Verifica que se puede actualizar una factura."""
        response = admin_client.patch(
            f'/api/invoices/{sample_invoice.id}/',
            {'status': 'sent'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_status(self, authenticated_client, sample_invoice):
        """Verifica el filtrado por estado."""
        response = authenticated_client.get('/api/invoices/?status=draft')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_client(self, authenticated_client, sample_invoice):
        """Verifica el filtrado por cliente."""
        response = authenticated_client.get(
            f'/api/invoices/?client_id={sample_invoice.client_id}'
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestPaymentViews:
    """Pruebas para las vistas de pagos."""

    def test_list_payments(self, authenticated_client, sample_invoice, sample_payment):
        """Verifica que se pueden listar pagos de una factura."""
        response = authenticated_client.get(f'/api/invoices/{sample_invoice.id}/payments/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_payment(self, admin_client, sample_invoice):
        """Verifica que se puede registrar un pago."""
        payment_data = {
            'amount': '200.00',
            'payment_method': 'transfer',
            'reference_number': 'REF-002',
            'payment_date': str(date.today()),
        }
        response = admin_client.post(
            f'/api/invoices/{sample_invoice.id}/payments/',
            payment_data,
            format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestInvoiceSummary:
    """Pruebas para el resumen de facturacion."""

    def test_get_summary(self, admin_client, sample_invoice):
        """Verifica que se puede obtener el resumen de facturacion."""
        response = admin_client.get('/api/invoices/summary/')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestOverdueInvoices:
    """Pruebas para facturas vencidas."""

    def test_overdue_invoice_detection(self, db, mock_user):
        """Verifica la deteccion de facturas vencidas."""
        from billing.models import Invoice

        overdue_invoice = Invoice.objects.create(
            client_id=uuid.uuid4(),
            client_name='Cliente',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            status='sent',
            due_date=date.today() - timedelta(days=10),
            created_by_id=mock_user.id,
            created_by_name=mock_user.email,
        )
        assert overdue_invoice.due_date < date.today()
