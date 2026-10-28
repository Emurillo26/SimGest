from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .models import Actor, Asignacion, Solicitud
from .permisos import modulo_requerido


@modulo_requerido('dashboard_actor')
def dashboard_actor_view(request):
    """
    HU-26:
    Como actor quiero visualizar mi dashboard para consultar
    rápidamente mis próximas simulaciones y su estado.

    Criterios:
    - Muestra únicamente las simulaciones del actor autenticado.
    - Muestra solo simulaciones actuales o futuras.
    - Muestra fecha, horario y estado.
    - Si no hay simulaciones futuras, muestra un mensaje informativo.
    """

    actor = (
        Actor.objects
        .filter(usuario=request.user)
        .select_related('usuario')
        .first()
    )

    asignaciones = Asignacion.objects.none()

    resumen = {
        'total': 0,
        'pendientes': 0,
        'confirmadas': 0,
    }

    if actor:
        ahora = timezone.localtime()
        hoy = ahora.date()
        hora_actual = ahora.time()

        asignaciones = (
            Asignacion.objects
            .filter(
                actor=actor,
                estado__in=[
                    Asignacion.Estado.PENDIENTE,
                    Asignacion.Estado.CONFIRMADA,
                ],
            )
            .filter(
                Q(solicitud__fecha_evento__gt=hoy)
                |
                Q(
                    solicitud__fecha_evento=hoy,
                    solicitud__hora_fin__gte=hora_actual,
                )
            )
            .exclude(
                solicitud__estado=Solicitud.Estado.CANCELADA
            )
            .select_related(
                'solicitud',
                'solicitud__escenario',
            )
            .order_by(
                'solicitud__fecha_evento',
                'solicitud__hora_inicio',
            )
        )

        resumen = {
            'total': asignaciones.count(),
            'pendientes': asignaciones.filter(
                estado=Asignacion.Estado.PENDIENTE
            ).count(),
            'confirmadas': asignaciones.filter(
                estado=Asignacion.Estado.CONFIRMADA
            ).count(),
        }

    return render(
        request,
        'simulactores/dashboard_actor.html',
        {
            'actor': actor,
            'asignaciones': asignaciones,
            'resumen': resumen,
        }
    )