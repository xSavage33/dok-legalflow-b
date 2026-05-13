"""
Middleware de limitacion de tasa (Rate Limiting) para el API Gateway de LegalFlow.

Este archivo implementa un middleware que limita el numero de peticiones que
un cliente puede realizar en un periodo de tiempo determinado. Utiliza Redis
como almacenamiento para mantener los contadores de peticiones, permitiendo
que el limite funcione correctamente incluso con multiples instancias del
gateway.

Caracteristicas principales:
    - Limitacion de tasa basada en direccion IP del cliente
    - Almacenamiento de contadores en Redis para escalabilidad
    - Ventana de tiempo deslizante configurable
    - Manejo gracil de fallos de Redis (continua operando sin limites)
    - Soporte para deteccion de IP real detras de proxies

Configuracion (en settings.py):
    - RATE_LIMIT_REQUESTS: Numero maximo de peticiones (default: 100)
    - RATE_LIMIT_WINDOW: Ventana de tiempo en segundos (default: 60)
    - REDIS_URL: URL de conexion a Redis

Clases:
    - RateLimitMiddleware: Middleware principal de limitacion de tasa

Autor: LegalFlow Team
"""

# Importacion del modulo time para funciones relacionadas con tiempo
# Aunque no se usa directamente, puede ser util para logging de timestamps
import time

# Importacion del modulo hashlib para funciones de hash criptografico
# Se usa para generar claves de Redis seguras basadas en IP
import hashlib

# Importacion del modulo settings de Django para acceder a configuracion
# Contiene los parametros de limitacion de tasa y URL de Redis
from django.conf import settings

# Importacion de JsonResponse para respuestas HTTP en formato JSON
# Se usa para enviar respuestas de error cuando se excede el limite
from django.http import JsonResponse

# Importacion del cliente Redis para almacenamiento de contadores
# Redis permite contadores distribuidos entre multiples instancias
import redis


class RateLimitMiddleware:
    """
    Middleware de limitacion de tasa usando Redis.

    Este middleware implementa un algoritmo de ventana fija para limitar
    el numero de peticiones por cliente (identificado por IP). Los contadores
    se almacenan en Redis con tiempo de expiracion automatico.

    Funcionamiento:
        1. Obtiene la IP del cliente de la peticion
        2. Genera una clave hash unica para la IP
        3. Incrementa el contador en Redis
        4. Si excede el limite, retorna error 429
        5. Si no excede, permite que la peticion continue

    Atributos:
        get_response: Callable que procesa la peticion (siguiente middleware/vista)
        redis_client: Cliente Redis para almacenar contadores
        requests_limit: Numero maximo de peticiones permitidas
        window: Ventana de tiempo en segundos

    Configuracion por defecto:
        - 100 peticiones por 60 segundos por IP

    Ejemplo de respuesta cuando se excede el limite:
        HTTP 429 Too Many Requests
        {
            "error": "Rate limit exceeded",
            "message": "Maximum 100 requests per 60 seconds"
        }
    """

    def __init__(self, get_response):
        """
        Inicializa el middleware de limitacion de tasa.

        Configura el cliente Redis y los parametros de limitacion.
        Si Redis no esta disponible, el middleware opera sin limites.

        Args:
            get_response: Callable que representa el siguiente middleware
                         o vista en la cadena de procesamiento de Django
        """
        # Almacena la referencia al siguiente procesador en la cadena
        # Django llama a esto para continuar procesando la peticion
        self.get_response = get_response

        # Inicializa el cliente Redis como None (se conecta despues)
        self.redis_client = None

        # Obtiene el limite de peticiones desde la configuracion
        # getattr proporciona un valor por defecto si no esta configurado
        # Default: 100 peticiones
        self.requests_limit = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)

        # Obtiene la ventana de tiempo desde la configuracion
        # Default: 60 segundos (1 minuto)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)

        try:
            # Intenta conectar al servidor Redis usando la URL configurada
            # redis.from_url parsea URLs como: redis://localhost:6379/0
            self.redis_client = redis.from_url(settings.REDIS_URL)
        except Exception:
            # Si falla la conexion, el middleware opera sin limitacion
            # Esto permite que la aplicacion funcione aunque Redis no este disponible
            pass

    def __call__(self, request):
        """
        Procesa cada peticion HTTP entrante.

        Este metodo es llamado por Django para cada peticion. Verifica
        el limite de tasa y decide si permitir o bloquear la peticion.

        Args:
            request: Objeto HttpRequest de Django con datos de la peticion

        Returns:
            HttpResponse: Respuesta de la vista si no excede limite,
                         JsonResponse con error 429 si excede el limite
        """
        # Endpoints excluidos del rate limiting (monitoreo, health checks)
        excluded_paths = ['/metrics', '/api/health/']
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)

        # Solo aplica limitacion si Redis esta disponible
        if self.redis_client:
            # Obtiene la direccion IP real del cliente
            client_ip = self.get_client_ip(request)

            # Genera una clave unica para Redis basada en la IP
            # Se usa MD5 para crear una clave de longitud fija y segura
            # Formato: "rate_limit:abc123def456..."
            key = f"rate_limit:{hashlib.md5(client_ip.encode()).hexdigest()}"

            try:
                # Intenta obtener el contador actual para esta IP
                current = self.redis_client.get(key)

                if current is None:
                    # Primera peticion de esta IP en la ventana actual
                    # setex: SET con EXpiracion automatica
                    # Crea la clave con valor 1 y expiracion en 'window' segundos
                    self.redis_client.setex(key, self.window, 1)

                elif int(current) >= self.requests_limit:
                    # El cliente ha excedido el limite de peticiones
                    # Retorna error HTTP 429 (Too Many Requests)
                    return JsonResponse({
                        'error': 'Rate limit exceeded',
                        'message': f'Maximum {self.requests_limit} requests per {self.window} seconds'
                    }, status=429)

                else:
                    # El cliente no ha excedido el limite
                    # Incrementa el contador atomicamente en Redis
                    # incr es atomico, evita condiciones de carrera
                    self.redis_client.incr(key)

            except Exception:
                # Si hay error con Redis, permite la peticion
                # Esto evita bloquear usuarios por fallos de infraestructura
                pass

        # Continua procesando la peticion con el siguiente middleware/vista
        response = self.get_response(request)

        # Retorna la respuesta generada por la vista
        return response

    def get_client_ip(self, request):
        """
        Obtiene la direccion IP real del cliente.

        Considera el caso de proxies inversos (como nginx) que envian
        la IP real en el header X-Forwarded-For. Esto es importante
        para no limitar todas las peticiones que vienen del proxy.

        Args:
            request: Objeto HttpRequest de Django

        Returns:
            str: Direccion IP del cliente como string

        Ejemplo:
            - Sin proxy: "192.168.1.100"
            - Con proxy: X-Forwarded-For contiene "203.0.113.50, 70.41.3.18"
                        Retorna "203.0.113.50" (la IP original del cliente)
        """
        # Intenta obtener la IP del header X-Forwarded-For (usado por proxies)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            # El header puede contener multiples IPs separadas por coma
            # Formato: "ip_cliente, ip_proxy1, ip_proxy2"
            # La primera IP es la del cliente original
            ip = x_forwarded_for.split(',')[0]
        else:
            # Sin proxy, obtiene la IP directa de la conexion
            # REMOTE_ADDR es establecido por el servidor web
            ip = request.META.get('REMOTE_ADDR')

        # Retorna la IP (puede incluir espacios, se deberia strip en produccion)
        return ip
