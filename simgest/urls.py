from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),

    # Todas las rutas de la aplicación SimGest
    path('', include('simulactores.urls')),
]