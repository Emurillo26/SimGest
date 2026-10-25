from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notificacion
from .permisos import modulo_requerido


@modulo_requerido('notificaciones')
def notificaciones_view(request):
    """HU-30: bandeja de notificaciones del usuario (todas o solo las no leídas)."""
    notificaciones = request.user.notificaciones.order_by('-fecha', '-id_notificacion')

    filtro_estado = request.GET.get('estado', '')
    if filtro_estado == 'no_leidas':
        notificaciones = notificaciones.filter(leido=False)
    else:
        filtro_estado = ''

    paginador = Paginator(notificaciones, 10)
    pagina = paginador.get_page(request.GET.get('pagina'))

    return render(request, 'simulactores/notificaciones.html', {
        'notificaciones': pagina,
        'filtro_estado': filtro_estado,
        'total_no_leidas': request.user.notificaciones.filter(leido=False).count(),
    })


@modulo_requerido('notificaciones')
def abrir_notificacion_view(request, notificacion_id):
    """HU-30 escenario 3: al abrir una notificación se marca como leída y se va a su destino."""
    notificacion = get_object_or_404(Notificacion, pk=notificacion_id, usuario=request.user)
    if not notificacion.leido:
        notificacion.leido = True
        notificacion.save(update_fields=['leido'])

    destino = notificacion.enlace
    if destino.startswith('/') and not destino.startswith('//'):
        return redirect(destino)
    return redirect('simulactores:notificaciones')


@modulo_requerido('notificaciones')
@require_POST
def marcar_notificacion_leida_view(request, notificacion_id):
    notificacion = get_object_or_404(Notificacion, pk=notificacion_id, usuario=request.user)
    if not notificacion.leido:
        notificacion.leido = True
        notificacion.save(update_fields=['leido'])
    return redirect('simulactores:notificaciones')


@modulo_requerido('notificaciones')
@require_POST
def marcar_todas_leidas_view(request):
    actualizadas = request.user.notificaciones.filter(leido=False).update(leido=True)
    if actualizadas:
        messages.success(request, 'Todas tus notificaciones quedaron marcadas como leídas.')
    return redirect('simulactores:notificaciones')
