# fincart/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Endpoints
    path('api/auth/', include('apps.authentication.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/cart/', include('apps.cart.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/sellers/', include('apps.sellers.urls')),
    path('api/admin/', include('apps.admin_tools.urls')),
    
    # Wallet Service Gateway (proxy to FastAPI)
    #path('api/wallet/', include('apps.wallet_gateway.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)