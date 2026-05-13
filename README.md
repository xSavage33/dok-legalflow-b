# LegalFlow

Sistema de Gestión Legal Inteligente - Plataforma completa para firmas de abogados con arquitectura de microservicios.

## Características

- **Gestión de Casos**: CRUD completo con seguimiento de partes, fechas y notas
- **Gestión Documental**: Versionado, auditoría de acceso y categorización
- **Control de Tiempo**: Temporizador en tiempo real y registro manual de horas
- **Facturación**: Generación de facturas, pagos y acuerdos de tarifas
- **Calendario**: Eventos y plazos procesales con cálculo de días hábiles
- **Portal del Cliente**: Acceso restringido para clientes
- **Analytics**: Dashboard de KPIs para gerencia
- **Notificaciones**: Sistema de alertas automáticas vía email

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │   Admin Portal      │    │   Client Portal     │            │
│  │   (React + TS)      │    │   (React + TS)      │            │
│  │   Puerto: 3000      │    │   Puerto: 3001      │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway                                 │
│                      Puerto: 8000                                │
│        (JWT Validation, Routing, Rate Limiting)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
      ┌───────────────────────┼───────────────────────┐
      │           │           │           │           │
      ▼           ▼           ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│   IAM   │ │ Matter  │ │Document │ │  Time   │ │ Billing │
│ Service │ │ Service │ │ Service │ │Tracking │ │ Service │
│  :8001  │ │  :8002  │ │  :8003  │ │  :8004  │ │  :8005  │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
     │           │           │           │           │
     ▼           ▼           ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ db_iam  │ │db_matter│ │  db_doc │ │ db_time │ │db_billing│
│ (PG)    │ │  (PG)   │ │  (PG)   │ │  (PG)   │ │  (PG)   │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘

┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────────┐
│Calendar │ │ Client  │ │Analytics│ │ Notification Worker │
│ Service │ │ Portal  │ │ Service │ │      (Celery)       │
│  :8006  │ │  :8007  │ │  :8008  │ │                     │
└────┬────┘ └────┬────┘ └────┬────┘ └──────────┬──────────┘
     │           │           │                  │
     ▼           ▼           ▼                  ▼
┌─────────┐ ┌─────────┐ ┌─────────┐      ┌───────────┐
│db_calendar│ │db_portal│ │db_analytics│    │   Redis   │
│  (PG)   │ │  (PG)   │ │  (PG)   │      │  (Broker) │
└─────────┘ └─────────┘ └─────────┘      └───────────┘
```

## Tecnologías

### Backend
- Python 3.11
- Django 5.0 + Django REST Framework
- PostgreSQL 15 (una BD por servicio)
- Redis (broker para Celery)
- Celery (tareas asíncronas)
- JWT (autenticación)
- django-guardian (permisos a nivel de objeto)

### Frontend
- React 18
- TypeScript
- TailwindCSS
- React Router DOM
- TanStack Query (React Query)
- Axios

### DevOps
- Docker + Docker Compose
- GitHub Actions (CI/CD)
- Vercel (Frontend)
- Render (Backend)

## Requisitos Previos

- Docker y Docker Compose
- Node.js 20+ (para desarrollo frontend)
- Python 3.11+ (para desarrollo backend local)

## Inicio Rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/xsavage33/legalflow-backend
git clone https://github.com/xsavage33/legalflow-frontend
cd legalflow
```

### 2. Configurar variables de entorno

```bash
cd backend
cp .env.example .env
# Editar .env con tus configuraciones
```

### 3. Iniciar con Docker Compose

```bash
cd backend
docker-compose up -d
```

Esto iniciará:
- 8 bases de datos PostgreSQL
- Redis
- 9 microservicios
- Celery worker

### 4. Iniciar Frontend (desarrollo)

**Admin Portal:**
```bash
cd frontend/admin-portal
cp .env.example .env
npm install
npm run dev
```

**Client Portal:**
```bash
cd frontend/client-portal
cp .env.example .env
npm install
npm run dev
```

## Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| API Gateway | 8000 | Punto de entrada, validación JWT, routing |
| IAM Service | 8001 | Autenticación, usuarios, roles, permisos |
| Matter Service | 8002 | Gestión de casos legales |
| Document Service | 8003 | Documentos, versiones, auditoría |
| Time Tracking | 8004 | Control de tiempo, temporizador |
| Billing Service | 8005 | Facturación, pagos, tarifas |
| Calendar Service | 8006 | Eventos, plazos procesales |
| Client Portal | 8007 | API para portal de clientes |
| Analytics Service | 8008 | Dashboard, KPIs, reportes |

## API Endpoints Principales

### Autenticación
```
POST /api/auth/register/      - Registro
POST /api/auth/login/         - Login (retorna JWT)
POST /api/auth/token/refresh/ - Refrescar token
GET  /api/auth/profile/       - Perfil del usuario
```

