"""
===========================================================================================
ARCHIVO: models.py
MODULO: permissions (Servicio IAM - Identity and Access Management)
===========================================================================================

PROPOSITO:
Este archivo define los modelos de base de datos para el sistema de permisos del
servicio IAM. Implementa un sistema de control de acceso basado en roles (RBAC)
con soporte para permisos a nivel de objeto.

MODELOS DEFINIDOS:
- Role: Roles personalizados del sistema (mas alla de los roles basicos de User)
- Permission: Permisos granulares para diferentes tipos de recursos
- RolePermission: Relacion muchos a muchos entre roles y permisos
- ObjectPermission: Permisos a nivel de objeto para recursos especificos

ARQUITECTURA DE PERMISOS:
1. Permisos basados en Rol: Un usuario tiene un rol, y ese rol tiene permisos asociados
2. Permisos a nivel de Objeto: Un usuario puede tener permisos especificos sobre
   recursos individuales (ej: acceso a un caso especifico)

AUTOR: Equipo de Desarrollo LegalFlow
===========================================================================================
"""

# Importacion del modulo uuid para generar identificadores unicos universales
# UUID (Universally Unique Identifier) se usa como clave primaria para evitar
# conflictos en sistemas distribuidos y mejorar la seguridad
import uuid

# Importacion del modulo models de Django
# Este modulo proporciona las clases base para definir modelos de base de datos
from django.db import models


class Role(models.Model):
    """
    Modelo para roles personalizados del sistema.

    Este modelo permite definir roles adicionales mas alla de los roles basicos
    definidos en el campo User.role. Cada rol puede tener multiples permisos
    asociados a traves de la tabla intermedia RolePermission.

    Atributos:
        id (UUID): Identificador unico del rol (clave primaria)
        name (str): Nombre unico del rol (ej: 'Abogado Senior', 'Paralegal')
        description (str): Descripcion detallada del rol y sus responsabilidades
        is_system (bool): Indica si es un rol del sistema (no puede ser eliminado)
        created_at (datetime): Fecha y hora de creacion del rol
        updated_at (datetime): Fecha y hora de ultima actualizacion

    Relaciones:
        role_permissions: Relacion inversa a RolePermission (permisos del rol)
    """

    # Identificador unico usando UUID v4
    # primary_key=True: Este campo es la clave primaria de la tabla
    # default=uuid.uuid4: Genera automaticamente un nuevo UUID al crear el registro
    # editable=False: No se puede modificar despues de la creacion
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Nombre del rol (debe ser unico en todo el sistema)
    # max_length=50: Longitud maxima de 50 caracteres
    # unique=True: No puede haber dos roles con el mismo nombre
    name = models.CharField(max_length=50, unique=True)

    # Descripcion del rol
    # blank=True: El campo puede estar vacio en formularios
    description = models.TextField(blank=True)

    # Indicador de rol del sistema
    # Los roles del sistema (is_system=True) no pueden ser eliminados
    # Esto protege roles criticos como 'admin', 'abogado', 'cliente'
    is_system = models.BooleanField(default=False)

    # Fecha de creacion del registro
    # auto_now_add=True: Se establece automaticamente al crear el registro
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de ultima actualizacion
    # auto_now=True: Se actualiza automaticamente cada vez que se guarda el registro
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Clase Meta para configuracion adicional del modelo.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'roles'

        # Ordenamiento predeterminado de los registros (alfabetico por nombre)
        ordering = ['name']

    def __str__(self):
        """
        Representacion en cadena del rol.

        Este metodo se usa cuando se necesita convertir el objeto a string,
        por ejemplo en el admin de Django o en logs.

        Returns:
            str: Nombre del rol
        """
        return self.name


class Permission(models.Model):
    """
    Modelo para permisos granulares del sistema.

    Define permisos especificos que pueden ser asignados a roles o directamente
    a usuarios para objetos especificos. Cada permiso esta asociado a un tipo
    de contenido (recurso) del sistema.

    Atributos:
        id (UUID): Identificador unico del permiso
        codename (str): Codigo unico del permiso (ej: 'case.view', 'document.edit')
        name (str): Nombre legible del permiso
        description (str): Descripcion de lo que permite hacer el permiso
        content_type (str): Tipo de recurso al que aplica el permiso
        created_at (datetime): Fecha de creacion

    Relaciones:
        permission_roles: Relacion inversa a RolePermission (roles con este permiso)
    """

    # Opciones disponibles para el tipo de contenido
    # Cada tupla contiene: (valor_almacenado, etiqueta_mostrada)
    CONTENT_TYPE_CHOICES = [
        ('case', 'Caso'),                    # Permisos sobre casos legales
        ('document', 'Documento'),           # Permisos sobre documentos
        ('invoice', 'Factura'),              # Permisos sobre facturas
        ('time_entry', 'Entrada de Tiempo'), # Permisos sobre registros de tiempo
        ('event', 'Evento'),                 # Permisos sobre eventos del calendario
        ('deadline', 'Plazo'),               # Permisos sobre plazos/vencimientos
        ('user', 'Usuario'),                 # Permisos sobre usuarios
        ('report', 'Reporte'),               # Permisos sobre reportes
        ('client', 'Cliente'),               # Permisos sobre clientes
        ('message', 'Mensaje'),              # Permisos sobre mensajes/comunicaciones
    ]

    # Identificador unico del permiso
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Codigo unico del permiso
    # Se usa internamente para verificar permisos (ej: 'case.view', 'case.edit')
    # unique=True: Cada codigo debe ser unico en el sistema
    codename = models.CharField(max_length=100, unique=True)

    # Nombre descriptivo del permiso (para mostrar en interfaces)
    name = models.CharField(max_length=200)

    # Descripcion detallada de lo que permite hacer el permiso
    description = models.TextField(blank=True)

    # Tipo de contenido/recurso al que aplica el permiso
    # choices=CONTENT_TYPE_CHOICES: Restringe los valores permitidos
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPE_CHOICES)

    # Fecha de creacion del permiso
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Configuracion del modelo Permission.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'permissions'

        # Ordenamiento: primero por tipo de contenido, luego por codigo
        ordering = ['content_type', 'codename']

    def __str__(self):
        """
        Representacion en cadena del permiso.

        Formato: "tipo_contenido:codigo" (ej: "case:view")

        Returns:
            str: Representacion del permiso
        """
        return f"{self.content_type}:{self.codename}"


