"""
Notification Worker - Servicio de Notificaciones para LegalFlow

Este modulo implementa un worker de Celery que gestiona todas las notificaciones
del sistema LegalFlow, un software de gestion legal. Sus principales funciones son:

1. Envio de correos electronicos mediante SMTP
2. Recordatorios automaticos de plazos legales
3. Notificaciones de facturas (creadas, enviadas, vencidas, pagadas)
4. Actualizaciones de casos para clientes
5. Notificaciones de mensajes y documentos compartidos
6. Recordatorios de eventos del calendario

El worker utiliza Redis como broker de mensajes y backend de resultados,
y se programa mediante Celery Beat para ejecutar tareas periodicas.

Autor: Equipo LegalFlow
Zona horaria: America/Bogota (Colombia)
"""

# ============================================================================
# IMPORTACIONES
# ============================================================================

# Modulo os: permite acceder a variables de entorno del sistema operativo
import os

# Modulo json: para parsear credenciales de Firebase desde variable de entorno
import json

# Modulo smtplib: proporciona funcionalidad para enviar correos via protocolo SMTP
import smtplib

# MIMEText: clase para crear contenido de texto plano o HTML en correos
from email.mime.text import MIMEText

# MIMEMultipart: clase para crear correos con multiples partes (texto plano y HTML)
from email.mime.multipart import MIMEMultipart

# Celery: framework para procesamiento de tareas asincronas en segundo plano
from celery import Celery

# crontab: permite programar tareas periodicas con sintaxis similar a cron de Linux
from celery.schedules import crontab

# requests: biblioteca para realizar peticiones HTTP a otros servicios
import requests

# load_dotenv: carga variables de entorno desde un archivo .env
from dotenv import load_dotenv

# Firebase Admin SDK: para enviar push notifications via FCM
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Firebase Admin SDK not installed. Push notifications disabled.")

# ============================================================================
# CARGA DE VARIABLES DE ENTORNO
# ============================================================================

# Carga las variables de entorno desde el archivo .env en el directorio actual
# Esto permite configurar el sistema sin modificar el codigo fuente
load_dotenv()

# ============================================================================
# CONFIGURACION DE CELERY
# ============================================================================

# URL del broker de mensajes (Redis) - donde se encolan las tareas
# Por defecto usa Redis en localhost, puerto 6379, base de datos 9
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/9')

# URL del backend de resultados - donde se almacenan los resultados de las tareas
# Utiliza la misma instancia de Redis que el broker
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/9')

# Crea la instancia principal de la aplicacion Celery
# 'notification_worker' es el nombre identificador de esta aplicacion
# broker: URL donde Celery busca tareas pendientes
# backend: URL donde Celery almacena resultados de tareas completadas
app = Celery('notification_worker', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)

# Configuracion adicional de la aplicacion Celery
app.conf.update(
    # Formato de serializacion para las tareas: JSON para compatibilidad universal
    task_serializer='json',
    # Tipos de contenido aceptados: solo JSON por seguridad
    accept_content=['json'],
    # Formato de serializacion para los resultados: JSON
    result_serializer='json',
    # Zona horaria para programacion de tareas: Colombia
    timezone='America/Bogota',
    # Habilita UTC internamente para consistencia en calculos de tiempo
    enable_utc=True,
)

# ============================================================================
# CONFIGURACION DE CORREO ELECTRONICO (SMTP)
# ============================================================================

# Servidor SMTP para envio de correos (por defecto Gmail)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')

# Puerto del servidor SMTP (587 es el puerto estandar para TLS)
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))

# Usuario/cuenta de correo para autenticacion SMTP
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')

# Contrasena o token de aplicacion para autenticacion SMTP
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Indica si se debe usar TLS (cifrado) para la conexion SMTP
# Convierte el string a booleano comparando con 'true'
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'

# Direccion de correo que aparecera como remitente por defecto
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@legalflow.com')

# ============================================================================
# URLs DE SERVICIOS INTERNOS (MICROSERVICIOS)
# ============================================================================

# URL del servicio de calendario - gestiona eventos, plazos y audiencias
CALENDAR_SERVICE_URL = os.environ.get('CALENDAR_SERVICE_URL', 'http://localhost:8006')

# URL del servicio IAM (Identity Access Management) - gestiona usuarios y autenticacion
IAM_SERVICE_URL = os.environ.get('IAM_SERVICE_URL', 'http://localhost:8001')

# URL del servicio de casos/asuntos legales - gestiona expedientes y casos
MATTER_SERVICE_URL = os.environ.get('MATTER_SERVICE_URL', 'http://localhost:8002')

# URL del servicio de facturacion - gestiona facturas y pagos
BILLING_SERVICE_URL = os.environ.get('BILLING_SERVICE_URL', 'http://localhost:8005')

# URL del servicio del portal de clientes - interfaz para clientes externos
PORTAL_SERVICE_URL = os.environ.get('PORTAL_SERVICE_URL', 'http://localhost:8007')


