from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),

    # Todas las rutas de la aplicación SimGest
    path('', include('simulactores.urls')),
]

# En desarrollo, Django sirve las fotos de perfil. En el hosting las sirve el servidor web.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
