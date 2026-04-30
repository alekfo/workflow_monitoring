"""
URL configuration for workflow_monitoring project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.views.defaults import permission_denied
from django.views.generic import RedirectView


def handler403(request, exception=None):
    return permission_denied(request, exception, template_name='403.html')


urlpatterns = [
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('admin/', admin.site.urls),
    path('<slug:org_slug>/', include('signal1520.urls')),
    path('accounts/', include('authentication.urls')),
]

if settings.DEBUG:
    #сохранение на диске для медия
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    #сохранение на диске для статики
    urlpatterns.extend(
        static(settings.STATIC_URL, document=settings.STATIC_ROOT)
    )
