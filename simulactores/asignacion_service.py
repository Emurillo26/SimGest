"""Lógica de asignación de actores (HU-42, HU-44 y HU-45).

Se deja separada de las vistas para que otras historias (por ejemplo, la
consulta de disponibilidad del administrador o el rechazo del actor) puedan
reutilizar las mismas reglas.
"""
from collections import namedtuple
from datetime import date

from django.db import transaction

from .models import Actor, Asignacion, Disponibilidad, Solicitud, TarifaActor
from .utils import notificar, registrar_cambios

ESTADOS_VIGENTES = (Asignacion.Estado.PENDIENTE, Asignacion.Estado.CONFIRMADA)
ESTADOS_PARA_ASIGNAR = (Solicitud.Estado.APROBADA, Solicitud.Estado.ACTOR_ASIGNADO)
ESTADOS_PARA_REASIGNAR = (Solicitud.Estado.ACTOR_ASIGNADO, Solicitud.Estado.CONFIRMADA)

MENSAJE_SIN_ACTORES = (
    'No hay actores disponibles. Prueba revisando fechas alternativas '
    'para esta simulación.'
)

Disponibilidad_actor = namedtuple('Disponibilidad_actor', 'disponible motivo')


class AsignacionError(Exception):
    """Error de negocio que se le muestra tal cual al administrador."""


# --- HU-42: validar la disponibilidad ---------------------------------------

def validar_disponibilidad(actor, solicitud):
    """Dice si el actor puede cubrir la fecha y el horario de la solicitud.

    Reglas, en este orden:
      1. El actor debe estar activo.
      2. No puede tener un bloqueo que se cruce con el horario.
      3. Debe tener un bloque «Disponible» que cubra todo el horario.
      4. No puede tener otra simulación asignada que se cruce (conflicto de agenda).
    """
    if actor.estado != Actor.EstadoActor.ACTIVO:
        return Disponibilidad_actor(False, 'El actor está inactivo.')

    bloques = Disponibilidad.objects.filter(actor=actor, fecha=solicitud.fecha_evento)

    if bloques.filter(
        tipo_bloque=Disponibilidad.TipoBloque.BLOQUEADO,
        hora_inicio__lt=solicitud.hora_fin,
        hora_fin__gt=solicitud.hora_inicio,
    ).exists():
        return Disponibilidad_actor(False, 'El actor bloqueó esa fecha u horario.')

    if not bloques.filter(
        tipo_bloque=Disponibilidad.TipoBloque.DISPONIBLE,
        hora_inicio__lte=solicitud.hora_inicio,
        hora_fin__gte=solicitud.hora_fin,
    ).exists():
        return Disponibilidad_actor(
            False, 'El actor no tiene disponibilidad registrada para esa fecha y hora.'
        )

    conflicto = Asignacion.objects.filter(
        actor=actor,
        estado__in=ESTADOS_VIGENTES,
        solicitud__fecha_evento=solicitud.fecha_evento,
        solicitud__hora_inicio__lt=solicitud.hora_fin,
        solicitud__hora_fin__gt=solicitud.hora_inicio,
    ).exclude(solicitud=solicitud).exclude(
        solicitud__estado=Solicitud.Estado.CANCELADA
    ).select_related('solicitud').first()
    if conflicto:
        return Disponibilidad_actor(
            False,
            f'Conflicto de agenda: ya tiene la simulación {conflicto.solicitud.numero_solicitud} '
            'en esa fecha y hora.',
        )

    return Disponibilidad_actor(True, '')


# --- Consultas de apoyo ------------------------------------------------------

def asignaciones_vigentes(solicitud):
    return solicitud.asignaciones.filter(estado__in=ESTADOS_VIGENTES).select_related('actor__usuario')


def cupos_libres(solicitud):
    return max(solicitud.cantidad_interpretes - asignaciones_vigentes(solicitud).count(), 0)


def edad_de(actor):
    if not actor.fecha_nacimiento:
        return None
    hoy = date.today()
    nac = actor.fecha_nacimiento
    return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))


def candidatos(solicitud, excluir_actor_ids=()):
    """Actores activos con su veredicto de disponibilidad para la solicitud.

    No se ofrecen los que ya cubren la solicitud ni los que la rechazaron.
    """
    descartados = set(excluir_actor_ids) | set(
        solicitud.asignaciones.filter(
            estado__in=ESTADOS_VIGENTES + (Asignacion.Estado.RECHAZADA,)
        ).values_list('actor_id', flat=True)
    )
    filas = []
    actores = (
        Actor.objects.filter(estado=Actor.EstadoActor.ACTIVO)
        .exclude(pk__in=descartados)
        .select_related('usuario').prefetch_related('habilidades')
        .order_by('usuario__nombre')
    )
    for actor in actores:
        veredicto = validar_disponibilidad(actor, solicitud)
        filas.append({
            'actor': actor,
            'edad': edad_de(actor),
            'habilidades': [h.nombre for h in actor.habilidades.all()],
            'disponible': veredicto.disponible,
            'motivo': veredicto.motivo,
        })
    # Primero los disponibles.
    filas.sort(key=lambda f: (not f['disponible'], f['actor'].usuario.nombre))
    return filas


def _tarifa_para(actor, solicitud):
    vigente = TarifaActor.vigente_en(actor, solicitud.fecha_evento)
    return vigente.monto if vigente else actor.tarifa


def _nombre(actor):
    return actor.usuario.nombre


