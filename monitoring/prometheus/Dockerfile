# =============================================================================
# PROMETHEUS DOCKERFILE - LegalFlow
# =============================================================================
# Imagen personalizada de Prometheus con la configuracion incluida
# =============================================================================

FROM prom/prometheus:v2.50.1

# Copiar configuracion de Prometheus
COPY prometheus.yml /etc/prometheus/prometheus.yml

# Crear directorio de alertas (vacio por ahora)
RUN mkdir -p /etc/prometheus/alerts

# Exponer puerto
EXPOSE 9090

# Comando por defecto
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/prometheus", \
     "--storage.tsdb.retention.time=15d", \
     "--web.enable-lifecycle"]
