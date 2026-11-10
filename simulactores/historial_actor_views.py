"""HU-38: historial de asignaciones de un actor, para evaluar su desempeño y frecuencia."""
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from .models import Actor, Asignacion
from .permisos import modulo_requerido

POR_PAGINA = 10


@modulo_requerido('perfil_actores')
def historial_actor_view(request, actor_id):
    actor = get_object_or_404(Actor.objects.select_related('usuario'), pk=actor_id)

    asignaciones = (
        Asignacion.objects.filter(actor=actor)
        .select_related('solicitud', 'solicitud__cliente')
        .order_by('-solicitud__fecha_evento', '-solicitud__hora_inicio', '-id_asignacion')
    )

    conteos = dict(
        asignaciones.order_by().values_list('estado').annotate(n=Count('pk'))
    )
    resumen = {
        'total': sum(conteos.values()),
        'ejecutadas': conteos.get(Asignacion.Estado.EJECUTADA, 0),
        'confirmadas': conteos.get(Asignacion.Estado.CONFIRMADA, 0),
        'pendientes': conteos.get(Asignacion.Estado.PENDIENTE, 0),
        'rechazadas': conteos.get(Asignacion.Estado.RECHAZADA, 0),
        'canceladas': conteos.get(Asignacion.Estado.CANCELADA, 0),
    }

    estado = request.GET.get('estado', '')
    estados_validos = {valor for valor, _ in Asignacion.Estado.choices}
    if estado in estados_validos:
        asignaciones = asignaciones.filter(estado=estado)
    else:
        estado = ''

    pagina = Paginator(asignaciones, POR_PAGINA).get_page(request.GET.get('page'))

    return render(request, 'simulactores/historial_actor.html', {
        'actor': actor,
        'pagina': pagina,
        'resumen': resumen,
        'estado': estado,
        'estados': Asignacion.Estado.choices,
    })