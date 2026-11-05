import calendar
import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Actor, Asignacion, Disponibilidad, Solicitud
from .permisos import modulo_requerido
from .utils import notificar_administradores, registrar_cambios


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


MENSAJE_NO_MODIFICABLE = (
    'Esta simulación ya fue ejecutada o cancelada, por lo que '
    'ya no es posible modificar tu participación.'
)
MAX_MOTIVO = 500


def participacion_modificable(asignacion):
    """HU-29: el actor solo responde mientras la simulación siga vigente."""
    if asignacion.estado not in (
        Asignacion.Estado.PENDIENTE,
        Asignacion.Estado.CONFIRMADA,
    ):
        return False
    return asignacion.solicitud.estado not in (
        Solicitud.Estado.CANCELADA,
        Solicitud.Estado.COMPLETADA,
    )


def _asignacion_del_actor(request, solicitud_uuid, estados=None):
    consulta = Asignacion.objects.filter(
        solicitud__uuid=solicitud_uuid,
        actor__usuario=request.user,
    )
    if estados is not None:
        consulta = consulta.filter(estado__in=estados)
    return consulta.select_related('solicitud', 'solicitud__escenario').first()


def _pantalla_detalle(request, asignacion, **extra):
    solicitud = asignacion.solicitud
    contexto = {
        'asignacion': asignacion,
        'solicitud': solicitud,
        'escenario': solicitud.escenario,
        'puede_responder': participacion_modificable(asignacion),
    }
    contexto.update(extra)
    return render(request, 'simulactores/detalle_simulacion_actor.html', contexto)


@modulo_requerido('dashboard_actor')
def detalle_simulacion_actor_view(request, solicitud_uuid):
    """HU-28: detalle de una simulación asignada al actor."""

    asignacion = _asignacion_del_actor(
        request, solicitud_uuid, estados=ESTADOS_CON_ACCESO_AL_DETALLE)

    if asignacion is None:
        return render(request, 'simulactores/simulacion_no_autorizada.html', status=403)

    return _pantalla_detalle(request, asignacion)


# ----------------------------------------------------------------------
# HU-29 - Confirmar o rechazar la participación en una simulación
# ----------------------------------------------------------------------

