"""
Modulo de Vistas del Servicio de Facturacion (Billing Service)

Este archivo define las vistas (endpoints) de la API REST para el sistema de
facturacion de LegalFlow. Utiliza Django REST Framework para proporcionar
una API robusta y bien estructurada.

Vistas incluidas:
- InvoiceListCreateView: Listar y crear facturas
- InvoiceDetailView: Ver, actualizar y eliminar facturas individuales
- InvoiceItemListCreateView: Gestionar items de facturas
- PaymentListCreateView: Registrar pagos
- SendInvoiceView: Cambiar estado de factura a enviada
- BillingSummaryView: Obtener resumen de facturacion
- ClientRateAgreementListCreateView: Gestionar acuerdos de tarifas
- ClientInvoicesView: Ver facturas por cliente
- CaseInvoicesView: Ver facturas por caso

Autor: Equipo de Desarrollo LegalFlow
Fecha de creacion: 2024
"""

# Importacion de clases genericas de Django REST Framework para crear vistas CRUD
# generics proporciona vistas predefinidas como ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework import generics, status, filters

# Importacion de Response para enviar respuestas HTTP personalizadas
from rest_framework.response import Response

# Importacion de APIView para crear vistas personalizadas sin comportamiento predefinido
from rest_framework.views import APIView

# Importacion de DjangoFilterBackend para filtrado avanzado de querysets
from django_filters.rest_framework import DjangoFilterBackend

# Importacion de funciones de agregacion de Django para calculos en base de datos
# Sum: suma de valores, Count: conteo de registros
from django.db.models import Sum, Count

# Importacion de timezone para manejo de fechas y horas con zona horaria
from django.utils import timezone

# Importacion de date para trabajar con fechas
from datetime import date

# Importacion de uuid para generar identificadores unicos
import uuid

# Importacion de requests para comunicacion HTTP con otros servicios
import requests

# Importacion de logging para registrar eventos y errores
import logging

# Importacion de settings para acceder a configuracion del proyecto
from django.conf import settings

# Importacion de los modelos definidos en este modulo
from .models import Invoice, InvoiceItem, Payment, ClientRateAgreement

# Configuracion del logger para este modulo
logger = logging.getLogger(__name__)

# Importacion de los serializadores para convertir modelos a JSON y viceversa
from .serializers import (
    InvoiceListSerializer,           # Serializador para listar facturas (campos resumidos)
    InvoiceDetailSerializer,         # Serializador para detalle de factura (todos los campos)
    InvoiceCreateSerializer,         # Serializador para crear facturas
    InvoiceItemSerializer,           # Serializador para items de factura
    PaymentSerializer,               # Serializador para pagos
    ClientRateAgreementSerializer,   # Serializador para acuerdos de tarifas
    BillingSummarySerializer,        # Serializador para resumen de facturacion
)


class InvoiceListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todas las facturas y crear nuevas facturas.

    Esta vista proporciona dos funcionalidades:
    - GET: Retorna una lista paginada de facturas con filtros y busqueda
    - POST: Crea una nueva factura con sus items opcionales

    Filtros disponibles:
    - client_id: Filtrar por ID de cliente
    - case_id: Filtrar por ID de caso
    - status: Filtrar por estado de la factura

    Busqueda:
    - Busca en invoice_number, client_name y case_number

    Ordenamiento:
    - Por defecto: mas recientes primero (-created_at)
    - Campos disponibles: created_at, issue_date, due_date, total_amount
    """

    # Queryset base que obtiene todas las facturas
    queryset = Invoice.objects.all()

    # Backends de filtrado habilitados para esta vista
    # DjangoFilterBackend: filtrado por campos exactos
    # SearchFilter: busqueda de texto
    # OrderingFilter: ordenamiento dinamico
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Campos por los que se puede filtrar (filtrado exacto)
    filterset_fields = ['client_id', 'case_id', 'status']

    # Campos en los que se realiza la busqueda de texto
    search_fields = ['invoice_number', 'client_name', 'case_number']

    # Campos por los que se puede ordenar el resultado
    ordering_fields = ['created_at', 'issue_date', 'due_date', 'total_amount']

    # Ordenamiento predeterminado: facturas mas recientes primero
    ordering = ['-created_at']

    def get_serializer_class(self):
        """
        Retorna el serializador apropiado segun el metodo HTTP.

        Para POST (crear): usa InvoiceCreateSerializer que permite enviar items
        Para GET (listar): usa InvoiceListSerializer con campos resumidos

        Returns:
            class: Clase del serializador a utilizar
        """
        # Si es una solicitud POST, usar el serializador de creacion
        if self.request.method == 'POST':
            return InvoiceCreateSerializer

        # Para GET y otros metodos, usar el serializador de lista
        return InvoiceListSerializer


class InvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar una factura individual.

    Esta vista proporciona tres funcionalidades:
    - GET: Retorna todos los detalles de una factura incluyendo items y pagos
    - PUT/PATCH: Actualiza los datos de la factura
    - DELETE: Elimina la factura (solo si no esta pagada)

    La factura se identifica por su UUID en la URL.
    """

    # Queryset base para obtener facturas
    queryset = Invoice.objects.all()

    # Serializador con todos los campos incluyendo items y pagos anidados
    serializer_class = InvoiceDetailSerializer

    # Campo usado para buscar la factura en la URL
    lookup_field = 'id'

    def perform_destroy(self, instance):
        """
        Ejecuta la eliminacion de la factura con validacion de negocio.

        No permite eliminar facturas que ya han sido pagadas para
        mantener la integridad del historial financiero.

        Args:
            instance: Instancia de Invoice a eliminar

        Raises:
            ValidationError: Si la factura tiene estado 'paid' (pagada)
        """
        # Verificar si la factura esta pagada
        if instance.status == 'paid':
            # Importar excepcion de validacion
            from rest_framework.exceptions import ValidationError

            # Lanzar error indicando que no se puede eliminar
            raise ValidationError('No se puede eliminar una factura pagada.')

        # Si no esta pagada, proceder con la eliminacion
        instance.delete()


class InvoiceItemListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear items de una factura especifica.

    Funcionalidades:
    - GET: Lista todos los items de una factura
    - POST: Agrega un nuevo item a la factura

    La factura se identifica por invoice_id en la URL.
    Despues de crear un item, recalcula automaticamente los totales de la factura.
    """

    # Serializador para items de factura
    serializer_class = InvoiceItemSerializer

    def get_queryset(self):
        """
        Filtra los items para mostrar solo los de la factura especificada.

        Returns:
            QuerySet: Items filtrados por invoice_id de la URL
        """
        # Obtener el invoice_id de los parametros de la URL
        # y filtrar los items que pertenecen a esa factura
        return InvoiceItem.objects.filter(invoice_id=self.kwargs['invoice_id'])

    def perform_create(self, serializer):
        """
        Crea un nuevo item y actualiza los totales de la factura.

        Args:
            serializer: Serializador validado con los datos del nuevo item
        """
        # Obtener la factura a la que se agregara el item
        invoice = Invoice.objects.get(id=self.kwargs['invoice_id'])

        # Guardar el item asociandolo a la factura
        serializer.save(invoice=invoice)

        # Recalcular los totales de la factura
        invoice.calculate_totals()

        # Guardar los cambios en la factura
        invoice.save()


class InvoiceItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un item individual de factura.

    Funcionalidades:
    - GET: Ver detalles del item
    - PUT/PATCH: Actualizar el item
    - DELETE: Eliminar el item (y recalcular totales de factura)

    El item se identifica por su id y debe pertenecer a la factura especificada.
    """

    # Serializador para items de factura
    serializer_class = InvoiceItemSerializer

    # Campo usado para buscar el item en la URL
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra los items para la factura especificada en la URL.

        Returns:
            QuerySet: Items de la factura especificada
        """
        # Filtrar items por el invoice_id de la URL
        return InvoiceItem.objects.filter(invoice_id=self.kwargs['invoice_id'])

    def perform_destroy(self, instance):
        """
        Elimina el item y recalcula los totales de la factura.

        Args:
            instance: Instancia de InvoiceItem a eliminar
        """
        # Guardar referencia a la factura antes de eliminar el item
        invoice = instance.invoice

        # Eliminar el item
        instance.delete()

        # Recalcular los totales de la factura sin el item eliminado
        invoice.calculate_totals()

        # Guardar los cambios en la factura
        invoice.save()


class PaymentListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y registrar pagos de una factura.

    Funcionalidades:
    - GET: Lista todos los pagos realizados a una factura
    - POST: Registra un nuevo pago para la factura

    El registro de un pago actualiza automaticamente:
    - El monto pagado de la factura
    - El saldo pendiente
    - El estado de la factura (parcial o pagada)
    """

    # Serializador para pagos
    serializer_class = PaymentSerializer

    def get_queryset(self):
        """
        Filtra los pagos para la factura especificada.

        Returns:
            QuerySet: Pagos de la factura especificada
        """
        # Filtrar pagos por el invoice_id de la URL
        return Payment.objects.filter(invoice_id=self.kwargs['invoice_id'])

    def perform_create(self, serializer):
        """
        Registra un nuevo pago asociandolo a la factura y al usuario actual.

        El modelo Payment se encarga automaticamente de actualizar
        los totales y estado de la factura en su metodo save().

        Args:
            serializer: Serializador validado con los datos del pago
        """
        # Obtener la factura a la que corresponde el pago
        invoice = Invoice.objects.get(id=self.kwargs['invoice_id'])

        # Guardar el pago con la factura y datos del usuario que lo registra
        serializer.save(
            invoice=invoice,
            recorded_by_id=self.request.user.id,      # ID del usuario autenticado
            recorded_by_name=self.request.user.email   # Email del usuario como nombre
        )


