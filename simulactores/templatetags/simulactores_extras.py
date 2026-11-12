from django import template

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
