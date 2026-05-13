from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    return JsonResponse({"service": "billing_service", "status": "healthy" if db_status == "healthy" else "unhealthy", "database": db_status})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('billing.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('health/', health_check, name='health_check'),
    # Prometheus metrics endpoint
    path('', include('django_prometheus.urls')),
]
