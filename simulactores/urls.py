from django.urls import path
from . import views

app_name = 'simulactores'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('usuarios/', views.listado_usuarios, name='listado_usuarios'),
    path('usuarios/<int:usuario_id>/rol/', views.actualizar_rol, name='actualizar_rol'),
]