# ============================================================================
# CONFIGURACION DE FIREBASE CLOUD MESSAGING (Push Notifications)
# ============================================================================

# Variable global para indicar si Firebase esta inicializado
FIREBASE_INITIALIZED = False

def initialize_firebase():
    """
    Inicializa Firebase Admin SDK para enviar push notifications.

    Soporta dos metodos de configuracion:
    1. FIREBASE_CREDENTIALS_JSON: JSON de credenciales en variable de entorno (recomendado para produccion)
    2. FIREBASE_CREDENTIALS_FILE: Ruta a archivo de credenciales JSON (para desarrollo local)

    Retorna:
        bool: True si la inicializacion fue exitosa, False en caso contrario
    """
    global FIREBASE_INITIALIZED

    if not FIREBASE_AVAILABLE:
        print("Firebase Admin SDK not available. Push notifications disabled.")
        return False

    if FIREBASE_INITIALIZED:
        return True

    try:
        # Opcion 1: Credenciales desde variable de entorno (JSON string)
        firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')

        # Opcion 2: Credenciales desde archivo
        firebase_creds_file = os.environ.get('FIREBASE_CREDENTIALS_FILE')

        if firebase_creds_json:
            # Parsea el JSON de credenciales desde la variable de entorno
            creds_dict = json.loads(firebase_creds_json)
            cred = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(cred)
            FIREBASE_INITIALIZED = True
            print("Firebase initialized from environment variable.")
            return True

        elif firebase_creds_file and os.path.exists(firebase_creds_file):
            # Carga credenciales desde archivo JSON
            cred = credentials.Certificate(firebase_creds_file)
            firebase_admin.initialize_app(cred)
            FIREBASE_INITIALIZED = True
            print(f"Firebase initialized from file: {firebase_creds_file}")
            return True

        else:
            print("Firebase credentials not configured. Push notifications disabled.")
            return False

    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        return False


# Intenta inicializar Firebase al cargar el modulo
initialize_firebase()


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def send_email(to_email, subject, body_html, body_text=None):
    """
    Envia un correo electronico utilizando el protocolo SMTP.

    Esta funcion es la base para todas las notificaciones por correo del sistema.
    Soporta envio de correos en formato HTML con version alternativa en texto plano.

    Parametros:
        to_email (str): Direccion de correo del destinatario
        subject (str): Asunto del correo
        body_html (str): Contenido del correo en formato HTML
        body_text (str, opcional): Contenido alternativo en texto plano

    Retorna:
        bool: True si el correo se envio exitosamente, False en caso contrario

    Notas:
        - Si no hay credenciales configuradas, imprime un mensaje de depuracion
        - Utiliza TLS si esta habilitado en la configuracion
        - Captura y registra cualquier excepcion durante el envio
    """
    # Verifica si las credenciales de correo estan configuradas
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        # Si no hay credenciales, imprime mensaje de depuracion y retorna False
        print(f"Email configuration missing. Would send to {to_email}: {subject}")
        return False

    try:
        # Crea un mensaje multipart que puede contener texto plano y HTML
        # 'alternative' indica que el cliente puede elegir cual version mostrar
        msg = MIMEMultipart('alternative')

        # Establece el asunto del correo
        msg['Subject'] = subject

        # Establece el remitente del correo
        msg['From'] = DEFAULT_FROM_EMAIL

        # Establece el destinatario del correo
        msg['To'] = to_email

        # Si se proporciono texto plano, lo adjunta como primera alternativa
        # Los clientes de correo mostraran HTML si lo soportan, sino texto plano
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))

        # Adjunta el contenido HTML como segunda alternativa (preferida)
        msg.attach(MIMEText(body_html, 'html'))

        # Establece conexion con el servidor SMTP usando context manager
        # El context manager asegura que la conexion se cierre correctamente
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            # Si TLS esta habilitado, inicia la conexion segura
            if EMAIL_USE_TLS:
                server.starttls()

            # Autentica con el servidor usando las credenciales configuradas
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)

            # Envia el mensaje al destinatario
            server.send_message(msg)

        # Retorna True indicando envio exitoso
        return True

    except Exception as e:
        # Captura cualquier error durante el envio y lo registra
        print(f"Error sending email: {str(e)}")
        # Retorna False indicando que el envio fallo
        return False


def get_user_fcm_tokens(user_id):
    """
    Obtiene los tokens FCM de todos los dispositivos activos de un usuario.

    Consulta al servicio IAM para obtener los tokens de dispositivos registrados.

    Parametros:
        user_id (str): UUID del usuario

    Retorna:
        list: Lista de tokens FCM activos del usuario
    """
    try:
        response = requests.get(
            f'{IAM_SERVICE_URL}/api/auth/users/{user_id}/devices/',
            timeout=10
        )
        if response.status_code == 200:
            devices = response.json()
            return [d['fcm_token'] for d in devices if d.get('is_active', True)]
    except Exception as e:
        print(f"Error getting FCM tokens for user {user_id}: {str(e)}")
    return []


