from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .password_reset_views import recuperar_contrasena_view


app_name = 'simulactores'


urlpatterns = [
    path('', views.home_view, name='home'),

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
        'bitacora-actividad/',
        views.bitacora_actividad_view,
        name='bitacora_actividad'
    ),

    path('dashboard/', views.dashboard_cliente_view, name='dashboard_cliente'),
    path('dashboard/admin/', views.dashboard_administrador_view, name='dashboard_administrador'),
    path('dashboard/actor/', views.dashboard_actor_view, name='dashboard_actor'),

    path('solicitudes/nueva/', views.crear_solicitud_view, name='crear_solicitud'),
    path(
        'solicitudes/historial/',
        views.historial_solicitudes_view,
        name='historial_solicitudes'
    ),
    path(
        'solicitudes/<uuid:solicitud_uuid>/',
        views.detalle_solicitud_view,
        name='detalle_solicitud'
    ),
    path(
        'solicitudes/<uuid:solicitud_uuid>/aprobar/',
        views.aprobar_escenario_view,
        name='aprobar_escenario'
    ),
    path(
        'solicitudes/<uuid:solicitud_uuid>/rechazar/',
        views.rechazar_escenario_view,
        name='rechazar_escenario'
    ),
    path(
        'solicitudes/<uuid:solicitud_uuid>/cancelar/',
        views.cancelar_solicitud_view,
        name='cancelar_solicitud'
    ),


    path('gestion-solicitudes/', views.solicitudes_admin_view, name='solicitudes_admin'),
    path(
        'gestion-solicitudes/<uuid:solicitud_uuid>/',
        views.solicitud_admin_detalle_view,
        name='solicitud_admin_detalle'
    ),
]