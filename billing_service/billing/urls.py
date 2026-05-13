"""
Modulo de URLs del Servicio de Facturacion (Billing Service)

Este archivo define las rutas URL que mapean las solicitudes HTTP a las vistas
correspondientes del modulo de facturacion. Utiliza el sistema de enrutamiento
de Django para definir los endpoints de la API REST.

Endpoints disponibles:

FACTURAS (Invoices):
- GET/POST   /invoices/                          - Listar/Crear facturas
- GET        /invoices/summary/                  - Resumen de facturacion
- GET/PUT/DELETE /invoices/<id>/                 - Detalle/Actualizar/Eliminar factura
- POST       /invoices/<id>/send/                - Enviar factura al cliente

ITEMS DE FACTURA (Invoice Items):
- GET/POST   /invoices/<id>/items/               - Listar/Crear items
- GET/PUT/DELETE /invoices/<id>/items/<item_id>/ - Detalle/Actualizar/Eliminar item

PAGOS (Payments):
- GET/POST   /invoices/<id>/payments/            - Listar/Registrar pagos

ACUERDOS DE TARIFAS (Rate Agreements):
- GET/POST   /rate-agreements/                   - Listar/Crear acuerdos
- GET/PUT/DELETE /rate-agreements/<id>/          - Detalle/Actualizar/Eliminar acuerdo

CONSULTAS POR CLIENTE Y CASO:
- GET        /clients/<client_id>/invoices/      - Facturas de un cliente
- GET        /cases/<case_id>/invoices/          - Facturas de un caso

Autor: Equipo de Desarrollo LegalFlow
Fecha de creacion: 2024
"""

# Importacion de la funcion path para definir rutas URL
# path() permite crear patrones de URL con parametros tipados
from django.urls import path

# Importacion del modulo de vistas de este paquete
# Contiene todas las clases de vista que manejan las solicitudes HTTP
from . import views

