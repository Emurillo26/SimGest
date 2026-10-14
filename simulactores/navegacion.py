MENU_LATERAL = [
    # --- Administrador ---
    {
        'modulo': 'dashboard_administrador',
        'seccion': 'dashboard_administrador',
        'etiqueta': 'Panel',
        'url_name': 'simulactores:dashboard_administrador',
    },
    {
        'modulo': 'listado_usuarios',
        'seccion': 'listado_usuarios',
        'etiqueta': 'Usuarios y accesos',
        'url_name': 'simulactores:listado_usuarios',
    },
    {
        'modulo': 'gestion_solicitudes',
        'seccion': 'gestion_solicitudes',
        'etiqueta': 'Solicitudes',
        'url_name': 'simulactores:solicitudes_admin',
    },
    {
        'modulo': 'bitacora_actividad',
        'seccion': 'bitacora_actividad',
        'etiqueta': 'Bitácora de actividad',
        'url_name': 'simulactores:bitacora_actividad',
    },
    {
        'modulo': 'biblioteca_escenarios',
        'seccion': 'biblioteca_escenarios',
        'etiqueta': 'Biblioteca de escenarios',
        'url_name': 'simulactores:biblioteca_escenarios',
    },

    # --- Cliente ---
    {
        'modulo': 'dashboard_cliente',
        'seccion': 'mis_solicitudes',
        'etiqueta': 'Mis solicitudes',
        'url_name': 'simulactores:dashboard_cliente',
    },
    {
        'modulo': 'dashboard_cliente',
        'seccion': 'nueva_solicitud',
        'etiqueta': 'Nueva solicitud',
        'url_name': 'simulactores:crear_solicitud',
    },

    # --- Actor ---
    {
        'modulo': 'dashboard_actor',
        'seccion': 'dashboard_actor',
        'etiqueta': 'Mi panel',
        'url_name': 'simulactores:dashboard_actor',
    },

    # --- Común a todos los roles ---
    {
        'modulo': 'perfil',
        'seccion': 'perfil',
        'etiqueta': 'Mi perfil',
        'url_name': 'simulactores:perfil',
    },
]


VISTA_A_SECCION = {
    'simulactores:dashboard_administrador': 'dashboard_administrador',
    'simulactores:listado_usuarios': 'listado_usuarios',
    'simulactores:actualizar_rol': 'listado_usuarios',
    'simulactores:solicitudes_admin': 'gestion_solicitudes',
    'simulactores:solicitud_admin_detalle': 'gestion_solicitudes',
    'simulactores:bitacora_actividad': 'bitacora_actividad',
    'simulactores:biblioteca_escenarios': 'biblioteca_escenarios',
    'simulactores:crear_escenario': 'biblioteca_escenarios',
    'simulactores:editar_escenario': 'biblioteca_escenarios',
    'simulactores:detalle_escenario': 'biblioteca_escenarios',

    'simulactores:dashboard_cliente': 'mis_solicitudes',
    'simulactores:detalle_solicitud': 'mis_solicitudes',
    'simulactores:aprobar_escenario': 'mis_solicitudes',
    'simulactores:rechazar_escenario': 'mis_solicitudes',
    'simulactores:cancelar_solicitud': 'mis_solicitudes',
    'simulactores:crear_solicitud': 'nueva_solicitud',

    'simulactores:dashboard_actor': 'dashboard_actor',

    'simulactores:perfil': 'perfil',
}


MODULOS_SIN_VISTA_TODAVIA = set()  # la biblioteca de escenarios ya tiene vista (HU-21)