def send_push_notification(fcm_token, title, body, data=None):
    """
    Envia una push notification a un dispositivo especifico.

    Parametros:
        fcm_token (str): Token FCM del dispositivo destino
        title (str): Titulo de la notificacion
        body (str): Contenido de la notificacion
        data (dict, opcional): Datos adicionales para la app

    Retorna:
        bool: True si el envio fue exitoso, False en caso contrario
    """
    if not FIREBASE_INITIALIZED or not FIREBASE_AVAILABLE:
        print(f"Push notification skipped (Firebase not initialized): {title}")
        return False

    try:
        # Construye el mensaje de FCM
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=fcm_token,
        )

        # Envia el mensaje
        response = messaging.send(message)
        print(f"Push notification sent successfully: {response}")
        return True

    except messaging.UnregisteredError:
        # Token invalido - el dispositivo ya no esta registrado
        print(f"FCM token unregistered: {fcm_token[:20]}...")
        # Aqui podriamos eliminar el token de la base de datos
        return False

    except Exception as e:
        print(f"Error sending push notification: {str(e)}")
        return False


def send_push_to_user(user_id, title, body, data=None):
    """
    Envia push notifications a todos los dispositivos de un usuario.

    Parametros:
        user_id (str): UUID del usuario
        title (str): Titulo de la notificacion
        body (str): Contenido de la notificacion
        data (dict, opcional): Datos adicionales para la app

    Retorna:
        int: Numero de notificaciones enviadas exitosamente
    """
    tokens = get_user_fcm_tokens(user_id)
    success_count = 0

    for token in tokens:
        if send_push_notification(token, title, body, data):
            success_count += 1

    return success_count


def send_push_to_multiple_users(user_ids, title, body, data=None):
    """
    Envia push notifications a multiples usuarios.

    Parametros:
        user_ids (list): Lista de UUIDs de usuarios
        title (str): Titulo de la notificacion
        body (str): Contenido de la notificacion
        data (dict, opcional): Datos adicionales para la app

    Retorna:
        int: Numero total de notificaciones enviadas exitosamente
    """
    total_success = 0
    for user_id in user_ids:
        total_success += send_push_to_user(user_id, title, body, data)
    return total_success


# ============================================================================
# TAREAS DE CELERY - PUSH NOTIFICATIONS
# ============================================================================

@app.task(name='send_push_notification_task')
def send_push_notification_task(user_id, title, body, data=None):
    """
    Tarea Celery para enviar push notification a un usuario.

    Parametros:
        user_id (str): UUID del usuario
        title (str): Titulo de la notificacion
        body (str): Contenido de la notificacion
        data (dict, opcional): Datos adicionales

    Retorna:
        dict: Resultado con el numero de notificaciones enviadas
    """
    success_count = send_push_to_user(user_id, title, body, data)
    return {'user_id': user_id, 'notifications_sent': success_count}


@app.task(name='send_push_to_multiple_task')
def send_push_to_multiple_task(user_ids, title, body, data=None):
    """
    Tarea Celery para enviar push notifications a multiples usuarios.

    Parametros:
        user_ids (list): Lista de UUIDs de usuarios
        title (str): Titulo de la notificacion
        body (str): Contenido de la notificacion
        data (dict, opcional): Datos adicionales

    Retorna:
        dict: Resultado con el total de notificaciones enviadas
    """
    total_success = send_push_to_multiple_users(user_ids, title, body, data)
    return {'users_count': len(user_ids), 'notifications_sent': total_success}


# ============================================================================
# TAREAS DE CELERY - NOTIFICACIONES DE PLAZOS
# ============================================================================