# --- HU-44: asignar ----------------------------------------------------------

def asignar_actor(solicitud, actor_id, realizado_por=None, ip_origen=None):
    """Asigna un actor disponible a la solicitud. Devuelve la Asignacion creada.

    Si dos administradores asignan al mismo actor a la vez, gana el primero que
    guarda: el segundo ve el conflicto de agenda porque se vuelve a validar
    dentro de la transacción, con la fila del actor bloqueada.
    """
    with transaction.atomic():
        solicitud = Solicitud.objects.select_for_update().select_related('cliente').get(pk=solicitud.pk)

        if solicitud.estado not in ESTADOS_PARA_ASIGNAR:
            raise AsignacionError(
                f'No se puede asignar un actor: la solicitud está en estado «{solicitud.estado}». '
                'Debe estar Aprobada.'
            )
        if cupos_libres(solicitud) == 0:
            raise AsignacionError('Esta solicitud ya tiene todos los actores que necesita.')

        actor = _actor_validado(solicitud, actor_id)
        asignacion = Asignacion.objects.create(
            solicitud=solicitud, actor=actor,
            estado=Asignacion.Estado.PENDIENTE,
            tarifa_aplicada=_tarifa_para(actor, solicitud),
        )

        cambios = [('actor_asignado', None, _nombre(actor))]
        estado_anterior = solicitud.estado
        if cupos_libres(solicitud) == 0 and solicitud.estado != Solicitud.Estado.ACTOR_ASIGNADO:
            solicitud.estado = Solicitud.Estado.ACTOR_ASIGNADO
            solicitud.save()
            cambios.append(('estado', estado_anterior, solicitud.estado))

        registrar_cambios(
            solicitud.cliente, 'Actor asignado por administrador', cambios,
            realizado_por=realizado_por, ip_origen=ip_origen,
        )

    # Al actor lo avisa la señal de HU-30; aquí se avisa al cliente.
    notificar(
        solicitud.cliente,
        f'Ya asignamos un actor a tu solicitud {solicitud.numero_solicitud}.',
        asunto='Actor asignado a tu simulación',
    )
    return asignacion


# --- HU-45: reasignar --------------------------------------------------------

def reasignar_actor(solicitud, asignacion_id, actor_id, realizado_por=None, ip_origen=None):
    """Reemplaza a un actor ya asignado por otro disponible.

    La asignación anterior queda Cancelada (el actor anterior queda libre y la
    señal de HU-30 le avisa) y se crea una nueva Pendiente para el reemplazo.
    """
    with transaction.atomic():
        solicitud = Solicitud.objects.select_for_update().select_related('cliente').get(pk=solicitud.pk)

        if solicitud.estado not in ESTADOS_PARA_REASIGNAR:
            raise AsignacionError(
                f'No se puede reasignar: la solicitud está en estado «{solicitud.estado}».'
            )
        anterior = solicitud.asignaciones.filter(
            pk=asignacion_id, estado__in=ESTADOS_VIGENTES
        ).select_related('actor__usuario').first()
        if not anterior:
            raise AsignacionError('Selecciona el actor que quieres reemplazar.')

        # El actor que sale no puede volver a elegirse como su propio reemplazo.
        if str(anterior.actor_id) == str(actor_id):
            raise AsignacionError('Elige un actor distinto al que vas a reemplazar.')

        nuevo = _actor_validado(solicitud, actor_id)

        anterior.estado = Asignacion.Estado.CANCELADA
        anterior.save()
        asignacion = Asignacion.objects.create(
            solicitud=solicitud, actor=nuevo,
            estado=Asignacion.Estado.PENDIENTE,
            tarifa_aplicada=_tarifa_para(nuevo, solicitud),
        )

        cambios = [('actor_asignado', _nombre(anterior.actor), _nombre(nuevo))]
        # El reemplazo debe confirmar su participación: vuelve a «Actor Asignado».
        if solicitud.estado != Solicitud.Estado.ACTOR_ASIGNADO:
            cambios.append(('estado', solicitud.estado, Solicitud.Estado.ACTOR_ASIGNADO))
            solicitud.estado = Solicitud.Estado.ACTOR_ASIGNADO
            solicitud.save()

        registrar_cambios(
            solicitud.cliente, 'Actor reasignado por administrador', cambios,
            realizado_por=realizado_por, ip_origen=ip_origen,
        )

    notificar(
        solicitud.cliente,
        f'Cambiamos el actor de tu solicitud {solicitud.numero_solicitud}. '
        'Tu simulación sigue en pie con el mismo horario.',
        asunto='Cambio de actor en tu simulación',
    )
    return asignacion


def _actor_validado(solicitud, actor_id):
    """Bloquea la fila del actor y vuelve a validar su disponibilidad (HU-42)."""
    try:
        actor = Actor.objects.select_for_update().select_related('usuario').get(pk=actor_id)
    except (Actor.DoesNotExist, ValueError, TypeError):
        raise AsignacionError('Selecciona un actor de la lista.')

    if solicitud.asignaciones.filter(actor=actor, estado__in=ESTADOS_VIGENTES).exists():
        raise AsignacionError(f'{_nombre(actor)} ya está asignado a esta solicitud.')

    veredicto = validar_disponibilidad(actor, solicitud)
    if not veredicto.disponible:
        raise AsignacionError(f'No se puede asignar a {_nombre(actor)}. {veredicto.motivo}')
    return actor