def _ip(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _resumen_simulacion(solicitud):
    return f'{solicitud.numero_solicitud} del {solicitud.fecha_evento.strftime("%d/%m/%Y")}'


def _recortar(texto, limite=255):
    """La notificación guarda máximo 255 caracteres."""
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + '…'


def _bloqueada(request, asignacion):
    """Cambio no permitido: simulación ejecutada o cancelada (u otra asignación cerrada)."""
    messages.error(request, MENSAJE_NO_MODIFICABLE)
    if asignacion.estado in ESTADOS_CON_ACCESO_AL_DETALLE:
        return redirect('simulactores:detalle_simulacion_actor', solicitud_uuid=asignacion.solicitud.uuid)
    return redirect('simulactores:dashboard_actor')


@modulo_requerido('dashboard_actor')
@require_POST
def confirmar_participacion_view(request, solicitud_uuid):
    """HU-29 escenario 1: el actor confirma una simulación pendiente."""
    asignacion = _asignacion_del_actor(request, solicitud_uuid)
    if asignacion is None:
        return render(request, 'simulactores/simulacion_no_autorizada.html', status=403)

    destino = redirect('simulactores:detalle_simulacion_actor', solicitud_uuid=solicitud_uuid)

    with transaction.atomic():
        asignacion = (
            Asignacion.objects.select_for_update()
            .select_related('solicitud', 'actor__usuario')
            .get(pk=asignacion.pk)
        )
        if not participacion_modificable(asignacion):
            return _bloqueada(request, asignacion)

        if asignacion.estado == Asignacion.Estado.CONFIRMADA:
            messages.info(request, 'Ya habías confirmado tu participación en esta simulación.')
            return destino

        asignacion.estado = Asignacion.Estado.CONFIRMADA
        asignacion.save(update_fields=['estado'])
        registrar_cambios(
            request.user, 'Respuesta a asignación',
            [('estado_asignacion', Asignacion.Estado.PENDIENTE, Asignacion.Estado.CONFIRMADA)],
            ip_origen=_ip(request),
        )

    solicitud = asignacion.solicitud
    notificar_administradores(
        _recortar(f'{request.user.nombre} confirmó su participación en la simulación {_resumen_simulacion(solicitud)}.'),
        asunto='Actor confirmó su participación',
        enlace=reverse('simulactores:solicitud_admin_detalle', args=[solicitud.uuid]),
    )
    messages.success(request, 'Confirmaste tu participación. Avisamos al administrador.')
    return destino


@modulo_requerido('dashboard_actor')
@require_POST
def rechazar_participacion_view(request, solicitud_uuid):
    """HU-29 escenario 2: el actor rechaza indicando un motivo."""
    asignacion = _asignacion_del_actor(request, solicitud_uuid)
    if asignacion is None:
        return render(request, 'simulactores/simulacion_no_autorizada.html', status=403)

    motivo = (request.POST.get('motivo') or '').strip()
    if not motivo or len(motivo) > MAX_MOTIVO:
        if not participacion_modificable(asignacion):
            return _bloqueada(request, asignacion)
        error = (
            'Indica el motivo por el que no puedes asistir.' if not motivo
            else f'El motivo no puede superar los {MAX_MOTIVO} caracteres.'
        )
        return _pantalla_detalle(
            request, asignacion, error_motivo=error, motivo_previo=motivo, abrir_rechazo=True)

    with transaction.atomic():
        asignacion = (
            Asignacion.objects.select_for_update()
            .select_related('solicitud', 'actor__usuario')
            .get(pk=asignacion.pk)
        )
        if not participacion_modificable(asignacion):
            return _bloqueada(request, asignacion)

        estado_anterior = asignacion.estado
        asignacion.estado = Asignacion.Estado.RECHAZADA
        asignacion.motivo_rechazo = motivo
        asignacion.save(update_fields=['estado', 'motivo_rechazo'])

        cambios = [
            ('estado_asignacion', estado_anterior, Asignacion.Estado.RECHAZADA),
            ('motivo_rechazo', None, motivo),
        ]

        # Con el cupo libre, el administrador debe poder asignar un reemplazo.
        solicitud = asignacion.solicitud
        if solicitud.estado == Solicitud.Estado.CONFIRMADA:
            cambios.append(('estado_solicitud', solicitud.estado, Solicitud.Estado.ACTOR_ASIGNADO))
            solicitud.estado = Solicitud.Estado.ACTOR_ASIGNADO
            solicitud.save()

        registrar_cambios(
            request.user, 'Respuesta a asignación', cambios, ip_origen=_ip(request))

    cabecera = (
        f'{request.user.nombre} rechazó la simulación {_resumen_simulacion(solicitud)}. '
        'Hay que gestionar un reemplazo. Motivo: '
    )
    notificar_administradores(
        _recortar(cabecera + motivo),
        asunto='Actor rechazó una simulación: se necesita reemplazo',
        enlace=reverse('simulactores:solicitud_admin_detalle', args=[solicitud.uuid]),
    )
    messages.success(
        request, 'Registramos tu rechazo y avisamos al administrador para que gestione un reemplazo.')
    return redirect('simulactores:dashboard_actor')


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
    bloques_por_fecha = {}
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

        # HU-36: los bloques de disponibilidad también viven en este calendario.
        bloques = (
            Disponibilidad.objects
            .filter(actor=actor, fecha__range=(primer_dia, ultimo_dia))
            .order_by('fecha', 'hora_inicio')
        )
        for bloque in bloques:
            bloques_por_fecha.setdefault(bloque.fecha, []).append(bloque)

    semanas = []
    agenda = []
    for semana in semanas_fechas:
        fila = []
        for fecha in semana:
            eventos = eventos_por_fecha.get(fecha, [])
            bloques_dia = bloques_por_fecha.get(fecha, [])
            en_mes = fecha.month == mes
            fila.append({
                'fecha': fecha,
                'en_mes': en_mes,
                'es_hoy': fecha == hoy,
                'eventos': eventos,
                'bloques': bloques_dia,
                # Solo se puede registrar o editar disponibilidad de hoy en adelante.
                'puede_registrar': fecha >= hoy,
            })
            if en_mes and (eventos or bloques_dia):
                agenda.append({
                    'fecha': fecha,
                    'etiqueta': f'{DIAS_LARGOS_ES[fecha.weekday()]} {fecha.day}',
                    'eventos': eventos,
                    'bloques': bloques_dia,
                    'puede_registrar': fecha >= hoy,
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
