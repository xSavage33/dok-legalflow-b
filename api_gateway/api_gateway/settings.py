import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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
    # Third party
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'django_prometheus',  # Monitoring with Prometheus
    # Local apps
    'gateway',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # Prometheus - must be first
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # CSRF disabled - REST API using JWT authentication
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'gateway.middleware.RateLimitMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',  # Prometheus - must be last
]

ROOT_URLCONF = 'api_gateway.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'api_gateway.wsgi.application'

# No database for API Gateway - it's stateless
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Settings for validation
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)

# Microservice URLs
SERVICE_URLS = {
    'iam': os.environ.get('IAM_SERVICE_URL', 'http://localhost:8001'),
    'matter': os.environ.get('MATTER_SERVICE_URL', 'http://localhost:8002'),
    'document': os.environ.get('DOCUMENT_SERVICE_URL', 'http://localhost:8003'),
    'time': os.environ.get('TIME_SERVICE_URL', 'http://localhost:8004'),
    'billing': os.environ.get('BILLING_SERVICE_URL', 'http://localhost:8005'),
    'calendar': os.environ.get('CALENDAR_SERVICE_URL', 'http://localhost:8006'),
    'portal': os.environ.get('PORTAL_SERVICE_URL', 'http://localhost:8007'),
    'analytics': os.environ.get('ANALYTICS_SERVICE_URL', 'http://localhost:8008'),
}

# CORS Configuration
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]
else:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://localhost:3001',
        'http://148.230.81.69:4000',
        'http://148.230.81.69:4001',
        'https://legalflow.company',
        'https://admin.legalflow.company',
        'https://app.legalflow.company',
        'http://legalflow.company',
        'http://admin.legalflow.company',
        'http://app.legalflow.company',
    ]

# Also allow origins with regex for subdomains
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.onrender\.com$",
    r"^https://.*\.legalflow\.company$",
    r"^http://.*\.legalflow\.company$",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:8000',
    'https://*.onrender.com',
    'https://*.vercel.app',
    'https://legalflow.company',
    'https://*.legalflow.company',
    'http://legalflow.company',
    'http://*.legalflow.company',
    'http://148.230.81.69:8000',
    'http://148.230.81.69:4000',
    'http://148.230.81.69:4001',
]

# Rate Limiting
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 100))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))  # seconds

# Redis for rate limiting
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'LegalFlow API Gateway',
    'DESCRIPTION': 'Central API Gateway for LegalFlow Microservices',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Internationalization
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
