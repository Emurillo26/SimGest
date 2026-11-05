"""Pagos a actores (HU-43): cálculo del monto pendiente y registro con trazabilidad."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction

from .models import Actor, Asignacion, Pago, TarifaActor
from .utils import registrar_cambios

CENTAVOS = Decimal('0.01')


class PagoError(Exception):
    """Error de negocio que se muestra tal cual al administrador."""


# --- Monto pendiente --------------------------------------------------------

def _horas(asignacion):
    """Horas reales si ya se registraron; si no, las horas agendadas."""
    reales = asignacion.horas_ejecutadas()
    if reales is not None:
        return Decimal(str(round(reales, 4)))
    solicitud = asignacion.solicitud
    inicio = datetime.combine(solicitud.fecha_evento, solicitud.hora_inicio)
    fin = datetime.combine(solicitud.fecha_evento, solicitud.hora_fin)
    return Decimal(str((fin - inicio).total_seconds() / 3600))


def monto_asignacion(asignacion):
    """Cuánto se le debe al actor por una simulación ejecutada."""
    actor = asignacion.actor
    vigente = TarifaActor.vigente_en(actor, asignacion.solicitud.fecha_evento)
    if asignacion.tarifa_aplicada is not None:
        tarifa = asignacion.tarifa_aplicada
    else:
        tarifa = vigente.monto if vigente else actor.tarifa
    tipo = vigente.tipo_tarifa if vigente else actor.tipo_tarifa

    if tarifa is None:
        return Decimal('0.00')
    if tipo == Actor.TipoTarifa.POR_HORA:
        return (Decimal(tarifa) * _horas(asignacion)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return Decimal(tarifa).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def asignaciones_ejecutadas(actor, mes, anio):
    return list(
        Asignacion.objects
        .filter(
            actor=actor,
            estado=Asignacion.Estado.EJECUTADA,
            solicitud__fecha_evento__month=mes,
            solicitud__fecha_evento__year=anio,
        )
        .select_related('solicitud', 'actor')
        .order_by('solicitud__fecha_evento', 'solicitud__hora_inicio')
    )


def monto_pendiente(actor, mes, anio):
    """(total, [(asignacion, monto), ...]) de las simulaciones ejecutadas del período."""
    filas = [(a, monto_asignacion(a)) for a in asignaciones_ejecutadas(actor, mes, anio)]
    return sum((m for _, m in filas), Decimal('0.00')), filas


def pago_del_periodo(actor, mes, anio):
    return Pago.objects.filter(actor=actor, periodo_mes=mes, periodo_anio=anio).first()


# --- Registro ---------------------------------------------------------------

def _periodo(mes, anio):
    return f'{int(mes):02d}/{anio}'


def registrar_pago(*, actor, mes, anio, monto, fecha_pago, metodo, referencia,
                   realizado_por=None, ip_origen=None):
    """Registra el pago mensual de un actor. Devuelve el Pago en estado Pagado."""
    try:
        with transaction.atomic():
            existente = (
                Pago.objects.select_for_update()
                .filter(actor=actor, periodo_mes=mes, periodo_anio=anio).first()
            )
            if existente and existente.estado == Pago.Estado.PAGADO:
                raise PagoError(
                    f'El período {_periodo(mes, anio)} de {actor.usuario.nombre} ya está pagado. '
                    'No se puede registrar el pago otra vez.'
                )

            pendiente, filas = monto_pendiente(actor, mes, anio)
            if not filas:
                raise PagoError(
                    f'{actor.usuario.nombre} no tiene monto pendiente en {_periodo(mes, anio)}: '
                    'no hay simulaciones ejecutadas en ese período.'
                )

            estado_anterior = existente.estado if existente else None
            pago = existente or Pago(actor=actor, periodo_mes=mes, periodo_anio=anio)
            pago.monto_total = monto
            pago.fecha_pago = fecha_pago
            pago.metodo_pago = metodo
            pago.referencia = referencia
            pago.estado = Pago.Estado.PAGADO
            pago.save()
            pago.asignaciones.set([a for a, _ in filas])

            registrar_cambios(
                actor.usuario, 'Pago registrado',
                [
                    ('periodo', None, _periodo(mes, anio)),
                    ('estado_pago', estado_anterior, Pago.Estado.PAGADO),
                    ('monto_pendiente_calculado', None, pendiente),
                    ('monto_pagado', None, monto),
                    ('metodo_pago', None, metodo),
                    ('referencia', None, referencia),
                    ('fecha_pago', None, fecha_pago),
                ],
                realizado_por=realizado_por, ip_origen=ip_origen,
            )
    except IntegrityError:
        # Dos administradores registrando el mismo período a la vez.
        raise PagoError('Ese período ya tiene un pago registrado. Actualiza la página.')
    return pago


# --- Modificar o anular -----------------------------------------------------

MENSAJE_CONFIRMACION = (
    'Este pago ya está confirmado como Pagado. Debes confirmar que quieres continuar.'
)


def _exigir_confirmacion(pago, confirmado):
    if pago.estado == Pago.Estado.PAGADO and not confirmado:
        raise PagoError(MENSAJE_CONFIRMACION)


def modificar_pago(pago, *, monto, fecha_pago, metodo, referencia, confirmado,
                   realizado_por=None, ip_origen=None):
    with transaction.atomic():
        pago = Pago.objects.select_for_update().select_related('actor__usuario').get(pk=pago.pk)
        if pago.estado == Pago.Estado.ANULADO:
            raise PagoError('Un pago anulado no se puede modificar.')
        _exigir_confirmacion(pago, confirmado)

        nuevos = {
            'monto_total': monto, 'fecha_pago': fecha_pago,
            'metodo_pago': metodo, 'referencia': referencia,
        }
        cambios = []
        for campo, nuevo in nuevos.items():
            anterior = getattr(pago, campo)
            if anterior != nuevo:
                cambios.append((campo, anterior, nuevo))
                setattr(pago, campo, nuevo)
        if not cambios:
            raise PagoError('No hiciste ningún cambio en el pago.')

        pago.save()
        registrar_cambios(
            pago.actor.usuario, 'Pago modificado', cambios,
            realizado_por=realizado_por, ip_origen=ip_origen,
        )
    return pago


def anular_pago(pago, *, motivo, confirmado, realizado_por=None, ip_origen=None):
    motivo = (motivo or '').strip()
    with transaction.atomic():
        pago = Pago.objects.select_for_update().select_related('actor__usuario').get(pk=pago.pk)
        if pago.estado == Pago.Estado.ANULADO:
            raise PagoError('Este pago ya estaba anulado.')
        _exigir_confirmacion(pago, confirmado)
        if not motivo:
            raise PagoError('Indica el motivo de la anulación.')

        anterior = pago.estado
        pago.estado = Pago.Estado.ANULADO
        pago.save(update_fields=['estado'])
        registrar_cambios(
            pago.actor.usuario, 'Pago anulado',
            [('estado_pago', anterior, Pago.Estado.ANULADO), ('motivo_anulacion', None, motivo)],
            realizado_por=realizado_por, ip_origen=ip_origen,
        )
    return pago
