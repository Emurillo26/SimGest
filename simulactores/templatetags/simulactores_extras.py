from django import template
from django.utils.html import format_html

register = template.Library()

# Flujo real de una solicitud (models.Solicitud.Estado), en orden.
PASOS = [
    ('Pendiente', 'Solicitud recibida', 'Hemos recibido tu solicitud.'),
    ('En Revisión', 'En revisión', 'El equipo está revisando la información.'),
    ('Aprobada', 'Escenario aprobado', 'Se definió el escenario de la simulación.'),
    ('Actor Asignado', 'Actor asignado', 'Ya hay un actor asignado, pendiente de su confirmación.'),
    ('Confirmada', 'Confirmada', 'El actor confirmó su participación.'),
    ('Completada', 'Ejecución del evento', 'La simulación se realizó.'),
]

SIGUIENTE = {
    'Pendiente': 'Revisión del equipo',
    'En Revisión': 'Aprobación del escenario',
    'Aprobada': 'Asignación de actor',
    'Actor Asignado': 'Confirmación del actor',
    'Confirmada': 'Ejecución del evento',
}


@register.filter
def siguiente_paso(estado):
    """Texto del siguiente paso según el estado real; vacío si ya no hay acciones."""
    return SIGUIENTE.get(estado, 'Sin acciones')


@register.filter
def seguimiento(estado):
    """Lista de pasos con su situación (hecho / actual / pendiente) para el seguimiento."""
    nombres = [p[0] for p in PASOS]
    actual = nombres.index(estado) if estado in nombres else -1
    resultado = []
    for i, (valor, titulo, descripcion) in enumerate(PASOS):
        if estado == 'Completada' or i < actual:
            situacion = 'hecho'
        elif i == actual:
            situacion = 'actual'
        else:
            situacion = 'pendiente'
        resultado.append({'titulo': titulo, 'descripcion': descripcion, 'situacion': situacion})
    return resultado


@register.simple_tag(takes_context=True)
def url_pagina(context, numero):
    """Enlace a otra página de un listado, conservando los filtros que ya tenga la URL."""
    parametros = context['request'].GET.copy()
    parametros['pagina'] = numero
    return '?' + parametros.urlencode()


@register.simple_tag
def avatar(usuario, clase, etiqueta='span'):
    """Círculo del usuario: su foto de perfil si tiene una, o la inicial de su nombre."""
    if usuario is not None and getattr(usuario, 'foto', None):
        return format_html(
            '<{0} class="{1}" aria-hidden="true" style="padding:0;overflow:hidden">'
            '<img src="{2}" alt="" style="width:100%;height:100%;object-fit:cover;display:block"></{0}>',
            etiqueta, clase, usuario.foto.url,
        )
    inicial = (getattr(usuario, 'nombre', '') or '?')[:1].upper()
    return format_html('<{0} class="{1}" aria-hidden="true">{2}</{0}>', etiqueta, clase, inicial)
