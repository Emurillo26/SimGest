"""Vistas para asignar y reasignar actores (HU-44 y HU-45)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import asignacion_service as servicio
from .asignacion_service import AsignacionError
from .models import Solicitud
from .permisos import modulo_requerido


def _ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _volver(solicitud):
    return redirect('simulactores:solicitud_admin_detalle', solicitud_uuid=solicitud.uuid)


@modulo_requerido('gestion_solicitudes')
@require_http_methods(['GET', 'POST'])
def asignar_actor_view(request, solicitud_uuid):
    """HU-44: el administrador elige un actor disponible para la solicitud."""
    solicitud = get_object_or_404(Solicitud.objects.select_related('cliente', 'escenario'), uuid=solicitud_uuid)

    if solicitud.estado not in servicio.ESTADOS_PARA_ASIGNAR or servicio.cupos_libres(solicitud) == 0:
        messages.error(
            request,
            'Esta solicitud no admite asignar un actor en este momento '
            f'(estado: {solicitud.estado}). Debe estar Aprobada y con cupos libres.',
        )
        return _volver(solicitud)

    if request.method == 'POST':
        try:
            servicio.asignar_actor(
                solicitud, request.POST.get('actor'),
                realizado_por=request.user, ip_origen=_ip(request),
            )
        except AsignacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, 'Actor asignado correctamente. Se notificó al actor y al cliente.')
            return _volver(solicitud)

    return _pantalla(request, solicitud, modo='asignar')


@modulo_requerido('gestion_solicitudes')
@require_http_methods(['GET', 'POST'])
def reasignar_actor_view(request, solicitud_uuid):
    """HU-45: el administrador reemplaza a un actor ya asignado."""
    solicitud = get_object_or_404(Solicitud.objects.select_related('cliente', 'escenario'), uuid=solicitud_uuid)

    vigentes = list(servicio.asignaciones_vigentes(solicitud))
    if solicitud.estado not in servicio.ESTADOS_PARA_REASIGNAR or not vigentes:
        messages.error(
            request,
            'Esta solicitud no tiene un actor asignado que se pueda reemplazar '
            f'(estado: {solicitud.estado}).',
        )
        return _volver(solicitud)

    if request.method == 'POST':
        try:
            servicio.reasignar_actor(
                solicitud, request.POST.get('asignacion'), request.POST.get('actor'),
                realizado_por=request.user, ip_origen=_ip(request),
            )
        except AsignacionError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, 'Actor reasignado correctamente. Se notificó al cliente y al actor.')
            return _volver(solicitud)

    return _pantalla(request, solicitud, modo='reasignar', vigentes=vigentes)


def _pantalla(request, solicitud, modo, vigentes=()):
    # Al reasignar, el actor que sale no se vuelve a ofrecer.
    salientes = [a.actor_id for a in vigentes]
    filas = servicio.candidatos(solicitud, excluir_actor_ids=salientes)
    hay_disponibles = any(f['disponible'] for f in filas)
    return render(request, 'simulactores/asignar_actor.html', {
        'solicitud': solicitud,
        'modo': modo,
        'filas': filas,
        'hay_disponibles': hay_disponibles,
        'mensaje_sin_actores': servicio.MENSAJE_SIN_ACTORES,
        'vigentes': vigentes,
        'asignacion_elegida': request.POST.get('asignacion') or (str(vigentes[0].pk) if len(vigentes) == 1 else ''),
        'actor_elegido': request.POST.get('actor', ''),
    })