@app.task(name='send_deadline_reminder')
def send_deadline_reminder(deadline_id, user_email, deadline_title, due_date, case_number='', user_id=None):
    """
    Envia un correo recordatorio sobre un plazo legal proximo a vencer.

    Esta tarea se ejecuta de forma asincrona cuando se detecta un plazo
    que requiere atencion del usuario asignado.

    Parametros:
        deadline_id (int): Identificador unico del plazo en la base de datos
        user_email (str): Correo electronico del usuario asignado al plazo
        deadline_title (str): Titulo o descripcion del plazo
        due_date (str): Fecha de vencimiento del plazo
        case_number (str, opcional): Numero de radicado del caso asociado
        user_id (str, opcional): UUID del usuario para push notifications

    Retorna:
        dict: Resultado del envio (email y push)
    """
    # Construye el asunto del correo con prefijo identificador de LegalFlow
    subject = f"[LegalFlow] Recordatorio de Plazo: {deadline_title}"

    # Construye el cuerpo del correo en formato HTML con estilos basicos
    # Incluye informacion del plazo, fecha de vencimiento y caso asociado
    body_html = f"""
    <html>
    <body>
        <h2>Recordatorio de Plazo</h2>
        <p>Este es un recordatorio de que el siguiente plazo esta proximo a vencer:</p>
        <ul>
            <li><strong>Plazo:</strong> {deadline_title}</li>
            <li><strong>Fecha de vencimiento:</strong> {due_date}</li>
            {'<li><strong>Caso:</strong> ' + case_number + '</li>' if case_number else ''}
        </ul>
        <p>Por favor, tome las acciones necesarias.</p>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Version en texto plano para clientes de correo que no soportan HTML
    body_text = f"""
    Recordatorio de Plazo

    Plazo: {deadline_title}
    Fecha de vencimiento: {due_date}
    {'Caso: ' + case_number if case_number else ''}

    Por favor, tome las acciones necesarias.
    """

    # Envia el correo electronico
    email_sent = send_email(user_email, subject, body_html, body_text)

    # Envia push notification si se proporciono user_id
    push_sent = 0
    if user_id:
        push_body = f"Plazo: {deadline_title}\nVence: {due_date}"
        if case_number:
            push_body += f"\nCaso: {case_number}"
        push_sent = send_push_to_user(
            user_id,
            "Recordatorio de Plazo",
            push_body,
            {'type': 'deadline_reminder', 'deadline_id': str(deadline_id)}
        )

    return {'email_sent': email_sent, 'push_notifications_sent': push_sent}


# ============================================================================
# TAREAS DE CELERY - NOTIFICACIONES DE FACTURACION
# ============================================================================

@app.task(name='send_invoice_notification')
def send_invoice_notification(invoice_number, client_email, client_name, total_amount, due_date, action='created', client_user_id=None, invoice_id=None, balance_due=None):
    """
    Envia una notificacion por correo relacionada con una factura.

    Esta tarea maneja diferentes tipos de notificaciones de facturacion
    segun la accion especificada (creacion, envio, vencimiento, pago).

    Parametros:
        invoice_number (str): Numero identificador de la factura
        client_email (str): Correo electronico del cliente
        client_name (str): Nombre del cliente para personalizacion
        total_amount (float): Monto total de la factura
        due_date (str): Fecha de vencimiento de la factura
        action (str): Tipo de accion ('created', 'sent', 'overdue', 'paid')
        client_user_id (str, opcional): UUID del cliente para push notifications
        invoice_id (str, opcional): UUID de la factura para generar link de pago
        balance_due (float, opcional): Saldo pendiente de la factura

    Retorna:
        dict: Resultado del envio (email y push)
    """
    # Diccionario que mapea codigos de accion a textos legibles en espanol
    actions = {
        'created': 'Nueva Factura',      # Cuando se crea una nueva factura
        'sent': 'Factura Enviada',        # Cuando se envia la factura al cliente
        'overdue': 'Factura Vencida',     # Cuando la factura supera su fecha de pago
        'paid': 'Pago Recibido',          # Cuando se registra el pago de la factura
    }

    # Obtiene el texto de accion correspondiente, con valor por defecto
    action_text = actions.get(action, 'Notificacion de Factura')

    # Construye el asunto del correo con el tipo de accion y numero de factura
    subject = f"[LegalFlow] {action_text}: {invoice_number}"

    # URL del portal de clientes para el link de pago
    client_portal_url = os.environ.get('CLIENT_PORTAL_URL', 'http://localhost:5174')

    # Genera el boton de pago solo si hay saldo pendiente y no esta pagada
    payment_button_html = ''
    if action in ['sent', 'overdue'] and balance_due and balance_due > 0:
        payment_button_html = f"""
        <div style="text-align: center; margin: 30px 0;">
            <a href="{client_portal_url}/invoices?pay={invoice_id}"
               style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                Pagar Ahora - ${balance_due:,.0f}
            </a>
        </div>
        """

    # Mensaje especifico segun la accion
    message_html = ''
    if action == 'sent':
        message_html = '<p>Por favor, realice el pago antes de la fecha de vencimiento.</p>'
    elif action == 'overdue':
        message_html = '<p style="color: #dc2626;"><strong>IMPORTANTE:</strong> Esta factura se encuentra vencida. Por favor, realice el pago lo antes posible para evitar recargos.</p>'
    elif action == 'paid':
        message_html = '<p style="color: #16a34a;"><strong>¡Gracias por su pago!</strong> Su factura ha sido pagada en su totalidad.</p>'

    # Construye el cuerpo del correo en HTML con los detalles de la factura
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h2 style="color: #1e40af; margin: 0;">{action_text}</h2>
        </div>

        <p>Estimado/a {client_name},</p>
        <p>Le informamos sobre su factura:</p>

        <div style="background-color: #f1f5f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">Numero de factura:</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">{invoice_number}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">Monto total:</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">${total_amount:,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">Fecha de vencimiento:</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #e2e8f0; text-align: right;">{due_date}</td>
                </tr>
                {f'<tr><td style="padding: 8px 0;"><strong>Saldo pendiente:</strong></td><td style="padding: 8px 0; text-align: right; font-weight: bold; color: #dc2626;">${balance_due:,.0f}</td></tr>' if balance_due and balance_due > 0 else ''}
            </table>
        </div>

        {message_html}
        {payment_button_html}

        <p>Tambien puede acceder al portal de clientes para ver y pagar sus facturas:</p>
        <p><a href="{client_portal_url}/invoices" style="color: #2563eb;">Ver mis facturas</a></p>

        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
        <p style="color: #64748b; font-size: 12px;">Este es un mensaje automatico de LegalFlow. Por favor no responda a este correo.</p>
    </body>
    </html>
    """

    # Envia el correo electronico
    email_sent = send_email(client_email, subject, body_html)

    # Envia push notification si se proporciono client_user_id
    push_sent = 0
    if client_user_id:
        push_body = f"Factura: {invoice_number}\nMonto: ${total_amount:,.0f}\nVence: {due_date}"
        push_sent = send_push_to_user(
            client_user_id,
            action_text,
            push_body,
            {'type': 'invoice_notification', 'action': action, 'invoice_number': invoice_number, 'invoice_id': str(invoice_id) if invoice_id else None}
        )

    return {'email_sent': email_sent, 'push_notifications_sent': push_sent}


