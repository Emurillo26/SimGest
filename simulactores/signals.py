"""Avisos automáticos al actor (HU-30).

Se disparan solos cuando cambian los datos, así que las demás historias
(asignar, reasignar, editar o cancelar solicitudes) no tienen que llamarlos.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from .models import Asignacion, Solicitud
from .utils import notificar

ESTADOS_ASIGNACION_VIGENTE = (Asignacion.Estado.PENDIENTE, Asignacion.Estado.CONFIRMADA)
CAMPOS_SOLICITUD = ('fecha_evento', 'hora_inicio', 'hora_fin', 'escenario_id', 'estado')


def _resumen(solicitud):
    return (
        f'{solicitud.numero_solicitud} ({solicitud.tipo_simulacion}) el '
        f'{solicitud.fecha_evento.strftime("%d/%m/%Y")} de '
        f'{solicitud.hora_inicio.strftime("%H:%M")} a {solicitud.hora_fin.strftime("%H:%M")}'
    )


def _enlace_actor():
    return reverse('simulactores:dashboard_actor')


# --- Asignaciones -----------------------------------------------------------

@receiver(pre_save, sender=Asignacion)
def recordar_estado_previo_asignacion(sender, instance, **kwargs):
    instance._estado_previo = None
    if instance.pk:
        instance._estado_previo = (
            Asignacion.objects.filter(pk=instance.pk).values_list('estado', flat=True).first()
        )


@receiver(post_save, sender=Asignacion)
def avisar_cambio_de_asignacion(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    usuario = instance.actor.usuario
    solicitud = instance.solicitud

    # Escenario 1: nueva asignación.
    if created and instance.estado in ESTADOS_ASIGNACION_VIGENTE:
        notificar(
            usuario,
            f'Se te asignó una nueva simulación: {_resumen(solicitud)}. Confírmala o recházala desde tu panel.',
            asunto='Nueva simulación asignada',
            enlace=_enlace_actor(),
        )
        return

    # Escenario 2: la asignación se cancela (por ejemplo, al reasignar a otro actor).
    previo = getattr(instance, '_estado_previo', None)
    if (
        not created
        and previo in ESTADOS_ASIGNACION_VIGENTE
        and instance.estado == Asignacion.Estado.CANCELADA
    ):
        notificar(
            usuario,
            f'Tu asignación a la simulación {_resumen(solicitud)} fue cancelada. Ya no debes asistir.',
            asunto='Asignación cancelada',
            enlace=_enlace_actor(),
        )


# --- Solicitudes ------------------------------------------------------------

@receiver(pre_save, sender=Solicitud)
def recordar_valores_previos_solicitud(sender, instance, **kwargs):
    instance._valores_previos = None
    if instance.pk:
        instance._valores_previos = (
            Solicitud.objects.filter(pk=instance.pk).values(*CAMPOS_SOLICITUD).first()
        )


@receiver(post_save, sender=Solicitud)
def avisar_cambios_de_solicitud(sender, instance, created, raw=False, **kwargs):
    previos = getattr(instance, '_valores_previos', None)
    if raw or created or not previos:
        return

    asignaciones = instance.asignaciones.filter(
        estado__in=ESTADOS_ASIGNACION_VIGENTE
    ).select_related('actor__usuario')
    if not asignaciones.exists():
        return

    cancelada = (
        previos['estado'] != Solicitud.Estado.CANCELADA
        and instance.estado == Solicitud.Estado.CANCELADA
    )

    cambios = []
    if previos['fecha_evento'] != instance.fecha_evento:
        cambios.append('la fecha')
    if previos['hora_inicio'] != instance.hora_inicio or previos['hora_fin'] != instance.hora_fin:
        cambios.append('el horario')
    if previos['escenario_id'] != instance.escenario_id:
        cambios.append('el escenario')

    if not cancelada and not cambios:
        return

    for asignacion in asignaciones:
        if cancelada:
            notificar(
                asignacion.actor.usuario,
                f'La simulación {_resumen(instance)} fue cancelada. Ya no debes asistir.',
                asunto='Simulación cancelada',
                enlace=_enlace_actor(),
            )
        else:
            notificar(
                asignacion.actor.usuario,
                f'La simulación {instance.numero_solicitud} tuvo cambios en {" y ".join(cambios)}. '
                f'Datos actuales: {_resumen(instance)}.',
                asunto='Cambios en tu simulación',
                enlace=_enlace_actor(),
            )