### Casos
```
GET    /api/cases/            - Listar casos
POST   /api/cases/            - Crear caso
GET    /api/cases/{id}/       - Detalle de caso
PUT    /api/cases/{id}/       - Actualizar caso
DELETE /api/cases/{id}/       - Eliminar caso
```

### Documentos
```
GET    /api/documents/                    - Listar documentos
POST   /api/documents/                    - Subir documento
GET    /api/documents/{id}/               - Detalle de documento
POST   /api/documents/{id}/download/      - Descargar (con auditoría)
GET    /api/documents/{id}/access-log/    - Log de accesos
```

### Control de Tiempo
```
GET    /api/time-entries/       - Listar entradas
POST   /api/time-entries/       - Crear entrada manual
POST   /api/timers/start/       - Iniciar temporizador
POST   /api/timers/stop/        - Detener temporizador
GET    /api/timers/current/     - Timer actual
```

### Facturación
```
GET    /api/invoices/           - Listar facturas
POST   /api/invoices/           - Crear factura
POST   /api/invoices/{id}/items/    - Agregar items
POST   /api/invoices/{id}/payments/ - Registrar pago
```

### Calendario
```
GET    /api/events/              - Listar eventos
GET    /api/events/upcoming/     - Próximos eventos
GET    /api/deadlines/           - Listar plazos
POST   /api/deadlines/calculate/ - Calcular fecha con días hábiles
```

### Analytics (Solo Admin/Partner)
```
GET    /api/analytics/dashboard/     - Dashboard general
GET    /api/analytics/profitability/ - Rentabilidad
GET    /api/analytics/workload/      - Carga de trabajo
```

## Roles y Permisos

| Rol | Descripción |
|-----|-------------|
| admin | Acceso total al sistema |
| partner | Socio - acceso a analytics y gestión |
| associate | Abogado asociado |
| paralegal | Asistente legal |
| client | Cliente - solo portal de cliente |

## Estructura del Proyecto

```
legalflow/
├── backend/
│   ├── api_gateway/
│   ├── iam_service/
│   ├── matter_service/
│   ├── document_service/
│   ├── time_tracking_service/
│   ├── billing_service/
│   ├── calendar_service/
│   ├── client_portal_service/
│   ├── analytics_service/
│   ├── notification_worker/
│   ├── docker-compose.yml
│   ├── requirements-base.txt
│   └── .env.example
├── frontend/
│   ├── admin-portal/
│   └── client-portal/
├── .github/
│   └── workflows/
│       ├── backend-ci.yml
│       └── frontend-ci.yml
└── README.md
```

## Desarrollo

### Backend

Cada microservicio es un proyecto Django independiente. Para desarrollo local:

```bash
cd backend/iam_service
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r ../requirements-base.txt
python manage.py migrate
python manage.py runserver 8001
```

### Frontend

```bash
cd frontend/admin-portal
npm install
npm run dev
```

### Tests

**Backend:**
```bash
cd backend
docker-compose up -d db_iam  # Iniciar BD de pruebas
cd iam_service
pytest --cov=.
```

**Frontend:**
```bash
cd frontend/admin-portal
npm test
```

## Despliegue

### Backend (Render)

1. Crear un nuevo Web Service por cada microservicio
2. Configurar las variables de entorno
3. El archivo `Dockerfile` en cada servicio se usa para el build

### Frontend (Vercel)

1. Importar repositorio en Vercel
2. Configurar directorio raíz: `frontend/admin-portal` o `frontend/client-portal`
3. Configurar variable `VITE_API_URL`

## Variables de Entorno

```env
# General
DEBUG=false
SECRET_KEY=tu-secret-key-muy-segura
JWT_SECRET_KEY=tu-jwt-secret-key-muy-segura

# Bases de datos (una por servicio)
DATABASE_URL_IAM=postgres://user:pass@host:5432/db_iam
DATABASE_URL_MATTER=postgres://user:pass@host:5432/db_matter
# ... etc

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (opcional)
EMAIL_HOST=smtp.ejemplo.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-email
EMAIL_HOST_PASSWORD=tu-password

# URLs de servicios
IAM_SERVICE_URL=http://localhost:8001
MATTER_SERVICE_URL=http://localhost:8002
# ... etc
```

## CI/CD

El proyecto incluye workflows de GitHub Actions para:

- **Backend CI**: Linting (Black, Flake8), tests, análisis de seguridad (Bandit, Safety), build Docker
- **Frontend CI**: ESLint, TypeScript check, build, deploy a Vercel

## Seguridad

- Todas las credenciales en variables de entorno
- JWT para autenticación
- RBAC con django-guardian para permisos granulares
- Auditoría de acceso a documentos
- Headers de seguridad (X-Frame-Options, X-Content-Type-Options)
- HTTPS obligatorio en producción

## Licencia

MIT License - Ver archivo LICENSE para detalles.

## Contacto

Para soporte o consultas, contactar a: soporte@legalflow.com
