"""
Modulo de Modelos del Servicio de Facturacion (Billing Service)

Este archivo define los modelos de base de datos para el sistema de facturacion
del aplicativo LegalFlow. Incluye los siguientes modelos principales:

- Invoice: Representa una factura emitida a un cliente
- InvoiceItem: Representa los items o conceptos dentro de una factura
- Payment: Representa los pagos realizados a una factura
- ClientRateAgreement: Representa los acuerdos de tarifas con clientes

Estos modelos utilizan UUID como identificadores primarios para mayor seguridad
y compatibilidad con sistemas distribuidos.

Autor: Equipo de Desarrollo LegalFlow
Fecha de creacion: 2024
"""

# Importacion del modulo uuid para generar identificadores unicos universales
import uuid

# Importacion del modulo models de Django para definir los modelos de base de datos
from django.db import models

# Importacion de la clase Decimal para manejo preciso de numeros decimales
# Esto es importante para calculos financieros que requieren precision
from decimal import Decimal


class Invoice(models.Model):
    """
    Modelo que representa una factura en el sistema de facturacion.

    Una factura es un documento comercial que detalla los servicios prestados
    a un cliente, incluyendo montos, impuestos, descuentos y condiciones de pago.

    Atributos:
        id: Identificador unico de la factura (UUID)
        invoice_number: Numero de factura legible (ej: INV-2024-00001)
        case_id: ID del caso legal asociado (opcional)
        client_id: ID del cliente al que se factura
        status: Estado actual de la factura (borrador, pendiente, pagada, etc.)
        subtotal: Suma de todos los items antes de impuestos
        tax_rate: Porcentaje de impuesto aplicable
        total_amount: Monto total a pagar incluyendo impuestos
        balance_due: Saldo pendiente por pagar
    """

    # Definicion de las opciones de estado para una factura
    # Cada tupla contiene (valor_interno, etiqueta_legible)
    STATUS_CHOICES = [
        ('draft', 'Borrador'),       # Factura en proceso de creacion
        ('pending', 'Pendiente'),    # Factura creada pero no enviada
        ('sent', 'Enviada'),         # Factura enviada al cliente
        ('paid', 'Pagada'),          # Factura completamente pagada
        ('partial', 'Pago Parcial'), # Factura con pago parcial recibido
        ('overdue', 'Vencida'),      # Factura con fecha de vencimiento pasada
        ('cancelled', 'Cancelada'),  # Factura anulada
    ]

    # Campo de identificador primario usando UUID para mayor seguridad
    # editable=False evita que se modifique desde formularios
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Numero de factura legible y unico, generado automaticamente
    invoice_number = models.CharField(max_length=50, unique=True)

    # ID del caso legal asociado a esta factura (puede ser nulo)
    # db_index=True mejora el rendimiento de busquedas por este campo
    case_id = models.UUIDField(db_index=True, null=True, blank=True)

    # Numero del caso para referencia rapida sin necesidad de consultar otro servicio
    case_number = models.CharField(max_length=50, blank=True)

    # ID del cliente (referencia al servicio de clientes)
    client_id = models.UUIDField(db_index=True)

    # Nombre del cliente almacenado localmente para evitar consultas externas
    client_name = models.CharField(max_length=255)

    # Email del cliente para envio de facturas
    client_email = models.EmailField(blank=True)

    # Direccion completa del cliente para la factura
    client_address = models.TextField(blank=True)

    # Identificacion fiscal del cliente (RFC, NIT, RUC, etc.)
    client_tax_id = models.CharField(max_length=50, blank=True)

    # Estado actual de la factura, por defecto es borrador
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Moneda en la que se emite la factura (codigo ISO 4217)
    currency = models.CharField(max_length=3, default='COP')

    # Subtotal: suma de todos los items antes de impuestos y descuentos
    # max_digits=15 permite valores hasta 9,999,999,999,999.99
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Porcentaje de impuesto a aplicar (ej: 16.00 para 16%)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Monto calculado del impuesto
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Descuento aplicado a la factura
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Monto total de la factura (subtotal + impuestos - descuentos)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Cantidad total pagada hasta el momento
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Saldo pendiente por pagar (total_amount - amount_paid)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Fecha de emision de la factura
    issue_date = models.DateField()

    # Fecha de vencimiento para el pago
    due_date = models.DateField()

    # Fecha en que se completo el pago (nulo si no esta pagada)
    paid_date = models.DateField(null=True, blank=True)

    # Notas adicionales visibles en la factura
    notes = models.TextField(blank=True)

    # Terminos y condiciones de pago
    terms = models.TextField(blank=True)

    # ID del usuario que creo la factura
    created_by_id = models.UUIDField()

    # Nombre del usuario que creo la factura
    created_by_name = models.CharField(max_length=255)

    # Fecha y hora de creacion del registro (automatico)
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha y hora de ultima actualizacion (automatico)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadatos del modelo Invoice.

        Define configuraciones adicionales como el nombre de la tabla,
        ordenamiento predeterminado e indices para optimizar consultas.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'invoices'

        # Ordenamiento predeterminado: mas recientes primero
        ordering = ['-created_at']

        # Indices adicionales para mejorar rendimiento de consultas frecuentes
        indexes = [
            models.Index(fields=['client_id']),  # Busquedas por cliente
            models.Index(fields=['case_id']),    # Busquedas por caso
            models.Index(fields=['status']),     # Filtrado por estado
            models.Index(fields=['due_date']),   # Filtrado por fecha de vencimiento
        ]

    def __str__(self):
        """
        Representacion en texto de la factura.

        Returns:
            str: Numero de factura y nombre del cliente
        """
        return f"{self.invoice_number} - {self.client_name}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe el metodo save para generar el numero de factura automaticamente
        y calcular los totales antes de guardar.

        El numero de factura sigue el formato: INV-YYYY-NNNNN
        donde YYYY es el ano actual y NNNNN es un consecutivo de 5 digitos.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave
        """
        # Generar numero de factura si no existe
        if not self.invoice_number:
            # Importar datetime para obtener el ano actual
            import datetime
            year = datetime.datetime.now().year

            # Buscar la ultima factura del ano actual para determinar el siguiente numero
            last = Invoice.objects.filter(
                invoice_number__startswith=f"INV-{year}"
            ).order_by('-invoice_number').first()

            # Calcular el siguiente numero consecutivo
            num = int(last.invoice_number.split('-')[-1]) + 1 if last else 1

            # Asignar el numero de factura con formato de 5 digitos
            self.invoice_number = f"INV-{year}-{num:05d}"

        # Calcular totales antes de guardar
        self.calculate_totals()

        # Llamar al metodo save del padre para guardar en la base de datos
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """
        Calcula los totales de la factura basandose en los items asociados.

        Este metodo calcula:
        - subtotal: suma de todos los items
        - tax_amount: impuesto calculado sobre el subtotal
        - total_amount: subtotal + impuestos - descuentos
        - balance_due: total - pagos realizados
        """
        # Calcular subtotal sumando el total de cada item
        # Solo si la factura ya existe en la base de datos (tiene pk)
        self.subtotal = sum(item.total for item in self.items.all()) if self.pk else Decimal('0')

        # Calcular el monto del impuesto
        self.tax_amount = self.subtotal * (self.tax_rate / 100)

        # Calcular el monto total (subtotal + impuesto - descuento)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount

        # Calcular el saldo pendiente (total - pagado)
        self.balance_due = self.total_amount - self.amount_paid


class InvoiceItem(models.Model):
    """
    Modelo que representa un item o concepto dentro de una factura.

    Cada item describe un servicio o producto facturado, incluyendo
    la cantidad, precio unitario y total calculado.

    Atributos:
        id: Identificador unico del item (UUID)
        invoice: Factura a la que pertenece el item
        description: Descripcion del servicio o producto
        quantity: Cantidad de unidades
        unit_price: Precio por unidad
        total: Total calculado (quantity * unit_price)
        time_entry_id: ID de la entrada de tiempo asociada (si aplica)
    """

    # Identificador unico del item
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con la factura padre
    # on_delete=CASCADE elimina los items cuando se elimina la factura
    # related_name='items' permite acceder a los items desde la factura como invoice.items
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')

    # Descripcion detallada del servicio o producto
    description = models.TextField()

    # Cantidad de unidades (permite decimales para horas facturadas)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    # Precio por unidad
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    # Total del item (calculado automaticamente)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # ID de la entrada de tiempo asociada (para facturacion por horas)
    time_entry_id = models.UUIDField(null=True, blank=True)

    # Fecha de creacion del item
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadatos del modelo InvoiceItem.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'invoice_items'

        # Ordenar items por fecha de creacion (mas antiguos primero)
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        """
        Sobrescribe el metodo save para calcular el total del item automaticamente.

        El total se calcula como: cantidad * precio_unitario

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave
        """
        # Calcular el total multiplicando cantidad por precio unitario
        self.total = self.quantity * self.unit_price

        # Guardar el item en la base de datos
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Modelo que representa un pago realizado a una factura.

    Los pagos se registran individualmente permitiendo pagos parciales
    y multiples pagos para una misma factura.

    Atributos:
        id: Identificador unico del pago (UUID)
        invoice: Factura a la que corresponde el pago
        payment_number: Numero de referencia del pago
        amount: Monto del pago
        method: Metodo de pago utilizado
        payment_date: Fecha en que se realizo el pago
    """

    # Opciones de metodos de pago disponibles
    METHOD_CHOICES = [
        ('cash', 'Efectivo'),        # Pago en efectivo
        ('check', 'Cheque'),         # Pago con cheque
        ('transfer', 'Transferencia'),  # Transferencia bancaria
        ('card', 'Tarjeta'),         # Pago con tarjeta de credito/debito
        ('other', 'Otro'),           # Otros metodos de pago
    ]

    # Identificador unico del pago
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con la factura
    # related_name='payments' permite acceder a los pagos como invoice.payments
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')

    # Numero de pago unico para referencia
    payment_number = models.CharField(max_length=50, unique=True)

    # Monto del pago realizado
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Metodo de pago utilizado
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    # Fecha en que se realizo el pago
    payment_date = models.DateField()

    # Referencia externa (numero de transaccion, cheque, etc.)
    reference = models.CharField(max_length=100, blank=True)

    # Notas adicionales sobre el pago
    notes = models.TextField(blank=True)

    # ID del usuario que registro el pago
    recorded_by_id = models.UUIDField()

    # Nombre del usuario que registro el pago
    recorded_by_name = models.CharField(max_length=255)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metadatos del modelo Payment.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'payments'

        # Ordenar pagos por fecha (mas recientes primero)
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        """
        Sobrescribe el metodo save para generar el numero de pago automaticamente
        y actualizar el estado de la factura asociada.

        El numero de pago sigue el formato: PAY-YYYY-NNNNN
        donde YYYY es el ano actual y NNNNN es un consecutivo de 5 digitos.

        Despues de guardar el pago, actualiza automaticamente:
        - El monto pagado de la factura
        - El saldo pendiente
        - El estado de la factura (pagada, parcial, etc.)

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos de palabra clave
        """
        # Generar numero de pago si no existe
        if not self.payment_number:
            import datetime
            year = datetime.datetime.now().year

            # Buscar el ultimo pago del ano para determinar el siguiente numero
            last = Payment.objects.filter(
                payment_number__startswith=f"PAY-{year}"
            ).order_by('-payment_number').first()

            # Calcular el siguiente numero consecutivo
            num = int(last.payment_number.split('-')[-1]) + 1 if last else 1

            # Asignar el numero de pago
            self.payment_number = f"PAY-{year}-{num:05d}"

        # Guardar el pago en la base de datos
        super().save(*args, **kwargs)

        # Actualizar los totales de la factura asociada
        invoice = self.invoice

        # Sumar todos los pagos de la factura
        invoice.amount_paid = sum(p.amount for p in invoice.payments.all())

        # Calcular el saldo pendiente
        invoice.balance_due = invoice.total_amount - invoice.amount_paid

        # Actualizar el estado de la factura segun los pagos
        if invoice.balance_due <= 0:
            # Si el saldo es cero o negativo, la factura esta pagada
            invoice.status = 'paid'
            invoice.paid_date = self.payment_date
        elif invoice.amount_paid > 0:
            # Si hay pagos pero aun hay saldo, es pago parcial
            invoice.status = 'partial'

        # Guardar los cambios en la factura
        invoice.save()