class RolePermission(models.Model):
    """
    Modelo de relacion muchos a muchos entre roles y permisos.

    Esta tabla intermedia conecta roles con permisos, permitiendo que:
    - Un rol tenga multiples permisos
    - Un permiso pueda estar asignado a multiples roles

    Atributos:
        id (UUID): Identificador unico de la relacion
        role (FK): Referencia al rol
        permission (FK): Referencia al permiso
        created_at (datetime): Fecha en que se asigno el permiso al rol
    """

    # Identificador unico de la relacion
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Clave foranea al rol
    # on_delete=models.CASCADE: Si se elimina el rol, se eliminan sus permisos asociados
    # related_name='role_permissions': Nombre para acceder desde Role (role.role_permissions.all())
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')

    # Clave foranea al permiso
    # related_name='permission_roles': Nombre para acceder desde Permission
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='permission_roles')

    # Fecha en que se creo la asignacion
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Configuracion del modelo RolePermission.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'role_permissions'

        # Restriccion de unicidad compuesta
        # No puede existir la misma combinacion rol-permiso dos veces
        unique_together = ['role', 'permission']

    def __str__(self):
        """
        Representacion en cadena de la relacion rol-permiso.

        Returns:
            str: "NombreRol - CodigoPermiso"
        """
        return f"{self.role.name} - {self.permission.codename}"


