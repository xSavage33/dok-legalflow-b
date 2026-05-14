"""
Modulo de Serializadores del Portal de Clientes (Client Portal Service)

Este archivo contiene los serializadores de Django REST Framework que se encargan
de convertir los modelos de datos a formato JSON (serializacion) y viceversa
(deserializacion). Los serializadores tambien validan los datos de entrada.

Contiene tres serializadores principales:
    - ClientPreferenceSerializer: Para las preferencias del cliente
    - MessageSerializer: Para la lectura de mensajes
    - MessageCreateSerializer: Para la creacion de nuevos mensajes

Los serializadores actuan como intermediarios entre los modelos de Django
y las respuestas/peticiones JSON de la API REST.

Autor: Equipo LegalFlow
"""

# Importacion del modulo serializers de Django REST Framework
# Este modulo proporciona clases base para crear serializadores
# ModelSerializer: Serializador automatico basado en modelos de Django
# serializers.CharField, etc.: Campos para definir serializadores personalizados
from rest_framework import serializers

# Importacion de los modelos locales que seran serializados
# ClientPreference: Modelo de preferencias del cliente
# Message: Modelo de mensajes del portal
from .models import ClientPreference, Message


class ClientPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo ClientPreference.

    Este serializador convierte objetos ClientPreference a JSON y viceversa.
    Se utiliza para que los clientes puedan ver y actualizar sus preferencias
    de notificacion, idioma y zona horaria.

    Campos incluidos:
        - id: Identificador unico de las preferencias (solo lectura)
        - user_id: Identificador del usuario asociado (solo lectura)
        - email_notifications: Preferencia de notificaciones por email
        - sms_notifications: Preferencia de notificaciones por SMS
        - case_updates: Preferencia de actualizaciones de casos
        - billing_updates: Preferencia de actualizaciones de facturacion
        - deadline_reminders: Preferencia de recordatorios de fechas limite
        - language: Codigo del idioma preferido
        - timezone: Zona horaria del cliente
        - created_at: Fecha de creacion (solo lectura)
        - updated_at: Fecha de ultima actualizacion (solo lectura)

    Campos de solo lectura:
        Los campos id, user_id, created_at y updated_at no pueden ser
        modificados por el cliente a traves de la API.
    """

    class Meta:
        """
        Clase Meta para configurar el serializador.

        Define el modelo asociado, los campos a incluir en la serializacion
        y cuales campos son de solo lectura.
        """
        # Modelo de Django que este serializador representa
        model = ClientPreference

        # Lista de campos a incluir en la serializacion
        # Estos campos estaran disponibles en el JSON de entrada y salida
        fields = [
            'id',                    # Identificador unico UUID
            'user_id',               # ID del usuario asociado
            'email_notifications',   # Preferencia de notificaciones por correo
            'sms_notifications',     # Preferencia de notificaciones por SMS
            'case_updates',          # Preferencia de actualizaciones de casos
            'billing_updates',       # Preferencia de actualizaciones de facturacion
            'deadline_reminders',    # Preferencia de recordatorios de fechas limite
            'language',              # Codigo del idioma preferido (ej: 'es', 'en')
            'timezone',              # Zona horaria (ej: 'America/Bogota')
            'created_at',            # Marca de tiempo de creacion
            'updated_at'             # Marca de tiempo de ultima modificacion
        ]

        # Campos que no pueden ser modificados a traves de la API
        # Estos campos seran ignorados si se envian en una peticion POST/PUT/PATCH
        read_only_fields = [
            'id',           # El identificador es generado automaticamente
            'user_id',      # El usuario se asigna automaticamente
            'created_at',   # La fecha de creacion es automatica
            'updated_at'    # La fecha de actualizacion es automatica
        ]


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializador completo para el modelo Message (lectura).

    Este serializador se utiliza para convertir mensajes a JSON cuando se
    leen o listan. Incluye todos los campos del mensaje mas un campo
    adicional que muestra el estado en formato legible.

    Campos incluidos:
        - id: Identificador unico del mensaje
        - sender_id: ID del usuario remitente
        - sender_name: Nombre del remitente
        - sender_role: Rol del remitente (cliente, abogado, etc.)
        - recipient_id: ID del usuario destinatario
        - recipient_name: Nombre del destinatario
        - case_id: ID del caso asociado (opcional)
        - case_number: Numero de referencia del caso
        - subject: Asunto del mensaje
        - content: Contenido del mensaje
        - status: Estado del mensaje (sent, delivered, read)
        - status_display: Estado en formato legible (Enviado, Entregado, Leido)
        - read_at: Fecha y hora de lectura
        - parent_message_id: ID del mensaje padre (para respuestas)
        - created_at: Fecha de creacion del mensaje

    Campos de solo lectura:
        La mayoria de campos son de solo lectura porque este serializador
        se usa principalmente para mostrar mensajes, no para crearlos.
    """

    # Campo adicional que obtiene el valor legible del estado
    # source='get_status_display': Llama al metodo get_status_display() del modelo
    # Este metodo es generado automaticamente por Django para campos con choices
    # Convierte 'sent' -> 'Enviado', 'delivered' -> 'Entregado', 'read' -> 'Leido'
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        """
        Clase Meta para configurar el serializador de mensajes.

        Define el modelo, los campos incluidos y cuales son de solo lectura.
        """
        # Modelo de Django que este serializador representa
        model = Message

        # Lista completa de campos a incluir en la serializacion
        fields = [
            'id',                  # Identificador unico UUID del mensaje
            'sender_id',           # UUID del usuario remitente
            'sender_name',         # Nombre completo del remitente
            'sender_role',         # Rol del remitente (client, lawyer, admin)
            'recipient_id',        # UUID del usuario destinatario
            'recipient_name',      # Nombre completo del destinatario
            'case_id',             # UUID del caso asociado (puede ser nulo)
            'case_number',         # Numero de referencia del caso
            'subject',             # Asunto o titulo del mensaje
            'content',             # Cuerpo/contenido del mensaje
            'status',              # Estado actual (sent, delivered, read)
            'status_display',      # Estado en formato legible (Enviado, etc.)
            'read_at',             # Fecha y hora en que se leyo el mensaje
            'parent_message_id',   # UUID del mensaje padre (para hilos)
            'created_at'           # Fecha y hora de creacion del mensaje
        ]

        # Campos que no pueden ser modificados a traves de este serializador
        # La informacion del remitente y los timestamps son automaticos
        read_only_fields = [
            'id',            # El identificador es generado automaticamente
            'sender_id',     # El remitente se asigna automaticamente
            'sender_name',   # El nombre se obtiene del usuario autenticado
            'sender_role',   # El rol se obtiene del usuario autenticado
            'status',        # El estado inicial es 'sent' automaticamente
            'read_at',       # Se establece cuando el destinatario lee el mensaje
            'created_at'     # La fecha de creacion es automatica
        ]


class MessageCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear nuevos mensajes.

    Este serializador se utiliza especificamente para la creacion de mensajes.
    Solo incluye los campos que el cliente debe proporcionar, mientras que
    los datos del remitente se asignan automaticamente desde el usuario autenticado.

    Campos requeridos del cliente:
        - subject: Asunto del mensaje
        - content: Contenido del mensaje

    Campos opcionales:
        - recipient_id: ID del destinatario (si no se proporciona, se asigna automaticamente)
        - recipient_name: Nombre del destinatario (si no se proporciona, se asigna automaticamente)
        - case_id: ID del caso asociado al mensaje
        - case_number: Numero de referencia del caso
        - parent_message_id: ID del mensaje al que se responde

    Campos asignados automaticamente:
        - sender_id: Se obtiene de request.user.id
        - sender_name: Se obtiene de request.user.email
        - sender_role: Se obtiene de request.user.role
        - status: Se establece como 'sent' por defecto del modelo
    """

    # Hacer recipient_id y recipient_name opcionales para clientes
    recipient_id = serializers.UUIDField(required=False, allow_null=True)
    recipient_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        """
        Clase Meta para configurar el serializador de creacion de mensajes.

        Define el modelo y los campos que el cliente debe proporcionar.
        """
        # Modelo de Django que este serializador representa
        model = Message

        # Solo los campos que el cliente necesita proporcionar al crear un mensaje
        # Los campos del remitente se asignan automaticamente en el metodo create()
        fields = [
            'recipient_id',        # UUID del usuario destinatario (opcional, se auto-asigna)
            'recipient_name',      # Nombre del destinatario (opcional, se auto-asigna)
            'case_id',             # UUID del caso asociado (opcional)
            'case_number',         # Numero de referencia del caso (opcional)
            'subject',             # Asunto del mensaje (requerido)
            'content',             # Contenido del mensaje (requerido)
            'parent_message_id'    # UUID del mensaje padre para respuestas (opcional)
        ]

    def create(self, validated_data):
        """
        Crea una nueva instancia de Message con los datos validados.

        Este metodo sobrescribe el create() por defecto de ModelSerializer
        para agregar automaticamente la informacion del remitente desde
        el usuario autenticado que hace la peticion.

        Si no se proporciona recipient_id/recipient_name, intenta obtener
        el abogado principal del caso o asigna un destinatario por defecto.

        Args:
            validated_data (dict): Diccionario con los datos validados del formulario
                Contiene: subject, content,
                y opcionalmente: recipient_id, recipient_name, case_id, case_number, parent_message_id

        Returns:
            Message: La nueva instancia del mensaje creada y guardada en la base de datos
        """
        import requests
        import uuid
        from django.conf import settings

        # Obtener el objeto request del contexto del serializador
        request = self.context.get('request')

        # Agregar el ID del usuario autenticado como remitente del mensaje
        validated_data['sender_id'] = request.user.id

        # Agregar el email del usuario como nombre del remitente
        validated_data['sender_name'] = request.user.email

        # Agregar el rol del usuario autenticado
        validated_data['sender_role'] = request.user.role

        # Si no se proporciono recipient_id, intentar obtenerlo automaticamente
        if not validated_data.get('recipient_id'):
            recipient_id = None
            recipient_name = 'Equipo Legal'

            # Si hay un caso asociado, intentar obtener el abogado principal
            case_id = validated_data.get('case_id')
            if case_id:
                try:
                    headers = {
                        'Authorization': request.META.get('HTTP_AUTHORIZATION', ''),
                        'Host': 'localhost'
                    }
                    matter_url = getattr(settings, 'MATTER_SERVICE_URL', 'http://matter-service:8000')
                    response = requests.get(
                        f"{matter_url}/api/cases/{case_id}/",
                        headers=headers,
                        timeout=5
                    )
                    if response.status_code == 200:
                        case_data = response.json()
                        # Intentar obtener lead_attorney_id del caso
                        lead_attorney_id = case_data.get('lead_attorney_id')
                        lead_attorney_name = case_data.get('lead_attorney_name')
                        if lead_attorney_id:
                            recipient_id = lead_attorney_id
                            recipient_name = lead_attorney_name or 'Abogado Principal'
                except Exception as e:
                    # Si falla, usar el destinatario por defecto
                    print(f"Error obteniendo info del caso: {e}")

            # Si aun no hay recipient_id, usar un ID de sistema por defecto
            # UUID del sistema para mensajes sin destinatario especifico
            if not recipient_id:
                # Usar un UUID fijo para el "buzon general" del equipo legal
                recipient_id = uuid.UUID('00000000-0000-0000-0000-000000000001')
                recipient_name = 'Equipo Legal LegalFlow'

            validated_data['recipient_id'] = recipient_id
            validated_data['recipient_name'] = recipient_name

        # Si hay recipient_id pero no recipient_name, asignar un nombre generico
        elif not validated_data.get('recipient_name'):
            validated_data['recipient_name'] = 'Destinatario'

        # Llamar al metodo create() de la clase padre (ModelSerializer)
        return super().create(validated_data)


class SystemNotificationSerializer(serializers.ModelSerializer):
    """
    Serializador para crear mensajes de notificacion del sistema.

    Este serializador se utiliza para que otros microservicios puedan
    enviar notificaciones a los clientes sin requerir autenticacion de usuario.
    Es usado internamente por servicios como billing_service para notificar
    sobre nuevas facturas, pagos, etc.

    Todos los campos del remitente deben ser proporcionados explicitamente
    ya que no hay un usuario autenticado haciendo la peticion.

    Campos requeridos:
        - sender_id: UUID del servicio o usuario sistema
        - sender_name: Nombre del remitente (ej: "Sistema de Facturacion")
        - sender_role: Rol del remitente (ej: "system")
        - recipient_id: UUID del cliente destinatario
        - recipient_name: Nombre del cliente
        - subject: Asunto del mensaje
        - content: Contenido del mensaje

    Campos opcionales:
        - case_id: UUID del caso asociado
        - case_number: Numero de referencia del caso
    """

    class Meta:
        model = Message
        fields = [
            'sender_id',
            'sender_name',
            'sender_role',
            'recipient_id',
            'recipient_name',
            'case_id',
            'case_number',
            'subject',
            'content',
        ]