class ClientRateAgreement(models.Model):
    """
    Modelo que representa un acuerdo de tarifas con un cliente.

    Permite definir diferentes tipos de tarifas (por hora, fija, contingencia, etc.)
    que se aplicaran al facturar servicios a un cliente especifico.

    Atributos:
        id: Identificador unico del acuerdo (UUID)
        client_id: ID del cliente
        case_id: ID del caso especifico (opcional)
        rate_type: Tipo de tarifa aplicada
        rate: Monto de la tarifa
        effective_date: Fecha desde la cual aplica el acuerdo
        is_active: Indica si el acuerdo esta vigente
    """

    # Opciones de tipos de tarifa disponibles
    RATE_TYPE_CHOICES = [
        ('hourly', 'Por Hora'),       # Tarifa por hora trabajada
        ('fixed', 'Tarifa Fija'),     # Tarifa fija por servicio
        ('contingency', 'Contingencia'),  # Porcentaje sobre el resultado
        ('retainer', 'Anticipo'),     # Tarifa de anticipo mensual
    ]

    # Identificador unico del acuerdo
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ID del cliente al que aplica el acuerdo
    client_id = models.UUIDField(db_index=True)

    # ID del caso especifico (nulo si aplica a todos los casos del cliente)
    case_id = models.UUIDField(null=True, blank=True)

    # Tipo de tarifa
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES)

    # Monto de la tarifa (por hora, fija, o porcentaje segun el tipo)
    rate = models.DecimalField(max_digits=12, decimal_places=2)

    # Moneda del acuerdo
    currency = models.CharField(max_length=3, default='COP')

    # Descripcion adicional del acuerdo
    description = models.TextField(blank=True)

    # Fecha desde la cual el acuerdo es efectivo
    effective_date = models.DateField()

    # Fecha de finalizacion del acuerdo (nulo si es indefinido)
    end_date = models.DateField(null=True, blank=True)

    # Indica si el acuerdo esta activo
    is_active = models.BooleanField(default=True)

    # Fecha de creacion del registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadatos del modelo ClientRateAgreement.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'client_rate_agreements'

        # Ordenar por fecha efectiva (mas recientes primero)
        ordering = ['-effective_date']