# ============================================================================
# TAREAS DE CELERY - ACTUALIZACIONES DE CASOS
# ============================================================================

@app.task(name='send_case_update')
def send_case_update(case_number, client_email, client_name, update_type, update_message, client_user_id=None):
    """
    Envia una notificacion de actualizacion sobre un caso legal.

    Notifica al cliente cuando hay cambios relevantes en su caso,
    como cambios de estado, nuevos documentos, o actuaciones procesales.

    Parametros:
        case_number (str): Numero de radicado del caso
        client_email (str): Correo electronico del cliente
        client_name (str): Nombre del cliente
        update_type (str): Tipo de actualizacion (ej: 'Estado', 'Documento')
        update_message (str): Descripcion detallada de la actualizacion
        client_user_id (str, opcional): UUID del cliente para push notifications

    Retorna:
        dict: Resultado del envio (email y push)
    """
    # Construye el asunto del correo con el numero de caso
    subject = f"[LegalFlow] Actualizacion de Caso: {case_number}"

    # Construye el cuerpo del correo con la informacion de la actualizacion
    body_html = f"""
    <html>
    <body>
        <h2>Actualizacion de Caso</h2>
        <p>Estimado/a {client_name},</p>
        <p>Hay una actualizacion en su caso <strong>{case_number}</strong>:</p>
        <p><strong>{update_type}:</strong> {update_message}</p>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Envia el correo electronico
    email_sent = send_email(client_email, subject, body_html)

    # Envia push notification si se proporciono client_user_id
    push_sent = 0
    if client_user_id:
        push_body = f"Caso: {case_number}\n{update_type}: {update_message}"
        push_sent = send_push_to_user(
            client_user_id,
            "Actualizacion de Caso",
            push_body,
            {'type': 'case_update', 'case_number': case_number, 'update_type': update_type}
        )

    return {'email_sent': email_sent, 'push_notifications_sent': push_sent}


@app.task(name='process_event_case_closed')
def process_event_case_closed(case_id, case_number, client_email, client_name):
    """
    Procesa el evento de cierre de un caso legal y notifica al cliente.

    Esta tarea se dispara automaticamente cuando un caso cambia su estado
    a 'cerrado' en el sistema, informando al cliente sobre la finalizacion.

    Parametros:
        case_id (int): Identificador unico del caso en la base de datos
        case_number (str): Numero de radicado del caso
        client_email (str): Correo electronico del cliente
        client_name (str): Nombre del cliente

    Retorna:
        bool: Resultado del envio del correo (True/False)
    """
    # Construye el asunto indicando el cierre del caso
    subject = f"[LegalFlow] Caso Cerrado: {case_number}"

    # Construye el cuerpo del correo informando sobre el cierre
    # Incluye invitacion a revisar detalles en el portal de clientes
    body_html = f"""
    <html>
    <body>
        <h2>Caso Cerrado</h2>
        <p>Estimado/a {client_name},</p>
        <p>Le informamos que su caso <strong>{case_number}</strong> ha sido cerrado.</p>
        <p>Puede acceder al portal de clientes para ver los detalles finales del caso.</p>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Envia la notificacion de cierre al cliente
    return send_email(client_email, subject, body_html)


# ============================================================================
# TAREAS DE CELERY - VERIFICACION PERIODICA DE PLAZOS
# ============================================================================

