from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Categoria, Escenario, Solicitud, TipoSimulacion
from .permisos import modulo_requerido
from .utils import registrar_cambios


ESTADOS_SOLICITUD_ACTIVA = [
    Solicitud.Estado.PENDIENTE,
    Solicitud.Estado.EN_REVISION,
    Solicitud.Estado.APROBADA,
    Solicitud.Estado.ACTOR_ASIGNADO,
    Solicitud.Estado.CONFIRMADA,
]


def _ip_del_request(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')


@modulo_requerido('biblioteca_escenarios')
def biblioteca_escenarios_hu24_view(request):
    """
    HU-24:
    - Por defecto muestra únicamente escenarios activos.
    - Permite consultar escenarios archivados para poder reactivarlos.
    - Mantiene los filtros existentes de categoría y tipo de simulación.
    """

    filtro_categoria = request.GET.get('categoria', '').strip()
    filtro_tipo = request.GET.get('tipo', '').strip()
    filtro_estado = request.GET.get(
        'estado',
        Escenario.Estado.ACTIVO
    ).strip()

    estados_validos = [
        Escenario.Estado.ACTIVO,
        Escenario.Estado.ARCHIVADO,
        'Todos',
    ]

    if filtro_estado not in estados_validos:
        filtro_estado = Escenario.Estado.ACTIVO

    escenarios = (
        Escenario.objects
        .prefetch_related('categorias')
        .order_by('nombre')
    )

    if filtro_estado != 'Todos':
        escenarios = escenarios.filter(
            estado=filtro_estado
        )

    if filtro_categoria.isdigit():
        escenarios = escenarios.filter(
            categorias__pk=int(filtro_categoria)
        )
    else:
        filtro_categoria = ''

    if filtro_tipo in TipoSimulacion.values:
        escenarios = escenarios.filter(
            tipo=filtro_tipo
        )
    else:
        filtro_tipo = ''

    escenarios = escenarios.distinct()

    return render(
        request,
        'simulactores/escenarios.html',
        {
            'escenarios': escenarios,
            'categorias': Categoria.objects.order_by('nombre'),
            'tipos': TipoSimulacion.choices,
            'filtro_categoria': filtro_categoria,
            'filtro_tipo': filtro_tipo,
            'filtro_estado': filtro_estado,
            'hay_filtros': bool(
                filtro_categoria
                or filtro_tipo
                or filtro_estado != Escenario.Estado.ACTIVO
            ),
            'biblioteca_vacia': not Escenario.objects.exists(),
        }
    )


@modulo_requerido('biblioteca_escenarios')
def detalle_escenario_hu24_view(request, escenario_id):
    """
    Muestra el detalle del escenario y la cantidad de solicitudes activas.
    """

    escenario = get_object_or_404(
        Escenario.objects.prefetch_related('categorias'),
        pk=escenario_id
    )

    solicitudes_activas = escenario.solicitudes.filter(
        estado__in=ESTADOS_SOLICITUD_ACTIVA
    ).count()

    return render(
        request,
        'simulactores/escenario_detalle.html',
        {
            'escenario': escenario,
            'solicitudes_activas': solicitudes_activas,
        }
    )


@modulo_requerido('biblioteca_escenarios')
@require_POST
def archivar_escenario_view(request, escenario_id):
    """
    HU-24:
    Archiva un escenario únicamente cuando no tiene solicitudes activas.
    """

    escenario = get_object_or_404(
        Escenario,
        pk=escenario_id
    )

    if escenario.estado == Escenario.Estado.ARCHIVADO:
        messages.info(
            request,
            'Este escenario ya se encuentra archivado.'
        )

        return redirect(
            'simulactores:detalle_escenario',
            escenario_id=escenario.pk
        )

    solicitudes_activas = escenario.solicitudes.filter(
        estado__in=ESTADOS_SOLICITUD_ACTIVA
    ).count()

    if solicitudes_activas > 0:
        messages.error(
            request,
            (
                f'No se puede archivar «{escenario.nombre}» porque '
                f'tiene {solicitudes_activas} solicitud(es) activa(s) '
                'asociada(s).'
            )
        )

        return redirect(
            'simulactores:detalle_escenario',
            escenario_id=escenario.pk
        )

    estado_anterior = escenario.estado

    escenario.estado = Escenario.Estado.ARCHIVADO

    escenario.save(
        update_fields=['estado']
    )

    registrar_cambios(
        request.user,
        f'Archivado de escenario: {escenario.nombre}'[:150],
        [
            (
                'estado',
                estado_anterior,
                escenario.estado
            )
        ],
        realizado_por=request.user,
        ip_origen=_ip_del_request(request),
    )

    messages.success(
        request,
        f'Escenario «{escenario.nombre}» archivado correctamente.'
    )

    return redirect(
        'simulactores:biblioteca_escenarios'
    )


@modulo_requerido('biblioteca_escenarios')
@require_POST
def reactivar_escenario_view(request, escenario_id):
    """
    HU-24:
    Reactiva un escenario que se encontraba archivado.
    """

    escenario = get_object_or_404(
        Escenario,
        pk=escenario_id
    )

    if escenario.estado == Escenario.Estado.ACTIVO:
        messages.info(
            request,
            'Este escenario ya se encuentra activo.'
        )

        return redirect(
            'simulactores:detalle_escenario',
            escenario_id=escenario.pk
        )

    estado_anterior = escenario.estado

    escenario.estado = Escenario.Estado.ACTIVO

    escenario.save(
        update_fields=['estado']
    )

    registrar_cambios(
        request.user,
        f'Reactivación de escenario: {escenario.nombre}'[:150],
        [
            (
                'estado',
                estado_anterior,
                escenario.estado
            )
        ],
        realizado_por=request.user,
        ip_origen=_ip_del_request(request),
    )

    messages.success(
        request,
        f'Escenario «{escenario.nombre}» reactivado correctamente.'
    )

    return redirect(
        'simulactores:detalle_escenario',
        escenario_id=escenario.pk
    )