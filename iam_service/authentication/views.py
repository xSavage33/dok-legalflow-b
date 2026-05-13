"""
Vistas de autenticacion del servicio IAM.
Proporciona endpoints para registro, login, logout, gestion de perfil y usuarios.
"""

# Importaciones de Django REST Framework
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

# Importaciones para manejo de tokens JWT
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

# Utilidades de Django para manejo de fechas
from django.utils import timezone

# Modelos locales de autenticacion
from .models import User, UserActivity, UserDevice

# Serializadores para validacion y transformacion de datos
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    PasswordChangeSerializer,
    UserListSerializer,
    UserCreateSerializer,
    UserAdminUpdateSerializer,
    UserActivitySerializer,
    UserDeviceSerializer,
    UserDeviceRegisterSerializer,
    UserDeviceUpdateSerializer,
)


def get_tokens_for_user(user):
    """
    Genera tokens JWT personalizados para un usuario.
    Incluye claims adicionales como el rol y email del usuario.

    Parametros:
        user (User): Instancia del usuario para quien se generan los tokens

    Retorna:
        dict: Diccionario con tokens 'refresh' y 'access'
    """
    # Genera el token de refresco para el usuario
    refresh = RefreshToken.for_user(user)

    # Agrega claims personalizados al token de refresco
    refresh['role'] = user.role
    refresh['email'] = user.email

    # Agrega claims personalizados al token de acceso
    refresh.access_token['role'] = user.role
    refresh.access_token['email'] = user.email

    # Retorna ambos tokens como cadenas de texto
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def get_client_ip(request):
    """
    Obtiene la direccion IP real del cliente desde la solicitud HTTP.
    Maneja casos donde la solicitud pasa por proxies o balanceadores de carga.

    Parametros:
        request: Objeto de solicitud HTTP de Django

    Retorna:
        str: Direccion IP del cliente
    """
    # Intenta obtener la IP del header X-Forwarded-For (usado por proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        # Si hay multiples IPs, toma la primera (IP real del cliente)
        ip = x_forwarded_for.split(',')[0]
    else:
        # Si no hay proxy, usa REMOTE_ADDR directamente
        ip = request.META.get('REMOTE_ADDR')

    return ip


def log_activity(user, action, request, details=None):
    """
    Registra una actividad del usuario para propositos de auditoria.

    Parametros:
        user (User): Usuario que realiza la accion
        action (str): Tipo de accion (login, logout, etc.)
        request: Objeto de solicitud HTTP
        details (dict, opcional): Informacion adicional sobre la accion
    """
    # Crea un nuevo registro de actividad en la base de datos
    UserActivity.objects.create(
        user=user,
        action=action,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        details=details or {}
    )