@app.task(name='check_upcoming_deadlines')
def check_upcoming_deadlines():
    """
    Verifica plazos proximos a vencer y envia recordatorios automaticos.

    Esta tarea periodica consulta el servicio de calendario para obtener
    todos los plazos que vencen en los proximos 3 dias. Para cada plazo
    encontrado, obtiene los datos del usuario asignado y programa el
    envio de un recordatorio.

    Esta tarea se ejecuta diariamente a las 8:00 AM (hora de Colombia)
    segun la configuracion de Celery Beat.

    Retorna:
        None: Esta tarea no retorna valor, pero programa tareas hijas

    Excepciones:
        Captura y registra cualquier error durante la ejecucion
    """
    try:
        # Consulta al servicio de calendario los plazos de los proximos 3 dias
        response = requests.get(f'{CALENDAR_SERVICE_URL}/api/deadlines/upcoming/?days=3')

        # Verifica que la respuesta sea exitosa (codigo 200)
        if response.status_code == 200:
            # Extrae la lista de plazos del JSON de respuesta
            deadlines = response.json().get('results', [])

            # Itera sobre cada plazo encontrado
            for deadline in deadlines:
                # Verifica si el plazo tiene un usuario asignado
                if deadline.get('assigned_to_id'):
                    # Consulta al servicio IAM para obtener datos del usuario
                    user_response = requests.get(
                        f'{IAM_SERVICE_URL}/api/auth/users/{deadline["assigned_to_id"]}/'
                    )

                    # Verifica que se obtuvo el usuario exitosamente
                    if user_response.status_code == 200:
                        # Extrae los datos del usuario del JSON
                        user = user_response.json()

                        # Programa el envio del recordatorio de forma asincrona
                        # .delay() encola la tarea para ejecucion en segundo plano
                        send_deadline_reminder.delay(
                            deadline['id'],              # ID del plazo
                            user.get('email'),           # Correo del usuario
                            deadline['title'],           # Titulo del plazo
                            deadline['due_date'],        # Fecha de vencimiento
                            deadline.get('case_number', '')  # Numero de caso (opcional)
                        )

    except Exception as e:
        # Registra cualquier error que ocurra durante la verificacion
        print(f"Error checking deadlines: {str(e)}")


# ============================================================================
# TAREAS DE CELERY - VERIFICACION PERIODICA DE FACTURAS VENCIDAS
# ============================================================================

@app.task(name='check_overdue_invoices')
def check_overdue_invoices():
    """
    Verifica facturas vencidas y envia recordatorios de pago.

    Esta tarea periodica consulta el servicio de facturacion para obtener
    todas las facturas con estado 'vencido'. Para cada factura encontrada,
    envia un recordatorio al cliente correspondiente.

    Esta tarea se ejecuta diariamente a las 9:00 AM (hora de Colombia)
    segun la configuracion de Celery Beat.

    Retorna:
        None: Esta tarea no retorna valor, pero programa tareas hijas

    Excepciones:
        Captura y registra cualquier error durante la ejecucion
    """
    try:
        # Consulta al servicio de facturacion las facturas vencidas
        response = requests.get(f'{BILLING_SERVICE_URL}/api/invoices/?status=overdue')

        # Verifica que la respuesta sea exitosa
        if response.status_code == 200:
            # Extrae la lista de facturas del JSON de respuesta
            invoices = response.json().get('results', [])

            # Itera sobre cada factura vencida
            for invoice in invoices:
                # Verifica si la factura tiene correo de cliente asociado
                if invoice.get('client_email'):
                    # Programa el envio de notificacion de factura vencida
                    # .delay() encola la tarea para ejecucion asincrona
                    send_invoice_notification.delay(
                        invoice['invoice_number'],            # Numero de factura
                        invoice['client_email'],              # Correo del cliente
                        invoice.get('client_name', 'Cliente'), # Nombre (con default)
                        invoice['total_amount'],              # Monto total
                        invoice['due_date'],                  # Fecha de vencimiento
                        'overdue'                             # Tipo: vencida
                    )

    except Exception as e:
        # Registra cualquier error durante la verificacion
        print(f"Error checking overdue invoices: {str(e)}")


# ============================================================================
# TAREAS DE CELERY - NOTIFICACIONES DE MENSAJES
# ============================================================================