class PaymentGatewayTransaction(models.Model):
    """
    Modelo que representa una transaccion de pago a traves de pasarelas externas.

    Este modelo registra los pagos procesados a traves de servicios como
    Stripe, PayPal u otras pasarelas de pago electronico. Almacena toda
    la informacion necesaria para seguimiento y reconciliacion.

    Atributos:
        id: Identificador unico de la transaccion (UUID)
        invoice: Factura asociada a la transaccion
        gateway: Pasarela de pago utilizada
        gateway_transaction_id: ID de la transaccion en la pasarela
        amount: Monto de la transaccion
        currency: Moneda de la transaccion
        status: Estado de la transaccion
        payment_method_type: Tipo de metodo de pago usado
        gateway_response: Respuesta completa de la pasarela en JSON
        error_message: Mensaje de error si la transaccion fallo
        client_ip: IP del cliente que inicio el pago
        created_at: Fecha de creacion de la transaccion
        updated_at: Fecha de ultima actualizacion
    """

    # Opciones de pasarelas de pago soportadas
    GATEWAY_CHOICES = [
        ('stripe', 'Stripe'),           # Pasarela Stripe
        ('paypal', 'PayPal'),           # Pasarela PayPal
        ('mercadopago', 'MercadoPago'), # Pasarela MercadoPago (Latinoamerica)
        ('manual', 'Manual'),           # Pago manual/externo
    ]

    # Opciones de estado de la transaccion
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),       # Transaccion iniciada pero no completada
        ('processing', 'Procesando'),   # Transaccion en proceso
        ('completed', 'Completada'),    # Transaccion exitosa
        ('failed', 'Fallida'),          # Transaccion fallida
        ('cancelled', 'Cancelada'),     # Transaccion cancelada por el usuario
        ('refunded', 'Reembolsada'),    # Transaccion reembolsada
        ('disputed', 'Disputa'),        # Transaccion en disputa
    ]

    # Opciones de tipos de metodo de pago
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Tarjeta de Credito/Debito'),    # Pago con tarjeta
        ('bank_transfer', 'Transferencia Bancaria'), # Transferencia
        ('paypal_balance', 'Saldo PayPal'),        # Saldo de cuenta PayPal
        ('wallet', 'Billetera Digital'),           # Billetera electronica
        ('other', 'Otro'),                         # Otros metodos
    ]

    # Identificador unico de la transaccion
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacion con la factura que se esta pagando
    # related_name permite acceder como invoice.gateway_transactions
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='gateway_transactions'
    )

    # Pasarela de pago utilizada
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)

    # ID unico de la transaccion en la pasarela externa
    # Este ID se usa para verificar y reconciliar pagos
    gateway_transaction_id = models.CharField(max_length=255, unique=True)

    # Monto de la transaccion
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Moneda de la transaccion (codigo ISO 4217)
    currency = models.CharField(max_length=3, default='COP')

    # Estado actual de la transaccion
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Tipo de metodo de pago utilizado
    payment_method_type = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True
    )

    # Ultimos 4 digitos de la tarjeta (si aplica)
    card_last_four = models.CharField(max_length=4, blank=True)

    # Marca de la tarjeta (visa, mastercard, etc.)
    card_brand = models.CharField(max_length=20, blank=True)

    # Respuesta completa de la pasarela en formato JSON
    # Almacena toda la informacion devuelta por la API
    gateway_response = models.JSONField(default=dict, blank=True)

    # Mensaje de error si la transaccion fallo
    error_message = models.TextField(blank=True)

    # Codigo de error de la pasarela
    error_code = models.CharField(max_length=50, blank=True)

    # IP del cliente que inicio la transaccion (para prevencion de fraude)
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    # Email del pagador
    payer_email = models.EmailField(blank=True)

    # Nombre del pagador
    payer_name = models.CharField(max_length=255, blank=True)

    # URL de checkout (para PayPal y metodos similares)
    checkout_url = models.URLField(max_length=500, blank=True)

    # ID del Payment creado cuando se completa la transaccion
    payment_id = models.UUIDField(null=True, blank=True)

    # Fecha de creacion de la transaccion
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Metadatos del modelo PaymentGatewayTransaction.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'payment_gateway_transactions'

        # Ordenar por fecha de creacion (mas recientes primero)
        ordering = ['-created_at']

        # Indices para consultas frecuentes
        indexes = [
            models.Index(fields=['invoice']),           # Busquedas por factura
            models.Index(fields=['gateway']),           # Busquedas por pasarela
            models.Index(fields=['status']),            # Filtrado por estado
            models.Index(fields=['gateway_transaction_id']),  # Busqueda por ID externo
        ]

    def __str__(self):
        """
        Representacion en texto de la transaccion.

        Returns:
            str: Descripcion de la transaccion con gateway y estado
        """
        return f"{self.gateway} - {self.gateway_transaction_id} - {self.status}"

    def complete_payment(self):
        """
        Marca la transaccion como completada y crea el registro de pago asociado.

        Este metodo se llama cuando la pasarela confirma que el pago fue exitoso.
        Crea automaticamente un registro en la tabla Payment y actualiza
        la factura correspondiente.

        Returns:
            Payment: El registro de pago creado
        """
        # Solo procesar si la transaccion no esta ya completada
        if self.status != 'completed':
            # Cambiar estado a completada
            self.status = 'completed'

            # Crear el registro de pago
            payment = Payment.objects.create(
                invoice=self.invoice,
                amount=self.amount,
                method='card' if self.payment_method_type == 'card' else 'other',
                payment_date=self.updated_at.date(),
                reference=f"{self.gateway}:{self.gateway_transaction_id}",
                notes=f"Pago via {self.get_gateway_display()}",
                recorded_by_id=self.invoice.created_by_id,
                recorded_by_name="Sistema - Pago Automatico"
            )

            # Guardar referencia al pago creado
            self.payment_id = payment.id
            self.save()

            return payment

        return None

    def process_refund(self, refund_amount=None, refund_reason=''):
        """
        Procesa un reembolso para esta transaccion.

        Este metodo se llama cuando la pasarela notifica un reembolso.
        Actualiza la transaccion, elimina/ajusta el pago asociado y
        actualiza la factura para reflejar el reembolso.

        Args:
            refund_amount: Monto del reembolso (None = reembolso total)
            refund_reason: Razon del reembolso

        Returns:
            dict: Informacion del reembolso procesado
        """
        from decimal import Decimal
        import datetime

        # Si no se especifica monto, es reembolso total
        if refund_amount is None:
            refund_amount = self.amount
        else:
            refund_amount = Decimal(str(refund_amount))

        # Actualizar estado de la transaccion
        if refund_amount >= self.amount:
            self.status = 'refunded'
        else:
            # Reembolso parcial - mantener como completed pero registrar
            pass

        self.error_message = f"Reembolso: {refund_reason}" if refund_reason else "Reembolso procesado"
        self.save()

        # Buscar y eliminar el pago asociado si existe
        if self.payment_id:
            try:
                payment = Payment.objects.get(id=self.payment_id)
                invoice = payment.invoice

                # Eliminar el pago
                payment.delete()

                # Recalcular totales de la factura
                invoice.amount_paid = sum(p.amount for p in invoice.payments.all())
                invoice.balance_due = invoice.total_amount - invoice.amount_paid

                # Actualizar estado de la factura
                if invoice.balance_due <= 0:
                    invoice.status = 'paid'
                elif invoice.amount_paid > 0:
                    invoice.status = 'partial'
                else:
                    # Volver a estado 'sent' si no hay pagos
                    invoice.status = 'sent'
                    invoice.paid_date = None

                invoice.save()

                # Limpiar referencia al pago
                self.payment_id = None
                self.save()

                return {
                    'success': True,
                    'refund_amount': float(refund_amount),
                    'invoice_status': invoice.status,
                    'balance_due': float(invoice.balance_due),
                    'amount_paid': float(invoice.amount_paid)
                }

            except Payment.DoesNotExist:
                pass

        return {
            'success': False,
            'error': 'No se encontro el pago asociado'
        }