# Lista de patrones URL del modulo de facturacion
# Cada entrada define una ruta, la vista que la maneja y un nombre unico
urlpatterns = [

    # ========================================================================
    # ENDPOINTS DE FACTURAS (INVOICES)
    # ========================================================================

    # Endpoint para listar todas las facturas y crear nuevas
    # GET: Retorna lista paginada de facturas con filtros
    # POST: Crea una nueva factura
    # Ejemplo: GET /api/billing/invoices/?status=pending
    path(
        'invoices/',
        views.InvoiceListCreateView.as_view(),
        name='invoice_list_create'
    ),

    # Endpoint para obtener el resumen estadistico de facturacion
    # GET: Retorna totales facturados, cobrados, pendientes y vencidos
    # Ejemplo: GET /api/billing/invoices/summary/?client_id=uuid
    # NOTA: Esta ruta debe ir ANTES de invoices/<uuid:id>/ para evitar conflictos
    path(
        'invoices/summary/',
        views.BillingSummaryView.as_view(),
        name='billing_summary'
    ),

    # Endpoint para ver, actualizar o eliminar una factura individual
    # GET: Retorna todos los detalles de la factura incluyendo items y pagos
    # PUT/PATCH: Actualiza los datos de la factura
    # DELETE: Elimina la factura (solo si no esta pagada)
    # Ejemplo: GET /api/billing/invoices/550e8400-e29b-41d4-a716-446655440000/
    path(
        'invoices/<uuid:id>/',
        views.InvoiceDetailView.as_view(),
        name='invoice_detail'
    ),

    # Endpoint para enviar una factura al cliente
    # POST: Cambia el estado de la factura de 'draft' a 'sent'
    # Ejemplo: POST /api/billing/invoices/550e8400-e29b-41d4-a716-446655440000/send/
    path(
        'invoices/<uuid:id>/send/',
        views.SendInvoiceView.as_view(),
        name='send_invoice'
    ),

    # Endpoint para descargar una factura en formato PDF
    # GET: Genera y descarga el PDF de la factura
    # Ejemplo: GET /api/billing/invoices/550e8400-e29b-41d4-a716-446655440000/pdf/
    path(
        'invoices/<uuid:id>/pdf/',
        views.InvoicePDFView.as_view(),
        name='invoice_pdf'
    ),

    # Endpoint para previsualizar una factura en formato PDF (inline)
    # GET: Muestra el PDF de la factura en el navegador
    # Ejemplo: GET /api/billing/invoices/550e8400-e29b-41d4-a716-446655440000/pdf/preview/
    path(
        'invoices/<uuid:id>/pdf/preview/',
        views.InvoicePDFPreviewView.as_view(),
        name='invoice_pdf_preview'
    ),

    # ========================================================================
    # ENDPOINTS DE ITEMS DE FACTURA (INVOICE ITEMS)
    # ========================================================================

    # Endpoint para listar y crear items de una factura especifica
    # GET: Lista todos los items de la factura
    # POST: Agrega un nuevo item a la factura
    # Ejemplo: POST /api/billing/invoices/uuid/items/
    path(
        'invoices/<uuid:invoice_id>/items/',
        views.InvoiceItemListCreateView.as_view(),
        name='invoice_items'
    ),

    # Endpoint para ver, actualizar o eliminar un item individual
    # GET: Ver detalles del item
    # PUT/PATCH: Actualizar el item
    # DELETE: Eliminar el item (recalcula totales de factura)
    # Ejemplo: DELETE /api/billing/invoices/uuid/items/item-uuid/
    path(
        'invoices/<uuid:invoice_id>/items/<uuid:id>/',
        views.InvoiceItemDetailView.as_view(),
        name='invoice_item_detail'
    ),

    # ========================================================================
    # ENDPOINTS DE PAGOS (PAYMENTS)
    # ========================================================================

    # Endpoint para listar y registrar pagos de una factura
    # GET: Lista todos los pagos realizados a la factura
    # POST: Registra un nuevo pago (actualiza automaticamente estado de factura)
    # Ejemplo: POST /api/billing/invoices/uuid/payments/
    path(
        'invoices/<uuid:invoice_id>/payments/',
        views.PaymentListCreateView.as_view(),
        name='invoice_payments'
    ),

    # ========================================================================
    # ENDPOINTS DE ACUERDOS DE TARIFAS (RATE AGREEMENTS)
    # ========================================================================

    # Endpoint para listar y crear acuerdos de tarifas con clientes
    # GET: Lista todos los acuerdos con filtros por cliente, caso, tipo
    # POST: Crea un nuevo acuerdo de tarifa
    # Ejemplo: GET /api/billing/rate-agreements/?client_id=uuid&is_active=true
    path(
        'rate-agreements/',
        views.ClientRateAgreementListCreateView.as_view(),
        name='rate_agreements'
    ),

    # Endpoint para ver, actualizar o eliminar un acuerdo de tarifa
    # GET: Ver detalles del acuerdo
    # PUT/PATCH: Actualizar el acuerdo
    # DELETE: Eliminar el acuerdo
    # Ejemplo: PUT /api/billing/rate-agreements/uuid/
    path(
        'rate-agreements/<uuid:id>/',
        views.ClientRateAgreementDetailView.as_view(),
        name='rate_agreement_detail'
    ),

    # ========================================================================
    # ENDPOINTS DE CONSULTAS POR CLIENTE Y CASO
    # ========================================================================

    # Endpoint para obtener todas las facturas de un cliente especifico
    # GET: Lista facturas filtradas por client_id
    # Util para ver el historial de facturacion de un cliente
    # Ejemplo: GET /api/billing/clients/uuid/invoices/
    path(
        'clients/<uuid:client_id>/invoices/',
        views.ClientInvoicesView.as_view(),
        name='client_invoices'
    ),

    # Endpoint para obtener todas las facturas de un caso especifico
    # GET: Lista facturas filtradas por case_id
    # Util para ver la facturacion asociada a un caso legal
    # Ejemplo: GET /api/billing/cases/uuid/invoices/
    path(
        'cases/<uuid:case_id>/invoices/',
        views.CaseInvoicesView.as_view(),
        name='case_invoices'
    ),

    # ========================================================================
    # ENDPOINTS DE PASARELAS DE PAGO (PAYMENT GATEWAYS)
    # ========================================================================

    # Endpoint para procesar pago con Stripe
    # POST: Crea un PaymentIntent en Stripe y procesa el pago
    # Requiere: payment_method_id en el body
    # Ejemplo: POST /api/billing/invoices/uuid/pay/stripe/
    path(
        'invoices/<uuid:invoice_id>/pay/stripe/',
        views.StripePaymentView.as_view(),
        name='stripe_payment'
    ),

    # Endpoint para confirmar pago de Stripe desde el frontend
    # POST: Registra el pago exitoso despues de stripe.confirmPayment()
    # Requiere: payment_intent_id en el body
    # Ejemplo: POST /api/billing/invoices/uuid/pay/stripe/confirm/
    path(
        'invoices/<uuid:invoice_id>/pay/stripe/confirm/',
        views.StripeConfirmPaymentView.as_view(),
        name='stripe_confirm_payment'
    ),

    # Endpoint para crear orden de pago en PayPal
    # POST: Crea una orden de pago en PayPal
    # Retorna: checkout_url para redirigir al usuario
    # Ejemplo: POST /api/billing/invoices/uuid/pay/paypal/
    path(
        'invoices/<uuid:invoice_id>/pay/paypal/',
        views.PayPalPaymentView.as_view(),
        name='paypal_payment'
    ),

    # Endpoint para capturar pago de PayPal despues de aprobacion
    # POST: Captura el pago aprobado por el usuario en PayPal
    # Ejemplo: POST /api/billing/payments/paypal/uuid/capture/
    path(
        'payments/paypal/<uuid:transaction_id>/capture/',
        views.PayPalCaptureView.as_view(),
        name='paypal_capture'
    ),

    # Endpoint para recibir webhooks de pasarelas de pago
    # POST: Procesa notificaciones automaticas de Stripe/PayPal
    # Ejemplo: POST /api/billing/webhooks/stripe/
    path(
        'webhooks/<str:gateway>/',
        views.PaymentGatewayWebhookView.as_view(),
        name='payment_webhook'
    ),

    # Endpoint para listar transacciones de pasarela de una factura
    # GET: Lista todos los intentos de pago via pasarela
    # Ejemplo: GET /api/billing/invoices/uuid/gateway-transactions/
    path(
        'invoices/<uuid:invoice_id>/gateway-transactions/',
        views.PaymentGatewayTransactionListView.as_view(),
        name='gateway_transactions'
    ),
]
