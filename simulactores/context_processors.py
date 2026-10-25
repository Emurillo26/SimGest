from .models import MATRIZ_PERMISOS, Notificacion
from .navegacion import MENU_LATERAL, MODULOS_SIN_VISTA_TODAVIA, VISTA_A_SECCION


def menu_lateral(request):

    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}

    rol = getattr(usuario.rol, 'nombre', None)
    permitidos = MATRIZ_PERMISOS.get(rol, set())

    vista_actual = getattr(request.resolver_match, 'view_name', None) if request.resolver_match else None
    seccion_activa = VISTA_A_SECCION.get(vista_actual)

    items = [
        {**item, 'activo': item['seccion'] == seccion_activa}
        for item in MENU_LATERAL
        if item['modulo'] in permitidos and item['modulo'] not in MODULOS_SIN_VISTA_TODAVIA
    ]

    return {
        'menu_lateral': items,
        'panel_nombre': f'Panel {rol}' if rol else 'Panel',
        'notificaciones_no_leidas': Notificacion.objects.filter(usuario=usuario, leido=False).count(),
    }
