from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .password_reset_views import recuperar_contrasena_view


app_name = 'simulactores'


urlpatterns = [
    path('registro/', views.registro_view, name='registro'),

    path(
        'confirmar/<str:token>/',
        views.confirmar_correo_view,
        name='confirmar_correo'
    ),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # HU-03 - Recuperación de contraseña
    path(
        'recuperar-contrasena/',
        recuperar_contrasena_view,
        name='password_reset'
    ),

    path(
        'recuperar-contrasena/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='simulactores/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'restablecer-contrasena/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='simulactores/password_reset_confirm.html',
            success_url='/restablecer-contrasena/completado/'
        ),
        name='password_reset_confirm'
    ),

    path(
        'restablecer-contrasena/completado/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='simulactores/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    path('perfil/', views.perfil_view, name='perfil'),

    path(
        'usuarios/',
        views.listado_usuarios,
        name='listado_usuarios'
    ),

    path(
        'usuarios/<int:usuario_id>/rol/',
        views.actualizar_rol,
        name='actualizar_rol'
    ),

    path(
        'historial-accesos/',
        views.historial_accesos_view,
        name='historial_accesos'
    ),
]