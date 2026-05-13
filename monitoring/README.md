# Sistema de Monitoreo - LegalFlow

## Descripcion General

Este sistema de monitoreo utiliza **Prometheus** y **Grafana** para recolectar, almacenar y visualizar metricas de todos los microservicios de LegalFlow.

## Arquitectura

```
                    +------------------+
                    |     Grafana      |
                    |   (Puerto 3030)  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |   Prometheus     |
                    |   (Puerto 9090)  |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
    +-----------+      +-----------+      +-----------+
    | API       |      | IAM       |      | Matter    |
    | Gateway   |      | Service   |      | Service   |
    | :8000     |      | :8001     |      | :8002     |
    +-----------+      +-----------+      +-----------+
          |                  |                  |
          v                  v                  v
    +-----------+      +-----------+      +-----------+
    | Document  |      | Time      |      | Billing   |
    | Service   |      | Service   |      | Service   |
    | :8003     |      | :8004     |      | :8005     |
    +-----------+      +-----------+      +-----------+
          |                  |                  |
          v                  v                  v
    +-----------+      +-----------+      +-----------+
    | Calendar  |      | Portal    |      | Analytics |
    | Service   |      | Service   |      | Service   |
    | :8006     |      | :8007     |      | :8008     |
    +-----------+      +-----------+      +-----------+
```

## Componentes

### 1. Prometheus (Puerto 9090)
- Recolecta metricas de todos los microservicios cada 15 segundos
- Almacena las metricas en su base de datos de series temporales
- Evalua reglas de alerta

### 2. Grafana (Puerto 3030)
- Visualiza las metricas en dashboards interactivos
- Permite crear alertas visuales
- Credenciales por defecto: `admin` / `legalflow2024`

### 3. django-prometheus
- Libreria instalada en cada microservicio Django
- Expone metricas en el endpoint `/metrics`
- Metricas incluyen:
  - Requests HTTP (count, latency, status codes)
  - Conexiones de base de datos
  - Metricas de Python (GC, threads, memoria)

## Metricas Disponibles

### HTTP Requests
- `django_http_requests_total_by_method_total` - Total de requests por metodo HTTP
- `django_http_requests_total_by_transport_total` - Total por tipo de transporte
- `django_http_requests_total_by_view_transport_method_total` - Por vista, transporte y metodo
- `django_http_responses_total_by_status_total` - Respuestas por codigo de estado
- `django_http_requests_latency_seconds` - Latencia de requests (histograma)

### Base de Datos
- `django_db_new_connections_total` - Nuevas conexiones a la DB
- `django_db_new_connection_errors_total` - Errores de conexion
- `django_db_execute_total` - Queries ejecutadas
- `django_db_errors_total` - Errores de DB

### Modelo de Datos
- `django_model_inserts_total` - Inserciones por modelo
- `django_model_updates_total` - Actualizaciones por modelo
- `django_model_deletes_total` - Eliminaciones por modelo

### Python/Process
- `process_cpu_seconds_total` - Uso de CPU
- `process_resident_memory_bytes` - Uso de memoria
- `python_gc_collections_total` - Colecciones de garbage collector

## Alertas Configuradas

Las alertas estan definidas en `prometheus/alerts/legalflow_alerts.yml`:

| Alerta | Condicion | Severidad |
|--------|-----------|-----------|
| ServiceDown | Servicio no responde por 1 min | critical |
| HighLatency | Latencia p95 > 2s por 5 min | warning |
| HighErrorRate5xx | Errores 5xx > 5% por 5 min | critical |
| HighErrorRate4xx | Errores 4xx > 20% por 10 min | warning |
| HighMemoryUsage | Memoria > 80% por 5 min | warning |
| HighCPUUsage | CPU > 80% por 5 min | warning |
| DatabaseConnectionErrors | Errores de conexion > 5 por 5 min | critical |
| AuthenticationServiceIssues | IAM Service con alta latencia | critical |

## Uso

### Iniciar el Sistema de Monitoreo

```bash
cd backend
docker-compose up -d prometheus grafana
```

### Acceder a las Interfaces

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3030
  - Usuario: `admin`
  - Password: `legalflow2024`

### Verificar que los Servicios Exponen Metricas

```bash
# Verificar metricas del API Gateway
curl http://localhost:8000/metrics

# Verificar metricas del IAM Service
curl http://localhost:8001/metrics

# Verificar targets en Prometheus
curl http://localhost:9090/api/v1/targets
```

## Dashboards

### LegalFlow Overview
Dashboard principal con:
- Estado de todos los servicios (UP/DOWN)
- Requests por segundo por servicio
- Latencia p95 por servicio
- Distribucion de codigos de estado HTTP
- Uso de memoria por servicio
- Total de requests y errores

### Acceder al Dashboard
1. Ir a Grafana (http://localhost:3030)
2. Login con credenciales
3. Ir a Dashboards > Browse
4. Seleccionar "LegalFlow Overview"

## Estructura de Archivos

```
monitoring/
├── README.md                                    # Esta documentacion
├── prometheus/
│   ├── prometheus.yml                           # Configuracion principal
│   └── alerts/
│       └── legalflow_alerts.yml                 # Reglas de alertas
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── datasources.yml                  # Configuracion de Prometheus
        └── dashboards/
            ├── dashboards.yml                   # Configuracion de dashboards
            └── json/
                └── legalflow-overview.json      # Dashboard principal
```

## Configuracion en Produccion

### Variables de Entorno

```env
# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=tu-password-seguro

# Prometheus (opcional - para retencion de datos)
PROMETHEUS_RETENTION_TIME=15d
PROMETHEUS_RETENTION_SIZE=10GB
```

### Recomendaciones de Seguridad

1. **Cambiar credenciales de Grafana** en produccion
2. **Restringir acceso** a los puertos 9090 y 3030
3. **Configurar HTTPS** para Grafana en produccion
4. **Habilitar autenticacion** en Prometheus si es accesible externamente

### Alertmanager (Opcional)

Para recibir notificaciones de alertas, configurar Alertmanager:

```yaml
# En prometheus.yml, descomentar:
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

## Troubleshooting

### Servicio no aparece en Prometheus

1. Verificar que el servicio este corriendo
2. Verificar que `/metrics` responda correctamente
3. Revisar logs de Prometheus: `docker-compose logs prometheus`

### Grafana no muestra datos

1. Verificar que Prometheus este corriendo
2. Verificar la conexion del datasource en Grafana
3. Revisar que el rango de tiempo sea correcto

### Metricas no se actualizan

1. Verificar el scrape_interval en prometheus.yml
2. Revisar el estado de los targets en http://localhost:9090/targets
3. Verificar que no hay errores de scraping

## Extender el Monitoreo

### Agregar Metricas Personalizadas

```python
# En cualquier vista de Django
from prometheus_client import Counter, Histogram

# Crear metrica
login_attempts = Counter(
    'legalflow_login_attempts_total',
    'Total login attempts',
    ['status']
)

# Usar metrica
login_attempts.labels(status='success').inc()
```

### Agregar Nuevos Dashboards

1. Crear dashboard en Grafana UI
2. Exportar como JSON
3. Guardar en `monitoring/grafana/provisioning/dashboards/json/`
4. Reiniciar Grafana

## Referencias

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [django-prometheus](https://github.com/korfuri/django-prometheus)
