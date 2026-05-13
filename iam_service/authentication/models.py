"""
Modelos de autenticacion del servicio IAM.
Define el modelo de Usuario personalizado y el registro de actividades.

Incluye soporte para cifrado de campos sensibles (email, phone) usando AES-256-GCM.
"""

# Importacion de UUID para generar identificadores unicos
import uuid

# Importacion de clases base de Django para modelos de usuario personalizados
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Importacion del modulo de modelos de Django
from django.db import models

# Importacion de utilidades de cifrado
from .encryption import encrypt_field, decrypt_field, hash_for_lookup


class UserManager(BaseUserManager):
    """
    Gestor personalizado para el modelo de Usuario.
    Proporciona metodos para crear usuarios normales y superusuarios.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Crea y guarda un usuario normal con el email y contrasena proporcionados.

        Parametros:
            email (str): Direccion de correo electronico del usuario (requerido)
            password (str): Contrasena del usuario (opcional)
            **extra_fields: Campos adicionales como first_name, last_name, etc.

        Retorna:
            User: Instancia del usuario creado

        Lanza:
            ValueError: Si no se proporciona un email
        """
        # Validacion de que el email sea proporcionado
        if not email:
            raise ValueError('El email es requerido')

        # Normaliza el email (convierte el dominio a minusculas)
        email = self.normalize_email(email)

        # Crea la instancia del usuario con los campos proporcionados
        user = self.model(email=email, **extra_fields)

        # Establece la contrasena de forma segura (genera hash)
        user.set_password(password)

        # Guarda el usuario en la base de datos
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Crea y guarda un superusuario con privilegios de administrador.

        Parametros:
            email (str): Direccion de correo electronico del superusuario
            password (str): Contrasena del superusuario
            **extra_fields: Campos adicionales

        Retorna:
            User: Instancia del superusuario creado

        Lanza:
            ValueError: Si is_staff o is_superuser no son True
        """
        # Establece valores por defecto para superusuario
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')

        # Validaciones de seguridad para superusuarios
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')

        # Delega la creacion al metodo create_user
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de Usuario personalizado para el sistema LegalFlow.
    Utiliza email como identificador unico en lugar de username.
    Implementa control de acceso basado en roles (RBAC).
    """

    # Definicion de los roles disponibles en el sistema
    ROLE_CHOICES = [
        ('admin', 'Administrador'),      # Acceso total al sistema
        ('partner', 'Socio'),            # Socio del bufete, acceso amplio
        ('associate', 'Asociado'),       # Abogado asociado, acceso limitado
        ('paralegal', 'Paralegal'),      # Asistente legal, acceso restringido
        ('client', 'Cliente'),           # Cliente del bufete, solo portal de cliente
    ]

    # Identificador unico universal (UUID) como clave primaria
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Email como campo de identificacion unico
    email = models.EmailField(unique=True)

    # Nombre del usuario
    first_name = models.CharField(max_length=100)

    # Apellido del usuario
    last_name = models.CharField(max_length=100)

    # Rol del usuario que determina sus permisos
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='associate'
    )

    # Telefono de contacto (opcional)
    phone = models.CharField(max_length=20, blank=True)

    # ========================================================================
    # CAMPOS CIFRADOS (para datos sensibles)
    # Los campos originales (email, phone) se mantienen para compatibilidad
    # Los campos cifrados almacenan la version encriptada
    # Los campos hash permiten busquedas sin descifrar
    # ========================================================================

    # Email cifrado con AES-256-GCM
    email_encrypted = models.TextField(blank=True, null=True)

    # Hash del email para busquedas (SHA256)
    email_hash = models.CharField(max_length=64, blank=True, db_index=True)

    # Telefono cifrado con AES-256-GCM
    phone_encrypted = models.TextField(blank=True, null=True)

    # Hash del telefono para busquedas (SHA256)
    phone_hash = models.CharField(max_length=64, blank=True, db_index=True)

    # Indica si el usuario puede iniciar sesion
    is_active = models.BooleanField(default=True)

    # Indica si el usuario puede acceder al panel de administracion de Django
    is_staff = models.BooleanField(default=False)

    # Marca de tiempo de creacion del usuario
    created_at = models.DateTimeField(auto_now_add=True)

    # Marca de tiempo de ultima actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    # Fecha y hora del ultimo inicio de sesion
    last_login = models.DateTimeField(null=True, blank=True)

    # Asigna el gestor personalizado
    objects = UserManager()

    # Define el campo que se usara como nombre de usuario
    USERNAME_FIELD = 'email'

    # Campos requeridos adicionales al crear usuario por linea de comandos
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        """Metadatos del modelo User."""
        # Nombre de la tabla en la base de datos
        db_table = 'users'
        # Ordenamiento por defecto (mas recientes primero)
        ordering = ['-created_at']

    def __str__(self):
        """
        Representacion en cadena del usuario.
        Retorna el email y el rol del usuario.
        """
        return f"{self.email} ({self.get_role_display()})"

    @property
    def full_name(self):
        """
        Propiedad que retorna el nombre completo del usuario.
        Combina nombre y apellido.
        """
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe el metodo save para cifrar campos sensibles automaticamente.

        Al guardar el usuario, los campos email y phone se cifran y se generan
        los hashes correspondientes para permitir busquedas.
        """
        # Cifrar email si ha cambiado
        if self.email:
            self.email_encrypted = encrypt_field(self.email)
            self.email_hash = hash_for_lookup(self.email)

        # Cifrar telefono si existe
        if self.phone:
            self.phone_encrypted = encrypt_field(self.phone)
            self.phone_hash = hash_for_lookup(self.phone)

        super().save(*args, **kwargs)

    def get_decrypted_email(self) -> str:
        """
        Obtiene el email descifrado.

        Returns:
            str: Email descifrado o el email original si no hay version cifrada
        """
        if self.email_encrypted:
            return decrypt_field(self.email_encrypted)
        return self.email

    def get_decrypted_phone(self) -> str:
        """
        Obtiene el telefono descifrado.

        Returns:
            str: Telefono descifrado o el telefono original si no hay version cifrada
        """
        if self.phone_encrypted:
            return decrypt_field(self.phone_encrypted)
        return self.phone

    @classmethod
    def find_by_email_hash(cls, email: str):
        """
        Busca un usuario por email usando el hash (sin exponer el email real).

        Args:
            email: Email a buscar

        Returns:
            User: Usuario encontrado o None
        """
        email_hash = hash_for_lookup(email)
        return cls.objects.filter(email_hash=email_hash).first()

    def get_permissions_list(self):
        """
        Obtiene la lista de permisos del usuario basados en su rol.
        Incluye permisos a nivel de objeto si django-guardian esta configurado.

        Retorna:
            list: Lista de codigos de permisos asignados al usuario
        """
        # Importacion de RolePermission para obtener permisos basados en rol
        from permissions.models import RolePermission

        # Obtiene los permisos asociados al rol del usuario
        role_perms = RolePermission.objects.filter(
            role__name=self.role
        ).values_list('permission__codename', flat=True)

        # Retorna lista unica de permisos (sin duplicados)
        return list(set(role_perms))


class UserActivity(models.Model):
    """
    Modelo para registrar la actividad de los usuarios.
    Utilizado para auditoria y seguimiento de seguridad.
    Registra inicios de sesion, cierres de sesion, cambios de contrasena, etc.
    """

    # Tipos de acciones que se pueden registrar
    ACTION_CHOICES = [
        ('login', 'Inicio de sesion'),
        ('logout', 'Cierre de sesion'),
        ('login_failed', 'Intento de inicio de sesion fallido'),
        ('password_change', 'Cambio de contrasena'),
        ('profile_update', 'Actualizacion de perfil'),
    ]

    # Identificador unico del registro de actividad
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Usuario que realizo la accion
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )

    # Tipo de accion realizada
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # Direccion IP desde donde se realizo la accion
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Informacion del navegador/cliente del usuario
    user_agent = models.TextField(blank=True)

    # Momento en que se registro la actividad
    timestamp = models.DateTimeField(auto_now_add=True)

    # Detalles adicionales de la actividad en formato JSON
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        """Metadatos del modelo UserActivity."""
        # Nombre de la tabla en la base de datos
        db_table = 'user_activities'
        # Ordenamiento por defecto (mas recientes primero)
        ordering = ['-timestamp']
        # Nombre plural para el panel de administracion
        verbose_name_plural = 'User activities'

    def __str__(self):
        """
        Representacion en cadena del registro de actividad.
        Muestra el email del usuario, la accion y la fecha.
        """
        return f"{self.user.email} - {self.action} at {self.timestamp}"


class UserDevice(models.Model):
    """
    Modelo para registrar dispositivos moviles de usuarios.
    Permite enviar push notifications via Firebase Cloud Messaging (FCM).

    Cada usuario puede tener multiples dispositivos registrados (telefono, tablet, web).
    Los tokens FCM son unicos y se actualizan cuando el dispositivo renueva su token.
    """

    # Plataformas soportadas para push notifications
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]

    # Identificador unico del registro
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Usuario propietario del dispositivo
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='devices'
    )

    # Token FCM del dispositivo (proporcionado por Firebase SDK en el cliente)
    # Es unico porque un token solo puede pertenecer a un dispositivo
    fcm_token = models.CharField(max_length=500, unique=True)

    # Plataforma del dispositivo
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES
    )

    # Nombre o modelo del dispositivo (opcional, para identificacion)
    device_name = models.CharField(max_length=100, blank=True)

    # Identificador unico del dispositivo (device_id del cliente)
    # Permite identificar el mismo dispositivo aunque cambie el token FCM
    device_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Indica si el dispositivo esta activo para recibir notificaciones
    is_active = models.BooleanField(default=True)

    # Fecha de registro del dispositivo
    created_at = models.DateTimeField(auto_now_add=True)

    # Ultima actualizacion (ej: cuando se actualiza el token FCM)
    updated_at = models.DateTimeField(auto_now=True)

    # Ultima vez que se envio una notificacion exitosa
    last_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Metadatos del modelo UserDevice."""
        db_table = 'user_devices'
        ordering = ['-created_at']
        # Un usuario no puede tener el mismo device_id registrado multiples veces
        unique_together = [['user', 'device_id']]

    def __str__(self):
        """Representacion en cadena del dispositivo."""
        return f"{self.user.email} - {self.platform} ({self.device_name or 'Unknown'})"
