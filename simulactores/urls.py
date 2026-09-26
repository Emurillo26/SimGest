from django.urls import path
from . import views

app_name = 'simulactores'

urlpatterns = [
    path('registro/', views.registro_view, name='registro'),
    path('confirmar/<str:token>/', views.confirmar_correo_view, name='confirmar_correo'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('usuarios/', views.listado_usuarios, name='listado_usuarios'),
    path('usuarios/<int:usuario_id>/rol/', views.actualizar_rol, name='actualizar_rol'),
    path('historial-accesos/', views.historial_accesos_view, name='historial_accesos'),
]