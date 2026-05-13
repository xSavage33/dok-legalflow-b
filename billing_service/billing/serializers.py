"""
Modulo de Serializadores del Servicio de Facturacion (Billing Service)

Este archivo define los serializadores que convierten los modelos de Django
a formato JSON (y viceversa) para la API REST. Los serializadores tambien
manejan la validacion de datos de entrada.

Serializadores incluidos:
- InvoiceItemSerializer: Serializa items de factura
- PaymentSerializer: Serializa pagos
- InvoiceListSerializer: Serializa facturas para listados (campos resumidos)
- InvoiceDetailSerializer: Serializa facturas con todos los detalles
- InvoiceCreateSerializer: Serializa datos para crear facturas
- ClientRateAgreementSerializer: Serializa acuerdos de tarifas
- BillingSummarySerializer: Serializa el resumen de facturacion

Autor: Equipo de Desarrollo LegalFlow
Fecha de creacion: 2024
"""

# Importacion del modulo serializers de Django REST Framework
# Proporciona clases base para crear serializadores
from rest_framework import serializers

# Importacion de los modelos que seran serializados
from .models import Invoice, InvoiceItem, Payment, ClientRateAgreement


class InvoiceItemSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo InvoiceItem (items de factura).

    Convierte instancias de InvoiceItem a JSON y valida datos de entrada
    al crear o actualizar items de factura.

    Campos:
    - id: Identificador unico (solo lectura)
    - description: Descripcion del servicio/producto
    - quantity: Cantidad de unidades
    - unit_price: Precio unitario
    - total: Total calculado (solo lectura, se calcula automaticamente)
    - time_entry_id: ID de entrada de tiempo asociada (opcional)
    - created_at: Fecha de creacion (solo lectura)
    """

    class Meta:
        """
        Metadatos del serializador que definen el modelo y campos a serializar.
        """
        # Modelo que sera serializado
        model = InvoiceItem

        # Lista de campos a incluir en la serializacion
        fields = [
            'id',            # Identificador unico del item
            'description',   # Descripcion del servicio o producto
            'quantity',      # Cantidad de unidades
            'unit_price',    # Precio por unidad
            'total',         # Total calculado (cantidad * precio)
            'time_entry_id', # Referencia a entrada de tiempo (opcional)
            'created_at'     # Fecha de creacion del item
        ]

        # Campos que no pueden ser modificados por el cliente
        # Estos se calculan o generan automaticamente
        read_only_fields = ['id', 'total', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo Payment (pagos).

    Convierte instancias de Payment a JSON y valida datos de entrada
    al registrar nuevos pagos.

    Incluye un campo adicional 'method_display' que muestra el nombre
    legible del metodo de pago en lugar del codigo interno.

    Campos principales:
    - payment_number: Numero de referencia del pago (solo lectura)
    - amount: Monto del pago
    - method: Codigo del metodo de pago
    - method_display: Nombre legible del metodo (solo lectura)
    - payment_date: Fecha del pago
    """

    # Campo adicional para mostrar el nombre legible del metodo de pago
    # Utiliza el metodo get_method_display() del modelo Django
    method_display = serializers.CharField(source='get_method_display', read_only=True)

    class Meta:
        """
        Metadatos del serializador.
        """
        # Modelo que sera serializado
        model = Payment

        # Lista de campos a incluir
        fields = [
            'id',               # Identificador unico del pago
            'payment_number',   # Numero de referencia (PAY-YYYY-NNNNN)
            'amount',           # Monto del pago
            'method',           # Codigo del metodo de pago
            'method_display',   # Nombre legible del metodo
            'payment_date',     # Fecha en que se realizo el pago
            'reference',        # Referencia externa (numero de cheque, transaccion)
            'notes',            # Notas adicionales
            'recorded_by_id',   # ID del usuario que registro el pago
            'recorded_by_name', # Nombre del usuario que registro el pago
            'created_at'        # Fecha de creacion del registro
        ]

        # Campos que se generan automaticamente y no pueden ser modificados
        read_only_fields = [
            'id',               # Generado automaticamente (UUID)
            'payment_number',   # Generado automaticamente (PAY-YYYY-NNNNN)
            'recorded_by_id',   # Se obtiene del usuario autenticado
            'recorded_by_name', # Se obtiene del usuario autenticado
            'created_at'        # Se establece automaticamente
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    """
    Serializador para listar facturas con campos resumidos.

    Este serializador se utiliza cuando se necesita mostrar una lista
    de facturas sin todos los detalles (items, pagos, etc.).
    Es mas eficiente para listados ya que no incluye relaciones anidadas.

    Campos incluidos:
    - Datos basicos de identificacion (id, invoice_number)
    - Informacion del cliente (client_name)
    - Estado y montos principales
    - Fechas importantes
    """

    # Campo adicional para mostrar el nombre legible del estado
    # Por ejemplo: 'draft' -> 'Borrador', 'paid' -> 'Pagada'
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        """
        Metadatos del serializador.
        """
        # Modelo que sera serializado
        model = Invoice

        # Campos resumidos para la lista de facturas
        fields = [
            'id',              # Identificador unico de la factura
            'invoice_number',  # Numero legible de factura
            'client_name',     # Nombre del cliente
            'case_number',     # Numero del caso asociado
            'status',          # Codigo de estado
            'status_display',  # Nombre legible del estado
            'total_amount',    # Monto total de la factura
            'amount_paid',     # Monto ya pagado
            'balance_due',     # Saldo pendiente por pagar
            'issue_date',      # Fecha de emision
            'due_date',        # Fecha de vencimiento
            'created_at'       # Fecha de creacion
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """
    Serializador completo para el detalle de una factura individual.

    Este serializador incluye todos los campos de la factura, asi como
    los items y pagos relacionados mediante serializadores anidados.
    Se utiliza cuando se necesita ver todos los detalles de una factura.

    Incluye:
    - Todos los campos de la factura
    - Lista de items (InvoiceItemSerializer)
    - Lista de pagos (PaymentSerializer)
    - Campos calculados (subtotal, tax_amount, total_amount, etc.)
    """

    # Serializador anidado para los items de la factura
    # many=True indica que es una lista de items
    # read_only=True porque los items se gestionan por separado
    items = InvoiceItemSerializer(many=True, read_only=True)

    # Serializador anidado para los pagos de la factura
    payments = PaymentSerializer(many=True, read_only=True)

    # Campo para mostrar el nombre legible del estado
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        """
        Metadatos del serializador.
        """
        # Modelo que sera serializado
        model = Invoice

        # Todos los campos de la factura incluyendo relaciones
        fields = [
            # Identificadores
            'id',               # UUID de la factura
            'invoice_number',   # Numero legible de factura

            # Informacion del caso
            'case_id',          # ID del caso asociado
            'case_number',      # Numero del caso

            # Informacion del cliente
            'client_id',        # ID del cliente
            'client_name',      # Nombre del cliente
            'client_email',     # Email del cliente
            'client_address',   # Direccion del cliente
            'client_tax_id',    # Identificacion fiscal

            # Estado y moneda
            'status',           # Codigo de estado
            'status_display',   # Nombre legible del estado
            'currency',         # Moneda (COP por defecto)

            # Montos financieros
            'subtotal',         # Suma de items antes de impuestos
            'tax_rate',         # Porcentaje de impuesto
            'tax_amount',       # Monto del impuesto
            'discount_amount',  # Descuento aplicado
            'total_amount',     # Total a pagar
            'amount_paid',      # Monto pagado
            'balance_due',      # Saldo pendiente

            # Fechas
            'issue_date',       # Fecha de emision
            'due_date',         # Fecha de vencimiento
            'paid_date',        # Fecha de pago completo

            # Notas y terminos
            'notes',            # Notas adicionales
            'terms',            # Terminos y condiciones

            # Informacion de creacion
            'created_by_id',    # ID del usuario creador
            'created_by_name',  # Nombre del usuario creador
            'created_at',       # Fecha de creacion
            'updated_at',       # Fecha de ultima actualizacion

            # Relaciones anidadas
            'items',            # Lista de items de la factura
            'payments'          # Lista de pagos recibidos
        ]

        # Campos que no pueden ser modificados directamente
        # Se calculan o generan automaticamente
        read_only_fields = [
            'id',               # Generado automaticamente
            'invoice_number',   # Generado automaticamente
            'subtotal',         # Calculado de los items
            'tax_amount',       # Calculado del subtotal y tax_rate
            'total_amount',     # Calculado (subtotal + tax - discount)
            'amount_paid',      # Suma de los pagos
            'balance_due',      # Calculado (total - pagado)
            'created_by_id',    # Se obtiene del usuario autenticado
            'created_by_name',  # Se obtiene del usuario autenticado
            'created_at',       # Se establece automaticamente
            'updated_at'        # Se actualiza automaticamente
        ]


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializador especializado para crear nuevas facturas.

    Este serializador permite crear una factura junto con sus items
    en una sola operacion (nested create). Los items se envian
    como una lista anidada en el JSON de entrada.

    Ejemplo de uso:
    {
        "client_id": "uuid-del-cliente",
        "client_name": "Nombre del Cliente",
        "issue_date": "2024-01-15",
        "due_date": "2024-02-15",
        "items": [
            {"description": "Servicio legal", "quantity": 10, "unit_price": 150}
        ]
    }
    """

    # Campo anidado para crear items junto con la factura
    # required=False permite crear facturas sin items iniciales
    items = InvoiceItemSerializer(many=True, required=False)

    def validate_items(self, value):
        """
        Valida que items sea una lista valida.

        Esta validacion adicional asegura que el campo items siempre
        sea una lista, manejando casos donde el frontend pueda enviar
        datos en formato incorrecto.

        Args:
            value: El valor del campo items a validar

        Returns:
            list: Lista validada de items

        Raises:
            serializers.ValidationError: Si items no es una lista
        """
        # Si el valor es None o no fue enviado, retornar lista vacia
        if value is None:
            return []

        # Verificar que sea una lista
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "El campo 'items' debe ser una lista de objetos. "
                "Formato esperado: [{\"description\": \"...\", \"quantity\": 1, \"unit_price\": 100}]"
            )

        return value

    class Meta:
        """
        Metadatos del serializador.
        """
        # Modelo que sera serializado
        model = Invoice

        # Campos permitidos al crear una factura
        # No incluye campos calculados ni generados automaticamente
        fields = [
            # Informacion del caso
            'case_id',          # ID del caso (opcional)
            'case_number',      # Numero del caso (opcional)

            # Informacion del cliente (requerido)
            'client_id',        # ID del cliente
            'client_name',      # Nombre del cliente
            'client_email',     # Email del cliente
            'client_address',   # Direccion del cliente
            'client_tax_id',    # Identificacion fiscal

            # Configuracion financiera
            'currency',         # Moneda de la factura
            'tax_rate',         # Porcentaje de impuesto
            'discount_amount',  # Descuento a aplicar

            # Fechas (requeridas)
            'issue_date',       # Fecha de emision
            'due_date',         # Fecha de vencimiento

            # Contenido adicional
            'notes',            # Notas para el cliente
            'terms',            # Terminos y condiciones

            # Items anidados
            'items'             # Lista de items de la factura
        ]

    def create(self, validated_data):
        """
        Crea una nueva factura junto con sus items.

        Este metodo sobrescribe el create() por defecto para manejar
        la creacion de items anidados y establecer los campos del
        usuario creador.

        Proceso:
        1. Extrae los items del diccionario de datos
        2. Agrega informacion del usuario creador
        3. Crea la factura
        4. Crea cada item asociado a la factura
        5. Calcula los totales
        6. Guarda y retorna la factura

        Args:
            validated_data: Diccionario con los datos validados de la factura

        Returns:
            Invoice: La instancia de factura creada
        """
        # Extraer la lista de items del diccionario (si existe)
        # pop() remueve el campo del diccionario y lo retorna
        items_data = validated_data.pop('items', [])

        # Obtener el objeto request del contexto del serializador
        request = self.context.get('request')

        # Agregar informacion del usuario que crea la factura
        validated_data['created_by_id'] = request.user.id
        validated_data['created_by_name'] = request.user.email

        # Crear la factura con los datos validados (sin items)
        invoice = Invoice.objects.create(**validated_data)

        # Crear cada item y asociarlo a la factura
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)

        # Recalcular los totales de la factura con los items creados
        invoice.calculate_totals()

        # Guardar los totales calculados
        invoice.save()

        # Retornar la factura creada
        return invoice


class ClientRateAgreementSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo ClientRateAgreement (acuerdos de tarifas).

    Convierte instancias de acuerdos de tarifas a JSON y valida datos
    de entrada al crear o actualizar acuerdos.

    Incluye un campo adicional para mostrar el tipo de tarifa en
    formato legible.
    """

    # Campo adicional para mostrar el nombre legible del tipo de tarifa
    # Por ejemplo: 'hourly' -> 'Por Hora', 'fixed' -> 'Tarifa Fija'
    rate_type_display = serializers.CharField(source='get_rate_type_display', read_only=True)

    class Meta:
        """
        Metadatos del serializador.
        """
        # Modelo que sera serializado
        model = ClientRateAgreement

        # Lista de campos a incluir
        fields = [
            'id',                # Identificador unico del acuerdo
            'client_id',         # ID del cliente
            'case_id',           # ID del caso (opcional)
            'rate_type',         # Codigo del tipo de tarifa
            'rate_type_display', # Nombre legible del tipo de tarifa
            'rate',              # Monto de la tarifa
            'currency',          # Moneda del acuerdo
            'description',       # Descripcion del acuerdo
            'effective_date',    # Fecha de inicio de vigencia
            'end_date',          # Fecha de fin de vigencia (opcional)
            'is_active',         # Indica si el acuerdo esta activo
            'created_at',        # Fecha de creacion
            'updated_at'         # Fecha de ultima actualizacion
        ]

        # Campos que no pueden ser modificados directamente
        read_only_fields = [
            'id',           # Generado automaticamente
            'created_at',   # Se establece automaticamente
            'updated_at'    # Se actualiza automaticamente
        ]


class BillingSummarySerializer(serializers.Serializer):
    """
    Serializador para el resumen de facturacion.

    Este serializador NO esta vinculado a un modelo de base de datos.
    Se utiliza para serializar datos agregados calculados en la vista
    BillingSummaryView.

    Campos:
    - total_invoiced: Suma total de todas las facturas
    - total_paid: Suma total de pagos recibidos
    - total_outstanding: Saldo pendiente total
    - overdue_amount: Monto vencido (facturas con fecha pasada)
    - by_status: Diccionario con conteo de facturas por estado
    """

    # Monto total facturado (suma de total_amount de todas las facturas)
    # max_digits=15 permite valores muy grandes
    # decimal_places=2 para precision monetaria
    total_invoiced = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Monto total cobrado (suma de amount_paid de todas las facturas)
    total_paid = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Saldo pendiente total (suma de balance_due de facturas activas)
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Monto vencido (suma de balance_due de facturas con due_date pasada)
    overdue_amount = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Diccionario con estadisticas agrupadas por estado
    # Ejemplo: {'draft': 5, 'sent': 10, 'paid': 25}
    by_status = serializers.DictField()
