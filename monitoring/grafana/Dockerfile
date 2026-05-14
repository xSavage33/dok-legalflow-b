# =============================================================================
# GRAFANA DOCKERFILE - LegalFlow
# =============================================================================
# Imagen personalizada de Grafana con dashboards y datasources incluidos
# =============================================================================

FROM grafana/grafana:10.4.1

# Cambiar a usuario root para copiar archivos
USER root

# Crear directorios de provisioning
RUN mkdir -p /etc/grafana/provisioning/datasources \
    && mkdir -p /etc/grafana/provisioning/dashboards/json

# Copiar configuracion de datasources
COPY provisioning/datasources/datasources.yml /etc/grafana/provisioning/datasources/

# Copiar configuracion de dashboards
COPY provisioning/dashboards/dashboards.yml /etc/grafana/provisioning/dashboards/

# Copiar archivos JSON de dashboards
COPY provisioning/dashboards/json/ /etc/grafana/provisioning/dashboards/json/

# Asegurar permisos correctos
RUN chown -R grafana:root /etc/grafana/provisioning \
    && chmod -R 755 /etc/grafana/provisioning

# Volver al usuario grafana
USER grafana

# Exponer puerto
EXPOSE 3000