class SendInvoiceView(APIView):
    """
    Vista para cambiar el estado de una factura a 'enviada'.

    Esta vista se utiliza cuando el usuario envia la factura al cliente.
    Solo cambia el estado si la factura esta en estado 'draft' (borrador).
    Ademas, envia una notificacion al cliente a traves del portal.

    Metodo HTTP:
    - POST: Marca la factura como enviada y notifica al cliente
    """

    def post(self, request, id):
        """
        Procesa la solicitud de envio de factura.

        Cambia el estado de la factura de 'draft' a 'sent' si corresponde,
        envia el email con el PDF adjunto y notifica al cliente en el portal.

        Args:
            request: Objeto de solicitud HTTP
            id: UUID de la factura a enviar

        Body opcional:
            send_email (bool): Si enviar email (default: True)
            cc_emails (list): Lista de emails en copia
            custom_message (str): Mensaje personalizado

        Returns:
            Response: Mensaje de confirmacion o error
        """
        # Importar el servicio de email
        from .email_service import send_invoice_email

        try:
            # Intentar obtener la factura por su ID
            invoice = Invoice.objects.get(id=id)
        except Invoice.DoesNotExist:
            # Si no existe, retornar error 404
            return Response(
                {'error': 'Factura no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Obtener opciones del body
        send_email = request.data.get('send_email', True)
        cc_emails = request.data.get('cc_emails', [])
        custom_message = request.data.get('custom_message', '')

        email_result = None

        # Solo cambiar estado si la factura esta en borrador
        if invoice.status == 'draft':
            # Actualizar estado a enviada
            invoice.status = 'sent'

            # Guardar cambios en la base de datos
            invoice.save()

            # Enviar email con PDF si esta habilitado
            if send_email and invoice.client_email:
                email_result = send_invoice_email(
                    invoice,
                    cc_emails=cc_emails if cc_emails else None,
                    custom_message=custom_message if custom_message else None
                )

            # Enviar notificacion al cliente en el portal
            self._send_client_notification(invoice)

        # Retornar mensaje de exito con el estado actual
        response_data = {
            'message': 'Factura enviada',
            'status': invoice.status
        }

        if email_result:
            response_data['email'] = email_result

        return Response(response_data)

    def _send_client_notification(self, invoice):
        """
        Envia una notificacion al cliente sobre la nueva factura.

        Hace una llamada HTTP al portal service para crear un mensaje
        del sistema notificando al cliente sobre la factura.

        Args:
            invoice: Instancia de Invoice que se envio
        """
        try:
            # URL del endpoint de notificaciones del sistema
            url = f"{settings.PORTAL_SERVICE_URL}/api/portal/internal/notification/"

            # Formatear el monto total
            total_formatted = f"${int(invoice.total_amount):,}".replace(',', '.')

            # Datos del mensaje de notificacion
            notification_data = {
                'sender_id': str(uuid.uuid4()),  # ID del sistema
                'sender_name': 'Sistema de Facturación',
                'sender_role': 'system',
                'recipient_id': str(invoice.client_id),
                'recipient_name': invoice.client_name,
                'case_id': str(invoice.case_id) if invoice.case_id else None,
                'case_number': invoice.case_number or '',
                'subject': f'Nueva factura #{invoice.invoice_number}',
                'content': (
                    f'Estimado/a {invoice.client_name},\n\n'
                    f'Se ha generado una nueva factura a su nombre.\n\n'
                    f'Número de factura: {invoice.invoice_number}\n'
                    f'Monto total: {total_formatted} COP\n'
                    f'Fecha de vencimiento: {invoice.due_date.strftime("%d/%m/%Y")}\n\n'
                    f'Puede consultar el detalle de esta factura en la sección '
                    f'"Mis Facturas" del portal de clientes.\n\n'
                    f'Gracias por su confianza.'
                ),
            }

            # Headers con token de servicio interno
            headers = {
                'Content-Type': 'application/json',
                'X-Service-Token': settings.INTERNAL_SERVICE_TOKEN,
            }

            # Enviar la notificacion
            response = requests.post(url, json=notification_data, headers=headers, timeout=10)

            if response.status_code != 201:
                logger.warning(
                    f"Error al enviar notificacion de factura {invoice.invoice_number}: "
                    f"Status {response.status_code}"
                )

        except Exception as e:
            # Log del error pero no fallar el envio de factura
            logger.error(f"Error al enviar notificacion de factura: {str(e)}")


class BillingSummaryView(APIView):
    """
    Vista para obtener un resumen estadistico de facturacion.

    Proporciona metricas agregadas como:
    - Total facturado
    - Total cobrado
    - Saldo pendiente total
    - Monto vencido

    Permite filtrar por cliente usando el parametro client_id.
    """

    def get(self, request):
        """
        Obtiene el resumen de facturacion.

        Args:
            request: Objeto de solicitud HTTP con parametros de filtro opcionales

        Returns:
            Response: Objeto JSON con las metricas de facturacion
        """
        # Comenzar con todas las facturas
        queryset = Invoice.objects.all()

        # Obtener parametro de filtro por cliente
        client_id = request.query_params.get('client_id')

        # Si se especifica client_id, filtrar por ese cliente
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        # Calcular totales generales usando agregacion en base de datos
        totals = queryset.aggregate(
            total_invoiced=Sum('total_amount'),  # Suma de todos los montos totales
            total_paid=Sum('amount_paid'),       # Suma de todos los montos pagados
        )

        # Calcular saldo pendiente total (excluyendo facturas pagadas y canceladas)
        outstanding = queryset.exclude(
            status__in=['paid', 'cancelled']
        ).aggregate(
            total=Sum('balance_due')  # Suma de saldos pendientes
        )

        # Calcular monto vencido (facturas con fecha de vencimiento pasada)
        overdue = queryset.filter(
            status__in=['pending', 'sent', 'partial'],  # Estados activos
            due_date__lt=date.today()                    # Fecha vencida
        ).aggregate(total=Sum('balance_due'))

        # Agrupar conteo de facturas por estado
        by_status = dict(
            queryset.values('status').annotate(
                count=Count('id'),          # Contar facturas por estado
                amount=Sum('total_amount')  # Sumar montos por estado
            ).values_list('status', 'count')
        )

        # Construir diccionario de resumen
        # Usar 0 como valor predeterminado si no hay datos
        summary = {
            'total_invoiced': totals['total_invoiced'] or 0,
            'total_paid': totals['total_paid'] or 0,
            'total_outstanding': outstanding['total'] or 0,
            'overdue_amount': overdue['total'] or 0,
            'by_status': by_status,
        }

        # Serializar y retornar el resumen
        return Response(BillingSummarySerializer(summary).data)


class ClientRateAgreementListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear acuerdos de tarifas con clientes.

    Funcionalidades:
    - GET: Lista todos los acuerdos de tarifas con filtros
    - POST: Crea un nuevo acuerdo de tarifa

    Filtros disponibles:
    - client_id: Por cliente especifico
    - case_id: Por caso especifico
    - rate_type: Por tipo de tarifa
    - is_active: Por estado activo/inactivo
    """

    # Queryset base con todos los acuerdos
    queryset = ClientRateAgreement.objects.all()

    # Serializador para acuerdos de tarifas
    serializer_class = ClientRateAgreementSerializer

    # Backend de filtrado habilitado
    filter_backends = [DjangoFilterBackend]

    # Campos disponibles para filtrado
    filterset_fields = ['client_id', 'case_id', 'rate_type', 'is_active']


class ClientRateAgreementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un acuerdo de tarifa individual.

    Funcionalidades:
    - GET: Ver detalles del acuerdo
    - PUT/PATCH: Actualizar el acuerdo
    - DELETE: Eliminar el acuerdo
    """

    # Queryset base con todos los acuerdos
    queryset = ClientRateAgreement.objects.all()

    # Serializador para acuerdos de tarifas
    serializer_class = ClientRateAgreementSerializer

    # Campo usado para buscar el acuerdo en la URL
    lookup_field = 'id'


class ClientInvoicesView(generics.ListAPIView):
    """
    Vista para listar todas las facturas de un cliente especifico.

    Esta vista es util para ver el historial de facturacion
    de un cliente particular. Solo muestra facturas enviadas,
    no borradores, ya que estos son internos del despacho.

    El cliente se identifica por client_id en la URL.
    """

    # Serializador de lista para facturas
    serializer_class = InvoiceListSerializer

    def get_queryset(self):
        """
        Filtra las facturas para el cliente especificado.

        Excluye facturas en estado 'draft' (borrador) ya que
        los clientes solo deben ver facturas que han sido enviadas.

        Returns:
            QuerySet: Facturas del cliente (excluyendo borradores)
        """
        # Filtrar facturas por client_id y excluir borradores
        return Invoice.objects.filter(
            client_id=self.kwargs['client_id']
        ).exclude(status='draft')


class CaseInvoicesView(generics.ListAPIView):
    """
    Vista para listar todas las facturas de un caso especifico.

    Esta vista es util para ver el historial de facturacion
    asociado a un caso legal particular.

    El caso se identifica por case_id en la URL.
    """

    # Serializador de lista para facturas
    serializer_class = InvoiceListSerializer

    def get_queryset(self):
        """
        Filtra las facturas para el caso especificado.

        Returns:
            QuerySet: Facturas del caso especificado
        """
        # Filtrar facturas por el case_id de la URL
        return Invoice.objects.filter(case_id=self.kwargs['case_id'])


# ============================================================================
# VISTAS DE PASARELAS DE PAGO
# ============================================================================

class StripePaymentView(APIView):
    """
    Vista para procesar pagos a traves de Stripe.

    Esta vista maneja la creacion de intentos de pago (PaymentIntents)
    en Stripe y el seguimiento de las transacciones.

    Soporta dos flujos:
    1. Stripe Elements (frontend): Solo envia amount, recibe client_secret
    2. Pago directo: Envia payment_method_id para confirmar inmediatamente

    Metodos:
    - POST: Crea un nuevo intento de pago en Stripe
    """

    def post(self, request, invoice_id):
        """
        Crea un intento de pago en Stripe para una factura.

        Args:
            request: Objeto de solicitud HTTP con los datos del pago
            invoice_id: UUID de la factura a pagar

        Cuerpo de la solicitud:
            - amount: Monto a pagar (opcional, usa balance_due por defecto)
            - payment_method_id: ID del metodo de pago de Stripe (opcional)
              Si se proporciona, confirma el pago inmediatamente.
              Si no, retorna client_secret para confirmar desde el frontend.

        Returns:
            Response: Resultado del intento de pago con client_secret
        """
        # Importaciones necesarias para Stripe
        import os
        from .models import PaymentGatewayTransaction

        try:
            # Intentar importar la libreria de Stripe
            import stripe

            # Configurar la clave secreta de Stripe desde variables de entorno
            stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

            # Verificar que la clave este configurada
            if not stripe.api_key:
                return Response(
                    {'error': 'Stripe no esta configurado. Contacte al administrador.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

        except ImportError:
            return Response(
                {'error': 'Libreria de Stripe no instalada'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Obtener la factura
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Factura no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que la factura no este pagada
        if invoice.status == 'paid':
            return Response(
                {'error': 'Esta factura ya esta pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener datos del request
        payment_method_id = request.data.get('payment_method_id')
        amount = request.data.get('amount', invoice.balance_due)

        try:
            # Flujo 1: Stripe Elements (sin payment_method_id)
            # Crea PaymentIntent sin confirmar, retorna client_secret
            if not payment_method_id:
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(float(amount) * 100),  # En centavos
                    currency=invoice.currency.lower(),
                    metadata={
                        'invoice_id': str(invoice.id),
                        'invoice_number': invoice.invoice_number,
                        'client_id': str(invoice.client_id),
                    },
                    automatic_payment_methods={
                        'enabled': True,
                    }
                )

                # Crear registro de transaccion en la base de datos
                transaction = PaymentGatewayTransaction.objects.create(
                    invoice=invoice,
                    gateway='stripe',
                    gateway_transaction_id=payment_intent.id,
                    amount=amount,
                    currency=invoice.currency,
                    status='pending',
                    payment_method_type='card',
                    gateway_response={
                        'payment_intent_id': payment_intent.id,
                        'status': payment_intent.status,
                    },
                    client_ip=self._get_client_ip(request),
                )

                # Retornar el client_secret para que el frontend confirme el pago
                return Response({
                    'client_secret': payment_intent.client_secret,
                    'transaction_id': str(transaction.id),
                    'payment_intent_id': payment_intent.id,
                    'amount': float(amount),
                    'currency': invoice.currency,
                }, status=status.HTTP_200_OK)

            # Flujo 2: Pago directo (con payment_method_id)
            # Crear el PaymentIntent y confirmar inmediatamente
            payment_intent = stripe.PaymentIntent.create(
                amount=int(float(amount) * 100),
                currency=invoice.currency.lower(),
                payment_method=payment_method_id,
                confirm=True,  # Confirmar inmediatamente
                metadata={
                    'invoice_id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                    'client_id': str(invoice.client_id),
                },
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                }
            )

            # Crear registro de transaccion en la base de datos
            transaction = PaymentGatewayTransaction.objects.create(
                invoice=invoice,
                gateway='stripe',
                gateway_transaction_id=payment_intent.id,
                amount=amount,
                currency=invoice.currency,
                status='completed' if payment_intent.status == 'succeeded' else 'processing',
                payment_method_type='card',
                gateway_response={
                    'payment_intent_id': payment_intent.id,
                    'status': payment_intent.status,
                    'client_secret': payment_intent.client_secret,
                },
                client_ip=self._get_client_ip(request),
            )

            # Si el pago fue exitoso, crear el registro de pago
            if payment_intent.status == 'succeeded':
                transaction.complete_payment()

                return Response({
                    'success': True,
                    'message': 'Pago procesado exitosamente',
                    'transaction_id': str(transaction.id),
                    'payment_intent_id': payment_intent.id,
                    'status': 'completed'
                }, status=status.HTTP_200_OK)

            # Si requiere accion adicional
            elif payment_intent.status == 'requires_action':
                return Response({
                    'success': False,
                    'requires_action': True,
                    'client_secret': payment_intent.client_secret,
                    'transaction_id': str(transaction.id),
                    'message': 'Se requiere autenticacion adicional'
                }, status=status.HTTP_200_OK)

            # Otros estados
            else:
                return Response({
                    'success': False,
                    'transaction_id': str(transaction.id),
                    'status': payment_intent.status,
                    'message': f'Estado del pago: {payment_intent.status}'
                }, status=status.HTTP_200_OK)

        except stripe.error.CardError as e:
            # Error de tarjeta (rechazada, fondos insuficientes, etc.)
            error = e.error
            return Response({
                'error': error.message,
                'code': error.code,
                'decline_code': getattr(error, 'decline_code', None)
            }, status=status.HTTP_400_BAD_REQUEST)

        except stripe.error.StripeError as e:
            # Otros errores de Stripe
            return Response({
                'error': str(e),
                'type': type(e).__name__
            }, status=status.HTTP_400_BAD_REQUEST)

    def _get_client_ip(self, request):
        """
        Obtiene la direccion IP del cliente desde la solicitud.

        Args:
            request: Objeto de solicitud HTTP

        Returns:
            str: Direccion IP del cliente
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class StripeConfirmPaymentView(APIView):
    """
    Vista para confirmar un pago de Stripe despues de que el frontend
    procesa exitosamente el PaymentIntent con Stripe Elements.

    Esta vista se llama desde el frontend cuando stripe.confirmPayment()
    retorna status='succeeded'. Actualiza la transaccion y crea el
    registro de pago en la base de datos.

    Metodos:
    - POST: Confirma el pago y actualiza la factura
    """

    def post(self, request, invoice_id):
        """
        Confirma un pago exitoso de Stripe.

        Args:
            request: Objeto de solicitud HTTP
            invoice_id: UUID de la factura

        Cuerpo de la solicitud:
            - payment_intent_id: ID del PaymentIntent de Stripe

        Returns:
            Response: Confirmacion del pago registrado
        """
        from .models import PaymentGatewayTransaction

        payment_intent_id = request.data.get('payment_intent_id')

        if not payment_intent_id:
            return Response(
                {'error': 'Se requiere payment_intent_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Buscar la transaccion por el payment_intent_id
            transaction = PaymentGatewayTransaction.objects.get(
                gateway='stripe',
                gateway_transaction_id=payment_intent_id,
                invoice_id=invoice_id
            )

            # Si ya esta completada, retornar exito
            if transaction.status == 'completed':
                return Response({
                    'success': True,
                    'message': 'El pago ya fue registrado',
                    'transaction_id': str(transaction.id),
                    'payment_id': str(transaction.payment_id) if transaction.payment_id else None
                }, status=status.HTTP_200_OK)

            # Completar el pago
            payment = transaction.complete_payment()

            return Response({
                'success': True,
                'message': 'Pago registrado exitosamente',
                'transaction_id': str(transaction.id),
                'payment_id': str(payment.id) if payment else None,
                'invoice_status': transaction.invoice.status,
                'balance_due': float(transaction.invoice.balance_due),
                'amount_paid': float(transaction.invoice.amount_paid)
            }, status=status.HTTP_200_OK)

        except PaymentGatewayTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaccion no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PayPalPaymentView(APIView):
    """
    Vista para procesar pagos a traves de PayPal.

    Esta vista maneja la creacion de ordenes de pago en PayPal
    y proporciona la URL de checkout para que el cliente complete el pago.

    Metodos:
    - POST: Crea una nueva orden de pago en PayPal
    """

    def post(self, request, invoice_id):
        """
        Crea una orden de pago en PayPal para una factura.

        Args:
            request: Objeto de solicitud HTTP
            invoice_id: UUID de la factura a pagar

        Cuerpo de la solicitud:
            - amount: Monto a pagar (opcional, usa balance_due por defecto)
            - return_url: URL de retorno despues del pago exitoso
            - cancel_url: URL de retorno si el pago es cancelado

        Returns:
            Response: URL de checkout de PayPal para completar el pago
        """
        # Importaciones necesarias
        import os
        import requests
        from .models import PaymentGatewayTransaction

        # Obtener credenciales de PayPal desde variables de entorno
        client_id = os.environ.get('PAYPAL_CLIENT_ID')
        client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        environment = os.environ.get('PAYPAL_ENVIRONMENT', 'sandbox')

        # Verificar que PayPal este configurado
        if not client_id or not client_secret:
            return Response(
                {'error': 'PayPal no esta configurado. Contacte al administrador.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Determinar URL base segun el ambiente
        base_url = 'https://api-m.sandbox.paypal.com' if environment == 'sandbox' else 'https://api-m.paypal.com'

        # Obtener la factura
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Factura no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que la factura no este pagada
        if invoice.status == 'paid':
            return Response(
                {'error': 'Esta factura ya esta pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener datos del request
        amount = request.data.get('amount', invoice.balance_due)
        return_url = request.data.get('return_url', 'http://localhost:3000/payment/success')
        cancel_url = request.data.get('cancel_url', 'http://localhost:3000/payment/cancel')

        try:
            # Paso 1: Obtener token de acceso de PayPal
            auth_response = requests.post(
                f'{base_url}/v1/oauth2/token',
                auth=(client_id, client_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data={'grant_type': 'client_credentials'}
            )
            auth_response.raise_for_status()
            access_token = auth_response.json()['access_token']

            # Paso 2: Crear la orden de pago
            order_payload = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'reference_id': str(invoice.id),
                    'description': f'Pago factura {invoice.invoice_number}',
                    'amount': {
                        'currency_code': invoice.currency,
                        'value': str(amount)
                    },
                    'custom_id': invoice.invoice_number
                }],
                'application_context': {
                    'return_url': return_url,
                    'cancel_url': cancel_url,
                    'brand_name': 'LegalFlow',
                    'landing_page': 'LOGIN',
                    'user_action': 'PAY_NOW'
                }
            }

            order_response = requests.post(
                f'{base_url}/v2/checkout/orders',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {access_token}'
                },
                json=order_payload
            )
            order_response.raise_for_status()
            order_data = order_response.json()

            # Obtener URL de aprobacion
            approve_url = None
            for link in order_data.get('links', []):
                if link['rel'] == 'approve':
                    approve_url = link['href']
                    break

            # Crear registro de transaccion
            transaction = PaymentGatewayTransaction.objects.create(
                invoice=invoice,
                gateway='paypal',
                gateway_transaction_id=order_data['id'],
                amount=amount,
                currency=invoice.currency,
                status='pending',
                checkout_url=approve_url,
                gateway_response=order_data,
                client_ip=self._get_client_ip(request),
            )

            return Response({
                'success': True,
                'order_id': order_data['id'],
                'transaction_id': str(transaction.id),
                'checkout_url': approve_url,
                'message': 'Orden de PayPal creada. Redirigir al usuario a checkout_url'
            }, status=status.HTTP_201_CREATED)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': f'Error al comunicarse con PayPal: {str(e)}'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    def _get_client_ip(self, request):
        """
        Obtiene la direccion IP del cliente desde la solicitud.

        Args:
            request: Objeto de solicitud HTTP

        Returns:
            str: Direccion IP del cliente
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class PayPalCaptureView(APIView):
    """
    Vista para capturar (completar) un pago de PayPal.

    Esta vista se llama despues de que el usuario aprueba el pago
    en PayPal y es redirigido de vuelta a la aplicacion.

    Metodos:
    - POST: Captura el pago aprobado por el usuario
    """

    def post(self, request, transaction_id):
        """
        Captura un pago de PayPal aprobado por el usuario.

        Args:
            request: Objeto de solicitud HTTP
            transaction_id: UUID de la transaccion local

        Returns:
            Response: Resultado de la captura del pago
        """
        # Importaciones necesarias
        import os
        import requests
        from .models import PaymentGatewayTransaction

        # Obtener credenciales de PayPal
        client_id = os.environ.get('PAYPAL_CLIENT_ID')
        client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        environment = os.environ.get('PAYPAL_ENVIRONMENT', 'sandbox')

        if not client_id or not client_secret:
            return Response(
                {'error': 'PayPal no esta configurado'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        base_url = 'https://api-m.sandbox.paypal.com' if environment == 'sandbox' else 'https://api-m.paypal.com'

        # Obtener la transaccion
        try:
            transaction = PaymentGatewayTransaction.objects.get(id=transaction_id)
        except PaymentGatewayTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaccion no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar que sea una transaccion de PayPal pendiente
        if transaction.gateway != 'paypal' or transaction.status != 'pending':
            return Response(
                {'error': 'Transaccion invalida o ya procesada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Obtener token de acceso
            auth_response = requests.post(
                f'{base_url}/v1/oauth2/token',
                auth=(client_id, client_secret),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data={'grant_type': 'client_credentials'}
            )
            auth_response.raise_for_status()
            access_token = auth_response.json()['access_token']

            # Capturar el pago
            capture_response = requests.post(
                f'{base_url}/v2/checkout/orders/{transaction.gateway_transaction_id}/capture',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {access_token}'
                }
            )
            capture_response.raise_for_status()
            capture_data = capture_response.json()

            # Actualizar la transaccion
            transaction.gateway_response = capture_data
            transaction.status = 'completed' if capture_data['status'] == 'COMPLETED' else 'failed'

            # Extraer informacion del pagador si esta disponible
            payer = capture_data.get('payer', {})
            transaction.payer_email = payer.get('email_address', '')
            transaction.payer_name = payer.get('name', {}).get('given_name', '')

            transaction.save()

            # Si el pago fue exitoso, crear el registro de pago
            if transaction.status == 'completed':
                transaction.complete_payment()

                return Response({
                    'success': True,
                    'message': 'Pago capturado exitosamente',
                    'transaction_id': str(transaction.id),
                    'paypal_order_id': capture_data['id'],
                    'status': 'completed'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'El pago no pudo ser completado',
                    'status': capture_data['status']
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            transaction.status = 'failed'
            transaction.error_message = str(e)
            transaction.save()

            return Response({
                'error': f'Error al capturar pago de PayPal: {str(e)}'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class PaymentGatewayWebhookView(APIView):
    """
    Vista para recibir webhooks de las pasarelas de pago.

    Esta vista maneja las notificaciones automaticas enviadas por
    Stripe y PayPal cuando hay eventos importantes (pagos exitosos,
    fallidos, reembolsos, etc.).

    Metodos:
    - POST: Procesa el webhook recibido
    """

    def post(self, request, gateway):
        """
        Procesa un webhook de una pasarela de pago.

        Args:
            request: Objeto de solicitud HTTP con el payload del webhook
            gateway: Nombre de la pasarela (stripe o paypal)

        Returns:
            Response: Confirmacion de recepcion del webhook
        """
        # Importaciones necesarias
        import os
        from .models import PaymentGatewayTransaction

        if gateway == 'stripe':
            return self._process_stripe_webhook(request)
        elif gateway == 'paypal':
            return self._process_paypal_webhook(request)
        else:
            return Response(
                {'error': 'Pasarela no soportada'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _process_stripe_webhook(self, request):
        """
        Procesa un webhook de Stripe.

        Verifica la firma del webhook y procesa eventos como:
        - payment_intent.succeeded: Pago exitoso
        - payment_intent.payment_failed: Pago fallido
        - charge.refunded: Reembolso procesado

        Args:
            request: Objeto de solicitud HTTP

        Returns:
            Response: Confirmacion de procesamiento
        """
        import os
        from .models import PaymentGatewayTransaction

        try:
            import stripe

            # Configurar Stripe
            stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
            webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

            # Obtener el payload y la firma
            payload = request.body
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

            # Verificar la firma del webhook
            if webhook_secret:
                try:
                    event = stripe.Webhook.construct_event(
                        payload, sig_header, webhook_secret
                    )
                except stripe.error.SignatureVerificationError:
                    return Response(
                        {'error': 'Firma invalida'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Si no hay webhook secret, parsear directamente (solo para desarrollo)
                import json
                event = json.loads(payload)

            # Procesar el evento segun su tipo
            event_type = event.get('type', event.get('data', {}).get('type'))
            data_object = event.get('data', {}).get('object', {})

            if event_type == 'payment_intent.succeeded':
                # Pago exitoso
                payment_intent_id = data_object.get('id')
                try:
                    transaction = PaymentGatewayTransaction.objects.get(
                        gateway='stripe',
                        gateway_transaction_id=payment_intent_id
                    )
                    if transaction.status != 'completed':
                        transaction.status = 'completed'
                        transaction.gateway_response = data_object
                        transaction.save()
                        transaction.complete_payment()
                except PaymentGatewayTransaction.DoesNotExist:
                    pass  # Transaccion no encontrada

            elif event_type == 'payment_intent.payment_failed':
                # Pago fallido
                payment_intent_id = data_object.get('id')
                try:
                    transaction = PaymentGatewayTransaction.objects.get(
                        gateway='stripe',
                        gateway_transaction_id=payment_intent_id
                    )
                    transaction.status = 'failed'
                    transaction.error_message = data_object.get('last_payment_error', {}).get('message', '')
                    transaction.error_code = data_object.get('last_payment_error', {}).get('code', '')
                    transaction.gateway_response = data_object
                    transaction.save()
                except PaymentGatewayTransaction.DoesNotExist:
                    pass

            elif event_type == 'charge.refunded':
                # Reembolso procesado
                payment_intent_id = data_object.get('payment_intent')
                refund_amount = data_object.get('amount_refunded', 0) / 100  # Convertir de centavos
                refunds_data = data_object.get('refunds', {}).get('data', [])
                refund_reason = refunds_data[0].get('reason', '') if refunds_data else ''

                if payment_intent_id:
                    try:
                        transaction = PaymentGatewayTransaction.objects.get(
                            gateway='stripe',
                            gateway_transaction_id=payment_intent_id
                        )
                        # Procesar el reembolso
                        transaction.process_refund(
                            refund_amount=refund_amount,
                            refund_reason=refund_reason or 'Reembolso desde Stripe'
                        )
                        # Actualizar respuesta de la pasarela
                        transaction.gateway_response = data_object
                        transaction.save()
                    except PaymentGatewayTransaction.DoesNotExist:
                        pass

            elif event_type == 'payment_intent.canceled':
                # Pago cancelado
                payment_intent_id = data_object.get('id')
                try:
                    transaction = PaymentGatewayTransaction.objects.get(
                        gateway='stripe',
                        gateway_transaction_id=payment_intent_id
                    )
                    transaction.status = 'cancelled'
                    transaction.gateway_response = data_object
                    transaction.save()
                except PaymentGatewayTransaction.DoesNotExist:
                    pass

            return Response({'received': True}, status=status.HTTP_200_OK)

        except ImportError:
            return Response(
                {'error': 'Stripe no instalado'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    def _process_paypal_webhook(self, request):
        """
        Procesa un webhook de PayPal.

        Procesa eventos como:
        - PAYMENT.CAPTURE.COMPLETED: Pago capturado exitosamente
        - PAYMENT.CAPTURE.DENIED: Pago denegado
        - PAYMENT.CAPTURE.REFUNDED: Reembolso procesado

        Args:
            request: Objeto de solicitud HTTP

        Returns:
            Response: Confirmacion de procesamiento
        """
        import json
        from .models import PaymentGatewayTransaction

        try:
            # Parsear el payload
            payload = json.loads(request.body)

            event_type = payload.get('event_type')
            resource = payload.get('resource', {})

            if event_type == 'PAYMENT.CAPTURE.COMPLETED':
                # Buscar la transaccion por el ID de la orden
                order_id = resource.get('supplementary_data', {}).get('related_ids', {}).get('order_id')
                if order_id:
                    try:
                        transaction = PaymentGatewayTransaction.objects.get(
                            gateway='paypal',
                            gateway_transaction_id=order_id
                        )
                        if transaction.status != 'completed':
                            transaction.status = 'completed'
                            transaction.gateway_response = payload
                            transaction.save()
                            transaction.complete_payment()
                    except PaymentGatewayTransaction.DoesNotExist:
                        pass

            elif event_type == 'PAYMENT.CAPTURE.DENIED':
                # Pago denegado
                order_id = resource.get('supplementary_data', {}).get('related_ids', {}).get('order_id')
                if order_id:
                    try:
                        transaction = PaymentGatewayTransaction.objects.get(
                            gateway='paypal',
                            gateway_transaction_id=order_id
                        )
                        transaction.status = 'failed'
                        transaction.error_message = 'Pago denegado por PayPal'
                        transaction.gateway_response = payload
                        transaction.save()
                    except PaymentGatewayTransaction.DoesNotExist:
                        pass

            return Response({'received': True}, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response(
                {'error': 'Payload invalido'},
                status=status.HTTP_400_BAD_REQUEST
            )


class PaymentGatewayTransactionListView(generics.ListAPIView):
    """
    Vista para listar las transacciones de pasarelas de pago de una factura.

    Muestra el historial de intentos de pago realizados a traves
    de pasarelas electronicas para una factura especifica.
    """

    def get_queryset(self):
        """
        Filtra las transacciones para la factura especificada.

        Returns:
            QuerySet: Transacciones de la factura
        """
        from .models import PaymentGatewayTransaction
        return PaymentGatewayTransaction.objects.filter(
            invoice_id=self.kwargs['invoice_id']
        )

    def get_serializer_class(self):
        """
        Retorna un serializador simple para las transacciones.
        """
        from rest_framework import serializers
        from .models import PaymentGatewayTransaction

        class TransactionSerializer(serializers.ModelSerializer):
            class Meta:
                model = PaymentGatewayTransaction
                fields = [
                    'id', 'gateway', 'gateway_transaction_id', 'amount',
                    'currency', 'status', 'payment_method_type',
                    'created_at', 'updated_at', 'error_message'
                ]

        return TransactionSerializer


# ============================================================================
# VISTA DE EXPORTACION PDF
# ============================================================================

class InvoicePDFView(APIView):
    """
    Vista para generar y descargar una factura en formato PDF.

    Esta vista genera un documento PDF profesional con toda la informacion
    de la factura, incluyendo items, totales, pagos y notas.

    Metodos:
    - GET: Genera y descarga el PDF de la factura
    """

    def get(self, request, id):
        """
        Genera y descarga el PDF de una factura.

        Args:
            request: Objeto de solicitud HTTP
            id: UUID de la factura

        Returns:
            HttpResponse: Respuesta HTTP con el archivo PDF
        """
        from .pdf_generator import generate_invoice_pdf_response

        try:
            # Obtener la factura
            invoice = Invoice.objects.get(id=id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Factura no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generar y retornar el PDF
        return generate_invoice_pdf_response(invoice)


class InvoicePDFPreviewView(APIView):
    """
    Vista para previsualizar una factura en PDF (inline en el navegador).

    A diferencia de InvoicePDFView, esta vista muestra el PDF en el navegador
    en lugar de forzar la descarga.

    Metodos:
    - GET: Genera y muestra el PDF de la factura en el navegador
    """

    def get(self, request, id):
        """
        Genera y muestra el PDF de una factura en el navegador.

        Args:
            request: Objeto de solicitud HTTP
            id: UUID de la factura

        Returns:
            HttpResponse: Respuesta HTTP con el archivo PDF para visualizacion
        """
        from django.http import HttpResponse
        from .pdf_generator import generate_invoice_pdf

        try:
            # Obtener la factura
            invoice = Invoice.objects.get(id=id)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Factura no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generar el PDF
        pdf_buffer = generate_invoice_pdf(invoice)

        # Crear respuesta HTTP para visualizacion inline
        response = HttpResponse(
            pdf_buffer.getvalue(),
            content_type='application/pdf'
        )

        # Usar inline en lugar de attachment para mostrar en navegador
        filename = f"Factura_{invoice.invoice_number}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        return response