class RegisterView(generics.CreateAPIView):
    """
    Vista para el registro de nuevos usuarios.
    Endpoint publico que permite crear cuentas de usuario.
    POST /api/auth/register/
    """

    # Conjunto de datos base para la vista
    queryset = User.objects.all()

    # Permite acceso sin autenticacion (registro publico)
    permission_classes = [permissions.AllowAny]

    # Serializador para validar los datos de registro
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        """
        Procesa la solicitud de registro de un nuevo usuario.

        Parametros:
            request: Solicitud HTTP con datos del usuario

        Retorna:
            Response: Datos del usuario creado y tokens JWT
        """
        # Valida los datos de entrada usando el serializador
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Crea el usuario en la base de datos
        user = serializer.save()

        # Retorna respuesta exitosa con datos del usuario y tokens
        return Response({
            'message': 'Usuario registrado exitosamente.',
            'user': UserSerializer(user).data,
            'tokens': get_tokens_for_user(user)
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    Vista para el inicio de sesion de usuarios.
    Endpoint publico que autentica credenciales y retorna tokens JWT.
    POST /api/auth/login/
    """

    # Permite acceso sin autenticacion
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Procesa la solicitud de inicio de sesion.

        Parametros:
            request: Solicitud HTTP con email y contrasena

        Retorna:
            Response: Datos del usuario y tokens JWT si es exitoso
                      Error 401 si las credenciales son invalidas
        """
        # Valida las credenciales usando el serializador
        serializer = UserLoginSerializer(data=request.data)

        if not serializer.is_valid():
            # Registra el intento fallido de inicio de sesion
            email = request.data.get('email')
            if email:
                try:
                    # Busca el usuario para registrar el intento fallido
                    user = User.objects.get(email=email)
                    log_activity(user, 'login_failed', request)
                except User.DoesNotExist:
                    # Usuario no existe, no se registra actividad
                    pass

            # Retorna error de autenticacion
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        # Obtiene el usuario autenticado del serializador
        user = serializer.validated_data['user']

        # Actualiza la fecha de ultimo inicio de sesion
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Registra el inicio de sesion exitoso
        log_activity(user, 'login', request)

        # Retorna respuesta exitosa con datos y tokens
        return Response({
            'message': 'Login exitoso.',
            'user': UserSerializer(user).data,
            'tokens': get_tokens_for_user(user)
        })


class LogoutView(APIView):
    """
    Vista para el cierre de sesion de usuarios.
    Invalida el token de refresco para prevenir su uso futuro.
    POST /api/auth/logout/
    """

    def post(self, request):
        """
        Procesa la solicitud de cierre de sesion.

        Parametros:
            request: Solicitud HTTP con token de refresco

        Retorna:
            Response: Mensaje de confirmacion
        """
        try:
            # Obtiene el token de refresco del cuerpo de la solicitud
            refresh_token = request.data.get('refresh')

            if refresh_token:
                # Crea objeto de token y lo agrega a la lista negra
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Registra el cierre de sesion
            log_activity(request.user, 'logout', request)

            return Response({'message': 'Logout exitoso.'})

        except Exception:
            # Incluso si hay error, retornamos exito (el usuario quiere salir)
            return Response({'message': 'Logout exitoso.'})


class TokenRefreshCustomView(TokenRefreshView):
    """
    Vista personalizada para refrescar tokens JWT.
    Extiende la vista base para agregar funcionalidad adicional si es necesario.
    POST /api/auth/token/refresh/
    """
    pass


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Vista para ver y actualizar el perfil del usuario autenticado.
    GET /api/auth/profile/ - Obtiene datos del perfil
    PUT/PATCH /api/auth/profile/ - Actualiza datos del perfil
    """

    # Serializador por defecto para lectura
    serializer_class = UserSerializer

    def get_object(self):
        """
        Obtiene el objeto de usuario actual.
        Retorna el usuario autenticado que hace la solicitud.
        """
        return self.request.user

    def get_serializer_class(self):
        """
        Selecciona el serializador apropiado segun el metodo HTTP.
        Usa serializador de actualizacion para PUT/PATCH.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        """
        Actualiza el perfil y registra la actividad.
        """
        # Ejecuta la actualizacion usando el metodo padre
        response = super().update(request, *args, **kwargs)

        # Registra la actualizacion del perfil
        log_activity(request.user, 'profile_update', request)

        return response


class PasswordChangeView(APIView):
    """
    Vista para cambiar la contrasena del usuario autenticado.
    POST /api/auth/password/change/
    """

    def post(self, request):
        """
        Procesa la solicitud de cambio de contrasena.

        Parametros:
            request: Solicitud con contrasena actual y nueva

        Retorna:
            Response: Mensaje de confirmacion
        """
        # Valida las contrasenas usando el serializador
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # Establece la nueva contrasena
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        # Registra el cambio de contrasena
        log_activity(request.user, 'password_change', request)

        return Response({'message': 'Contrasena actualizada exitosamente.'})


class UserListView(generics.ListCreateAPIView):
    """
    Vista para listar y crear usuarios (solo administradores).
    GET /api/auth/users/ - Lista usuarios con filtros opcionales
    POST /api/auth/users/ - Crea un nuevo usuario
    """

    # Conjunto base de usuarios
    queryset = User.objects.all()

    def get_serializer_class(self):
        """
        Selecciona el serializador segun el metodo HTTP.
        """
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserListSerializer

    def get_queryset(self):
        """
        Filtra la lista de usuarios segun parametros de consulta.
        Soporta filtros por rol, estado activo y busqueda por texto.
        """
        queryset = super().get_queryset()

        # Filtro por rol del usuario
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        # Filtro por estado activo/inactivo
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Busqueda por nombre o email
        search = self.request.query_params.get('search')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        # Ordena por fecha de creacion descendente
        return queryset.order_by('-created_at')


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar usuarios especificos.
    GET /api/auth/users/{id}/ - Obtiene datos de un usuario
    PUT/PATCH /api/auth/users/{id}/ - Actualiza un usuario
    DELETE /api/auth/users/{id}/ - Desactiva un usuario (soft delete)
    """

    # Conjunto base de usuarios
    queryset = User.objects.all()

    # Serializador por defecto
    serializer_class = UserSerializer

    # Campo usado para buscar el usuario en la URL
    lookup_field = 'id'

    def get_serializer_class(self):
        """
        Selecciona el serializador segun el metodo HTTP.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return UserAdminUpdateSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Desactiva un usuario en lugar de eliminarlo fisicamente.
        Implementa "soft delete" para mantener integridad de datos.
        """
        # Obtiene el usuario a desactivar
        user = self.get_object()

        # Marca el usuario como inactivo
        user.is_active = False
        user.save()

        return Response({'message': 'Usuario desactivado exitosamente.'})


class UserActivityListView(generics.ListAPIView):
    """
    Vista para listar las actividades del usuario autenticado.
    GET /api/auth/activities/
    Muestra las ultimas 50 actividades para auditoria personal.
    """

    # Serializador para las actividades
    serializer_class = UserActivitySerializer

    def get_queryset(self):
        """
        Obtiene las actividades del usuario actual.
        Limitado a las 50 mas recientes.
        """
        return UserActivity.objects.filter(user=self.request.user)[:50]


class ValidateTokenView(APIView):
    """
    Vista para validar tokens JWT desde otros microservicios.
    GET /api/auth/validate/
    Usado por el API Gateway y otros servicios para verificar autenticacion.
    """

    def get(self, request):
        """
        Valida el token y retorna informacion del usuario.

        Retorna:
            Response: Estado de validacion y datos del usuario
        """
        return Response({
            'valid': True,
            'user': UserSerializer(request.user).data
        })


# =============================================================================
# VISTAS DE GESTION DE DISPOSITIVOS (Push Notifications)
# =============================================================================


class DeviceRegisterView(APIView):
    """
    Vista para registrar dispositivos para push notifications.
    POST /api/auth/devices/register/
    Registra o actualiza el token FCM de un dispositivo.
    """

    def post(self, request):
        """
        Registra un dispositivo para recibir push notifications.

        Parametros:
            request: Solicitud HTTP con fcm_token, platform, device_name (opcional), device_id (opcional)

        Retorna:
            Response: Datos del dispositivo registrado
        """
        serializer = UserDeviceRegisterSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        device = serializer.save()

        return Response({
            'message': 'Dispositivo registrado exitosamente.',
            'device': UserDeviceSerializer(device).data
        }, status=status.HTTP_201_CREATED)


class DeviceListView(generics.ListAPIView):
    """
    Vista para listar los dispositivos del usuario autenticado.
    GET /api/auth/devices/
    Muestra todos los dispositivos activos registrados.
    """

    serializer_class = UserDeviceSerializer

    def get_queryset(self):
        """
        Obtiene los dispositivos del usuario actual.
        Solo retorna dispositivos activos.
        """
        return UserDevice.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-created_at')


class DeviceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar dispositivos especificos.
    GET /api/auth/devices/{id}/ - Obtiene datos de un dispositivo
    PATCH /api/auth/devices/{id}/ - Actualiza un dispositivo
    DELETE /api/auth/devices/{id}/ - Elimina un dispositivo
    """

    serializer_class = UserDeviceSerializer
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filtra dispositivos por el usuario autenticado.
        """
        return UserDevice.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """
        Selecciona el serializador segun el metodo HTTP.
        """
        if self.request.method in ['PUT', 'PATCH']:
            return UserDeviceUpdateSerializer
        return UserDeviceSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Elimina un dispositivo (hard delete).
        """
        device = self.get_object()
        device.delete()
        return Response({'message': 'Dispositivo eliminado exitosamente.'}, status=status.HTTP_204_NO_CONTENT)


class DeviceUnregisterView(APIView):
    """
    Vista para desregistrar un dispositivo por su token FCM.
    POST /api/auth/devices/unregister/
    Util cuando el usuario cierra sesion desde un dispositivo.
    """

    # Permite acceso sin autenticacion (para casos de logout)
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Desregistra un dispositivo usando su token FCM.

        Parametros:
            request: Solicitud HTTP con fcm_token

        Retorna:
            Response: Mensaje de confirmacion
        """
        fcm_token = request.data.get('fcm_token')

        if not fcm_token:
            return Response(
                {'error': 'fcm_token es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Busca y elimina el dispositivo por token
        deleted_count, _ = UserDevice.objects.filter(fcm_token=fcm_token).delete()

        if deleted_count > 0:
            return Response({'message': 'Dispositivo desregistrado exitosamente.'})
        else:
            return Response({'message': 'Dispositivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
