import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
# ALLOWED_HOSTS - allow all hosts for microservices communication
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # CSRF disabled - REST API using JWT authentication
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'client_portal_service.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'client_portal_service.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://portal_user:portal_password@localhost:5438/portal_db')
DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('client_portal_service.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend', 'rest_framework.filters.SearchFilter'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
IAM_SERVICE_URL = os.environ.get('IAM_SERVICE_URL', 'http://localhost:8001')
MATTER_SERVICE_URL = os.environ.get('MATTER_SERVICE_URL', 'http://localhost:8002')
DOCUMENT_SERVICE_URL = os.environ.get('DOCUMENT_SERVICE_URL', 'http://localhost:8003')
BILLING_SERVICE_URL = os.environ.get('BILLING_SERVICE_URL', 'http://localhost:8005')

# Token para comunicacion interna entre microservicios
INTERNAL_SERVICE_TOKEN = os.environ.get('INTERNAL_SERVICE_TOKEN', 'legalflow-internal-service-token-2024')

# CORS Configuration
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]
else:
    CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://localhost:3001']

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.onrender\.com$",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

CORS_ALLOW_HEADERS = [
    "accept", "accept-encoding", "authorization", "content-type",
    "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with",
]

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000', 'http://localhost:3001', 'http://localhost:8000',
    'https://*.onrender.com', 'https://*.vercel.app',
]

SPECTACULAR_SETTINGS = {'TITLE': 'LegalFlow Client Portal API', 'VERSION': '1.0.0'}

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/7')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
