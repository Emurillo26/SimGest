import calendar
import datetime

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


ESTADOS_CON_ACCESO_AL_DETALLE = [
    Asignacion.Estado.PENDIENTE,
    Asignacion.Estado.CONFIRMADA,
    Asignacion.Estado.EJECUTADA,
]


@modulo_requerido('dashboard_actor')
def detalle_simulacion_actor_view(request, solicitud_uuid):
    """HU-28: detalle de una simulación asignada al actor."""

    asignacion = (
        Asignacion.objects
        .filter(
            solicitud__uuid=solicitud_uuid,
            actor__usuario=request.user,
            estado__in=ESTADOS_CON_ACCESO_AL_DETALLE,
        )
        .select_related('solicitud', 'solicitud__escenario')
        .first()
    )

    if asignacion is None:
        return render(request, 'simulactores/simulacion_no_autorizada.html', status=403)

    solicitud = asignacion.solicitud

    return render(request, 'simulactores/detalle_simulacion_actor.html', {
        'asignacion': asignacion,
        'solicitud': solicitud,
        'escenario': solicitud.escenario,
    })


# ----------------------------------------------------------------------
# HU-27 - Calendario de simulaciones del actor
# ----------------------------------------------------------------------

MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
DIAS_SEMANA_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
DIAS_LARGOS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

# Mismos estados que dan acceso al detalle (HU-28), para que todo evento
# del calendario se pueda abrir con un clic.
ESTADOS_EN_CALENDARIO = ESTADOS_CON_ACCESO_AL_DETALLE


def _leer_mes(valor, hoy):
    """Convierte '2026-11' en (2026, 11). Si es inválido, usa el mes actual."""
    try:
        anio_txt, mes_txt = (valor or '').split('-')
        anio, mes = int(anio_txt), int(mes_txt)
        if 2000 <= anio <= 2100 and 1 <= mes <= 12:
            return anio, mes
    except (ValueError, AttributeError):
        pass
    return hoy.year, hoy.month


def _mes_vecino(anio, mes, delta):
    indice = anio * 12 + (mes - 1) + delta
    return indice // 12, indice % 12 + 1


def _clave_mes(anio, mes):
    return f'{anio:04d}-{mes:02d}'


@modulo_requerido('dashboard_actor')
def calendario_actor_view(request):
    """
    HU-27:
    Como actor quiero consultar mi calendario de simulaciones para
    organizar mi disponibilidad y preparación.

    Criterios:
    - Visualización: muestra los eventos en sus fechas con hora y estado.
    - Cambio de período: mes anterior / siguiente actualiza el calendario.
    - Selección: al hacer clic en un evento se abre su detalle.
    """

    hoy = timezone.localdate()
    anio, mes = _leer_mes(request.GET.get('mes'), hoy)

    actor = (
        Actor.objects
        .filter(usuario=request.user)
        .select_related('usuario')
        .first()
    )

    semanas_fechas = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    primer_dia = semanas_fechas[0][0]
    ultimo_dia = semanas_fechas[-1][-1]

    eventos_por_fecha = {}
    total_mes = 0

    if actor:
        asignaciones = (
            Asignacion.objects
            .filter(
                actor=actor,
                estado__in=ESTADOS_EN_CALENDARIO,
                solicitud__fecha_evento__range=(primer_dia, ultimo_dia),
            )
            .exclude(solicitud__estado=Solicitud.Estado.CANCELADA)
            .select_related('solicitud', 'solicitud__escenario')
            .order_by('solicitud__fecha_evento', 'solicitud__hora_inicio')
        )
        for asignacion in asignaciones:
            fecha = asignacion.solicitud.fecha_evento
            eventos_por_fecha.setdefault(fecha, []).append(asignacion)
            if fecha.month == mes and fecha.year == anio:
                total_mes += 1

    semanas = []
    agenda = []
    for semana in semanas_fechas:
        fila = []
        for fecha in semana:
            eventos = eventos_por_fecha.get(fecha, [])
            en_mes = fecha.month == mes
            fila.append({
                'fecha': fecha,
                'en_mes': en_mes,
                'es_hoy': fecha == hoy,
                'eventos': eventos,
            })
            if en_mes and eventos:
                agenda.append({
                    'fecha': fecha,
                    'etiqueta': f'{DIAS_LARGOS_ES[fecha.weekday()]} {fecha.day}',
                    'eventos': eventos,
                })
        semanas.append(fila)

    anio_ant, mes_ant = _mes_vecino(anio, mes, -1)
    anio_sig, mes_sig = _mes_vecino(anio, mes, 1)

    return render(request, 'simulactores/calendario_actor.html', {
        'actor': actor,
        'semanas': semanas,
        'agenda': agenda,
        'dias_semana': DIAS_SEMANA_ES,
        'nombre_mes': f'{MESES_ES[mes]} {anio}',
        'total_mes': total_mes,
        'mes_anterior': _clave_mes(anio_ant, mes_ant),
        'mes_siguiente': _clave_mes(anio_sig, mes_sig),
        'es_mes_actual': (anio, mes) == (hoy.year, hoy.month),
    })