@app.task(name='send_message_notification')
def send_message_notification(recipient_email, recipient_name, sender_name, subject, case_number='', recipient_user_id=None):
    """
    Envia una notificacion cuando se recibe un nuevo mensaje en el sistema.

    Notifica al usuario destinatario sobre mensajes nuevos en su bandeja
    de entrada de LegalFlow, incluyendo informacion del remitente y asunto.

    Parametros:
        recipient_email (str): Correo del destinatario del mensaje
        recipient_name (str): Nombre del destinatario
        sender_name (str): Nombre de quien envia el mensaje
        subject (str): Asunto del mensaje recibido
        case_number (str, opcional): Numero de caso relacionado
        recipient_user_id (str, opcional): UUID del destinatario para push notifications

    Retorna:
        dict: Resultado del envio (email y push)
    """
    # Construye el asunto del correo de notificacion
    email_subject = f"[LegalFlow] Nuevo mensaje de {sender_name}"

    # Construye el cuerpo del correo en HTML
    body_html = f"""
    <html>
    <body>
        <h2>Nuevo Mensaje</h2>
        <p>Estimado/a {recipient_name},</p>
        <p>Ha recibido un nuevo mensaje en LegalFlow:</p>
        <ul>
            <li><strong>De:</strong> {sender_name}</li>
            <li><strong>Asunto:</strong> {subject}</li>
            {'<li><strong>Caso:</strong> ' + case_number + '</li>' if case_number else ''}
        </ul>
        <p>Ingrese a LegalFlow para ver el mensaje completo.</p>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Version en texto plano del correo
    body_text = f"""
    Nuevo Mensaje

    Ha recibido un nuevo mensaje en LegalFlow:
    De: {sender_name}
    Asunto: {subject}
    {'Caso: ' + case_number if case_number else ''}

    Ingrese a LegalFlow para ver el mensaje completo.
    """

    # Envia el correo electronico
    email_sent = send_email(recipient_email, email_subject, body_html, body_text)

    # Envia push notification si se proporciono recipient_user_id
    push_sent = 0
    if recipient_user_id:
        push_body = f"De: {sender_name}\nAsunto: {subject}"
        if case_number:
            push_body += f"\nCaso: {case_number}"
        push_sent = send_push_to_user(
            recipient_user_id,
            "Nuevo Mensaje",
            push_body,
            {'type': 'message_notification', 'sender': sender_name}
        )

    return {'email_sent': email_sent, 'push_notifications_sent': push_sent}


# ============================================================================
# TAREAS DE CELERY - NOTIFICACIONES DE DOCUMENTOS COMPARTIDOS
# ============================================================================

@app.task(name='send_document_shared_notification')
def send_document_shared_notification(recipient_email, recipient_name, document_name, shared_by, case_number=''):
    """
    Envia una notificacion cuando un documento es compartido con un usuario.

    Notifica al destinatario que tiene acceso a un nuevo documento
    compartido en el sistema, incluyendo informacion del documento
    y quien lo compartio.

    Parametros:
        recipient_email (str): Correo del destinatario
        recipient_name (str): Nombre del destinatario
        document_name (str): Nombre del documento compartido
        shared_by (str): Nombre de quien compartio el documento
        case_number (str, opcional): Numero de caso relacionado

    Retorna:
        bool: Resultado del envio del correo (True/False)
    """
    # Construye el asunto del correo con el nombre del documento
    subject = f"[LegalFlow] Documento compartido: {document_name}"

    # Construye el cuerpo del correo con los detalles del documento
    body_html = f"""
    <html>
    <body>
        <h2>Documento Compartido</h2>
        <p>Estimado/a {recipient_name},</p>
        <p>{shared_by} ha compartido un documento con usted:</p>
        <ul>
            <li><strong>Documento:</strong> {document_name}</li>
            {'<li><strong>Caso:</strong> ' + case_number + '</li>' if case_number else ''}
        </ul>
        <p>Ingrese a LegalFlow para acceder al documento.</p>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Envia la notificacion al destinatario
    return send_email(recipient_email, subject, body_html)


# ============================================================================
# TAREAS DE CELERY - RECORDATORIOS DE EVENTOS
# ============================================================================

@app.task(name='send_event_reminder')
def send_event_reminder(event_id, user_email, event_title, event_datetime, location='', case_number='', user_id=None):
    """
    Envia un correo recordatorio sobre un evento proximo.

    Notifica al usuario sobre eventos del calendario como audiencias,
    reuniones, citas o cualquier otro compromiso programado.

    Parametros:
        event_id (int): Identificador unico del evento
        user_email (str): Correo del usuario asignado al evento
        event_title (str): Titulo o descripcion del evento
        event_datetime (str): Fecha y hora del evento
        location (str, opcional): Ubicacion donde se realizara el evento
        case_number (str, opcional): Numero de caso relacionado
        user_id (str, opcional): UUID del usuario para push notifications

    Retorna:
        dict: Resultado del envio (email y push)
    """
    # Construye el asunto del correo con el titulo del evento
    subject = f"[LegalFlow] Recordatorio de Evento: {event_title}"

    # Construye el cuerpo del correo en HTML con los detalles del evento
    # Incluye ubicacion y caso solo si estan disponibles
    body_html = f"""
    <html>
    <body>
        <h2>Recordatorio de Evento</h2>
        <p>Este es un recordatorio del siguiente evento:</p>
        <ul>
            <li><strong>Evento:</strong> {event_title}</li>
            <li><strong>Fecha y hora:</strong> {event_datetime}</li>
            {'<li><strong>Ubicacion:</strong> ' + location + '</li>' if location else ''}
            {'<li><strong>Caso:</strong> ' + case_number + '</li>' if case_number else ''}
        </ul>
        <hr>
        <p><small>Este es un mensaje automatico de LegalFlow.</small></p>
    </body>
    </html>
    """

    # Version en texto plano del recordatorio
    body_text = f"""
    Recordatorio de Evento

    Evento: {event_title}
    Fecha y hora: {event_datetime}
    {'Ubicacion: ' + location if location else ''}
    {'Caso: ' + case_number if case_number else ''}
    """

    # Envia el correo electronico
    email_sent = send_email(user_email, subject, body_html, body_text)

    # Envia push notification si se proporciono user_id
    push_sent = 0
    if user_id:
        push_body = f"{event_title}\nFecha: {event_datetime}"
        if location:
            push_body += f"\nUbicacion: {location}"
        push_sent = send_push_to_user(
            user_id,
            "Recordatorio de Evento",
            push_body,
            {'type': 'event_reminder', 'event_id': str(event_id)}
        )

    return {'email_sent': email_sent, 'push_notifications_sent': push_sent}