class ObjectPermission(models.Model):
    """
    Modelo para permisos a nivel de objeto especifico.

    Permite asignar permisos a usuarios sobre recursos individuales,
    complementando el sistema de permisos basado en roles. Por ejemplo,
    un usuario puede tener acceso a un caso especifico sin tener acceso
    a todos los casos del sistema.

    Este modelo trabaja en conjunto con django-guardian para verificaciones
    de permisos entre microservicios.

    Atributos:
        id (UUID): Identificador unico del permiso de objeto
        user_id (UUID): ID del usuario que tiene el permiso
        permission (FK): Referencia al permiso otorgado
        object_type (str): Tipo de objeto (ej: 'case', 'document')
        object_id (UUID): ID del objeto especifico
        granted_by_id (UUID): ID del usuario que otorgo el permiso
        created_at (datetime): Fecha en que se otorgo el permiso
    """

    # Identificador unico del registro
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ID del usuario que tiene el permiso
    # Se almacena como UUID en lugar de ForeignKey porque el usuario
    # puede estar en otro microservicio (servicio de autenticacion)
    # db_index=True: Crea un indice para busquedas rapidas por usuario
    user_id = models.UUIDField(db_index=True)

    # Clave foranea al permiso otorgado
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    # Tipo de objeto sobre el que se otorga el permiso
    # Ejemplos: 'case', 'document', 'invoice'
    object_type = models.CharField(max_length=50)

    # ID del objeto especifico sobre el que se tiene el permiso
    # db_index=True: Indice para busquedas rapidas por objeto
    object_id = models.UUIDField(db_index=True)

    # ID del usuario que otorgo este permiso (para auditoria)
    # null=True, blank=True: Puede estar vacio (permisos automaticos del sistema)
    granted_by_id = models.UUIDField(null=True, blank=True)

    # Fecha en que se creo el permiso
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Configuracion del modelo ObjectPermission.
        """
        # Nombre de la tabla en la base de datos
        db_table = 'object_permissions'

        # Restriccion de unicidad compuesta
        # Un usuario solo puede tener un permiso especifico sobre un objeto especifico una vez
        unique_together = ['user_id', 'permission', 'object_type', 'object_id']

        # Indices adicionales para optimizar consultas frecuentes
        indexes = [
            # Indice compuesto para busquedas por usuario, tipo de objeto y objeto
            models.Index(fields=['user_id', 'object_type', 'object_id']),
        ]

    def __str__(self):
        """
        Representacion en cadena del permiso de objeto.

        Returns:
            str: Descripcion del permiso de objeto
        """
        return f"User {self.user_id} - {self.permission.codename} on {self.object_type}:{self.object_id}"


class FieldPermission(models.Model):
    """
    Modelo para permisos a nivel de campo.

    Permite controlar el acceso a campos especificos de un modelo,
    por ejemplo, permitir que ciertos roles vean el email pero no
    el telefono de un usuario.

    Atributos:
        id (UUID): Identificador unico del permiso de campo
        role (FK): Rol al que aplica el permiso
        content_type (str): Tipo de objeto (ej: 'user', 'client')
        field_name (str): Nombre del campo (ej: 'email', 'phone')
        can_read (bool): Permiso de lectura del campo
        can_write (bool): Permiso de escritura del campo
        created_at (datetime): Fecha de creacion

    Uso:
        # Verificar si un rol puede leer el email de un usuario
        can_read = FieldPermission.objects.filter(
            role__name='paralegal',
            content_type='user',
            field_name='email',
            can_read=True
        ).exists()
    """

    # Opciones de tipos de contenido (modelos) que tienen campos protegidos
    CONTENT_TYPE_CHOICES = [
        ('user', 'Usuario'),
        ('client', 'Cliente'),
        ('case', 'Caso'),
        ('invoice', 'Factura'),
        ('document', 'Documento'),
    ]

    # Campos comunes que pueden ser protegidos
    FIELD_CHOICES = [
        # Campos de Usuario
        ('email', 'Correo Electronico'),
        ('phone', 'Telefono'),
        ('address', 'Direccion'),
        ('tax_id', 'Identificacion Fiscal'),
        ('bank_account', 'Cuenta Bancaria'),
        ('salary', 'Salario'),
        # Campos de Cliente
        ('contact_info', 'Informacion de Contacto'),
        ('billing_info', 'Informacion de Facturacion'),
        # Campos de Caso
        ('sensitive_notes', 'Notas Sensibles'),
        ('financial_details', 'Detalles Financieros'),
    ]

    # Identificador unico del permiso
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Rol al que aplica el permiso de campo
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='field_permissions'
    )

    # Tipo de objeto/modelo que contiene el campo
    content_type = models.CharField(
        max_length=50,
        choices=CONTENT_TYPE_CHOICES
    )

    # Nombre del campo protegido
    field_name = models.CharField(max_length=100)

    # Permiso de lectura del campo
    can_read = models.BooleanField(default=False)

    # Permiso de escritura del campo
    can_write = models.BooleanField(default=False)

    # Fecha de creacion
    created_at = models.DateTimeField(auto_now_add=True)

    # Fecha de actualizacion
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Configuracion del modelo FieldPermission."""
        db_table = 'field_permissions'

        # Un rol solo puede tener un permiso por cada campo de cada tipo
        unique_together = ['role', 'content_type', 'field_name']

        # Ordenamiento
        ordering = ['content_type', 'field_name', 'role__name']

    def __str__(self):
        """Representacion en cadena del permiso de campo."""
        perms = []
        if self.can_read:
            perms.append('read')
        if self.can_write:
            perms.append('write')
        perm_str = '+'.join(perms) if perms else 'none'
        return f"{self.role.name}: {self.content_type}.{self.field_name} ({perm_str})"

    @classmethod
    def check_field_permission(cls, role_name: str, content_type: str,
                                field_name: str, action: str = 'read') -> bool:
        """
        Verifica si un rol tiene permiso sobre un campo.

        Args:
            role_name: Nombre del rol a verificar
            content_type: Tipo de objeto (ej: 'user')
            field_name: Nombre del campo (ej: 'email')
            action: 'read' o 'write'

        Returns:
            bool: True si tiene permiso, False en caso contrario
        """
        try:
            permission = cls.objects.get(
                role__name=role_name,
                content_type=content_type,
                field_name=field_name
            )
            if action == 'read':
                return permission.can_read
            elif action == 'write':
                return permission.can_write
            return False
        except cls.DoesNotExist:
            # Si no hay permiso definido, permitir por defecto para admin
            return role_name == 'admin'

    @classmethod
    def get_readable_fields(cls, role_name: str, content_type: str) -> list:
        """
        Obtiene la lista de campos que un rol puede leer.

        Args:
            role_name: Nombre del rol
            content_type: Tipo de objeto

        Returns:
            list: Lista de nombres de campos con permiso de lectura
        """
        return list(cls.objects.filter(
            role__name=role_name,
            content_type=content_type,
            can_read=True
        ).values_list('field_name', flat=True))

    @classmethod
    def get_writable_fields(cls, role_name: str, content_type: str) -> list:
        """
        Obtiene la lista de campos que un rol puede escribir.

        Args:
            role_name: Nombre del rol
            content_type: Tipo de objeto

        Returns:
            list: Lista de nombres de campos con permiso de escritura
        """
        return list(cls.objects.filter(
            role__name=role_name,
            content_type=content_type,
            can_write=True
        ).values_list('field_name', flat=True))
