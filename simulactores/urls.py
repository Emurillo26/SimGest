from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

from .asignacion_views import asignar_actor_view, reasignar_actor_view
from .escenario_estado_views import (
    archivar_escenario_view,
    biblioteca_escenarios_hu24_view,
    detalle_escenario_hu24_view,
    reactivar_escenario_view,
)

from .notificaciones_views import (
    abrir_notificacion_view,
    marcar_notificacion_leida_view,
    marcar_todas_leidas_view,
    notificaciones_view,
)

from .password_reset_views import recuperar_contrasena_view


app_name = 'simulactores'


urlpatterns = [
    # ------------------------------------------------------------
    # Inicio
    # ------------------------------------------------------------

    path(
        '',
        views.home_view,
        name='home'
    ),

    # ------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------

    path(
        'registro/',
        views.registro_view,
        name='registro'
    ),

    path(
        'confirmar/<str:token>/',
        views.confirmar_correo_view,
        name='confirmar_correo'
    ),

    # ------------------------------------------------------------
    # Login / Logout
    # ------------------------------------------------------------

    path(
        'login/',
        views.login_view,
        name='login'
    ),

    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),

    # ------------------------------------------------------------
    # HU-03 - Recuperación de contraseña
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Perfil
    # ------------------------------------------------------------

    path(
        'perfil/',
        views.perfil_view,
        name='perfil'
    ),

    # ------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Bitácora
    # ------------------------------------------------------------

    path(
        'bitacora-actividad/',
        views.bitacora_actividad_view,
        name='bitacora_actividad'
    ),

    # ------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------

    path(
        'dashboard/',
        views.dashboard_cliente_view,
        name='dashboard_cliente'
    ),

    path(
        'dashboard/admin/',
        views.dashboard_administrador_view,
        name='dashboard_administrador'
    ),

    path(
        'dashboard/actor/',
        views.dashboard_actor_view,
        name='dashboard_actor'
    ),

    # ------------------------------------------------------------
    # Solicitudes del cliente
    # ------------------------------------------------------------

    path(
        'solicitudes/',
        views.mis_solicitudes_view,
        name='mis_solicitudes'
    ),

    path(
        'solicitudes/nueva/',
        views.crear_solicitud_view,
        name='crear_solicitud'
    ),

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

    # ------------------------------------------------------------
    # Gestión de solicitudes del administrador
    # ------------------------------------------------------------

    path(
        'gestion-solicitudes/',
        views.solicitudes_admin_view,
        name='solicitudes_admin'
    ),

    path(
        'gestion-solicitudes/<uuid:solicitud_uuid>/',
        views.solicitud_admin_detalle_view,
        name='solicitud_admin_detalle'
    ),

    # HU-19
    path(
        'gestion-solicitudes/<uuid:solicitud_uuid>/estado/',
        views.cambiar_estado_solicitud_view,
        name='cambiar_estado_solicitud'
    ),

    # HU-44 y HU-45
    path(
        'gestion-solicitudes/<uuid:solicitud_uuid>/asignar-actor/',
        asignar_actor_view,
        name='asignar_actor'
    ),
    path(
        'gestion-solicitudes/<uuid:solicitud_uuid>/reasignar-actor/',
        reasignar_actor_view,
        name='reasignar_actor'
    ),

    # ------------------------------------------------------------
    # Biblioteca de escenarios
    # HU-21 / HU-22 / HU-23 / HU-24 / HU-25
    # ------------------------------------------------------------

    path(
        'escenarios/',
        biblioteca_escenarios_hu24_view,
        name='biblioteca_escenarios'
    ),

    path(
        'escenarios/nuevo/',
        views.crear_escenario_view,
        name='crear_escenario'
    ),

    path(
        'escenarios/<int:escenario_id>/',
        detalle_escenario_hu24_view,
        name='detalle_escenario'
    ),

    path(
        'escenarios/<int:escenario_id>/editar/',
        views.editar_escenario_view,
        name='editar_escenario'
    ),

    # HU-24 - Archivar escenario
    path(
        'escenarios/<int:escenario_id>/archivar/',
        archivar_escenario_view,
        name='archivar_escenario'
    ),

    # HU-24 - Reactivar escenario
    path(
        'escenarios/<int:escenario_id>/reactivar/',
        reactivar_escenario_view,
        name='reactivar_escenario'
    ),

    # HU-30 - Notificaciones
    path(
        'notificaciones/',
        notificaciones_view,
        name='notificaciones'
    ),

    path(
        'notificaciones/<int:notificacion_id>/abrir/',
        abrir_notificacion_view,
        name='abrir_notificacion'
    ),

    path(
        'notificaciones/<int:notificacion_id>/leida/',
        marcar_notificacion_leida_view,
        name='marcar_notificacion_leida'
    ),

    path(
        'notificaciones/marcar-todas/',
        marcar_todas_leidas_view,
        name='marcar_notificaciones_leidas'
    ),
]