# ============================================================================
# TAREAS DE CELERY - VERIFICACION PERIODICA DE EVENTOS
# ============================================================================

@app.task(name='check_upcoming_events')
def check_upcoming_events():
    """
    Verifica eventos del dia y envia recordatorios automaticos.

    Esta tarea periodica consulta el servicio de calendario para obtener
    todos los eventos programados para el dia actual. Para cada evento
    encontrado con usuario asignado, programa el envio de un recordatorio.

    Esta tarea se ejecuta diariamente a las 7:30 AM (hora de Colombia)
    segun la configuracion de Celery Beat, permitiendo a los usuarios
    prepararse para sus compromisos del dia.

    Retorna:
        None: Esta tarea no retorna valor, pero programa tareas hijas

    Excepciones:
        Captura y registra cualquier error durante la ejecucion
    """
    try:
        # Consulta al servicio de calendario los eventos del dia actual
        response = requests.get(f'{CALENDAR_SERVICE_URL}/api/events/today/')

        # Verifica que la respuesta sea exitosa
        if response.status_code == 200:
            # Extrae la lista de eventos del JSON de respuesta
            events = response.json().get('results', [])

            # Itera sobre cada evento del dia
            for event in events:
                # Verifica si el evento tiene un usuario asignado
                if event.get('assigned_to_id'):
                    # Consulta al servicio IAM para obtener datos del usuario
                    user_response = requests.get(
                        f'{IAM_SERVICE_URL}/api/auth/users/{event["assigned_to_id"]}/'
                    )

                    # Verifica que se obtuvo el usuario exitosamente
                    if user_response.status_code == 200:
                        # Extrae los datos del usuario del JSON
                        user = user_response.json()

                        # Programa el envio del recordatorio de forma asincrona
                        send_event_reminder.delay(
                            event['id'],                    # ID del evento
                            user.get('email'),              # Correo del usuario
                            event['title'],                 # Titulo del evento
                            event['start_datetime'],        # Fecha y hora de inicio
                            event.get('location', ''),      # Ubicacion (opcional)
                            event.get('case_number', '')    # Numero de caso (opcional)
                        )

    except Exception as e:
        # Registra cualquier error durante la verificacion de eventos
        print(f"Error checking upcoming events: {str(e)}")


# ============================================================================
# CONFIGURACION DE CELERY BEAT - TAREAS PROGRAMADAS
# ============================================================================

# Configuracion del programador de tareas periodicas de Celery Beat
# Define las tareas que se ejecutan automaticamente segun un horario
app.conf.beat_schedule = {

    # Tarea: Verificacion diaria de plazos proximos a vencer
    # Se ejecuta todos los dias a las 8:00 AM hora de Colombia
    # Busca plazos que vencen en los proximos 3 dias y envia recordatorios
    'check-upcoming-deadlines-daily': {
        'task': 'check_upcoming_deadlines',          # Nombre de la tarea a ejecutar
        'schedule': crontab(hour=8, minute=0),       # Programacion: 8:00 AM diario
    },

    # Tarea: Verificacion diaria de facturas vencidas
    # Se ejecuta todos los dias a las 9:00 AM hora de Colombia
    # Busca facturas con estado 'overdue' y envia recordatorios de pago
    'check-overdue-invoices-daily': {
        'task': 'check_overdue_invoices',            # Nombre de la tarea a ejecutar
        'schedule': crontab(hour=9, minute=0),       # Programacion: 9:00 AM diario
    },

    # Tarea: Verificacion matutina de eventos del dia
    # Se ejecuta todos los dias a las 7:30 AM hora de Colombia
    # Envia recordatorios de todos los eventos programados para el dia actual
    'check-upcoming-events-morning': {
        'task': 'check_upcoming_events',             # Nombre de la tarea a ejecutar
        'schedule': crontab(hour=7, minute=30),      # Programacion: 7:30 AM diario
    },
}
