"""
URL configuration for contractcommand_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core.auth_views import (
    RoleTokenObtainPairView,
    RoleTokenBlacklistView,
    RoleTokenRefreshView,
    current_user,
)

urlpatterns = [
    path('', RedirectView.as_view(url=settings.FRONTEND_URL, permanent=False), name='home'),
    path('admin/', admin.site.urls),
    path('api/auth/token/', RoleTokenObtainPairView.as_view(), name='auth-token'),
    path(
        'api/auth/token/refresh/',
        RoleTokenRefreshView.as_view(),
        name='auth-token-refresh',
    ),
    path(
        'api/auth/token/blacklist/',
        RoleTokenBlacklistView.as_view(),
        name='auth-token-blacklist',
    ),
    path('api/auth/me/', current_user, name='auth-me'),
    path('api/', include('core.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
