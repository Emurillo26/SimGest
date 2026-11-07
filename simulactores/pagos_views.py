"""HU-43: el administrador registra, modifica y anula pagos a actores.
HU-41: el administrador genera el reporte mensual de horas ejecutadas por
actor para preparar el cálculo de esos pagos."""
import datetime
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import pagos_service as servicio
from .models import Actor, Pago
from .pagos_service import PagoError
from .permisos import modulo_requerido

MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
    (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'),
    (12, 'Diciembre'),
]
NOMBRE_MES = dict(MESES)
ANIO_MIN, ANIO_MAX = 2020, 2100


def _ip(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class _DatosDelPago(forms.Form):
    """Campos comunes al registrar y al modificar."""

    monto = forms.DecimalField(
        label='Monto pagado (₡)', max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
        error_messages={'required': 'Indica el monto.'},
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    fecha_pago = forms.DateField(
        label='Fecha del pago',
        error_messages={'required': 'Indica la fecha del pago.'},
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
    )
    metodo_pago = forms.ChoiceField(
        label='Método de pago',
        choices=[('', 'Selecciona…')] + list(Pago.MetodoPago.choices),
        error_messages={'required': 'Selecciona el método de pago.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    referencia = forms.CharField(
        label='Referencia', max_length=100,
        error_messages={'required': 'Indica la referencia del pago.'},
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº de transferencia, comprobante…'}),
    )

    def clean_fecha_pago(self):
        fecha = self.cleaned_data['fecha_pago']
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha del pago no puede ser futura.')
        return fecha


class PagoForm(_DatosDelPago):
    actor = forms.ModelChoiceField(
        label='Actor', queryset=Actor.objects.none(), empty_label='Selecciona…',
        error_messages={'required': 'Selecciona el actor.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    periodo_mes = forms.TypedChoiceField(
        label='Mes', choices=[('', 'Selecciona…')] + MESES, coerce=int,
        error_messages={'required': 'Selecciona el mes.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    periodo_anio = forms.IntegerField(
        label='Año', min_value=ANIO_MIN, max_value=ANIO_MAX,
        error_messages={'required': 'Indica el año.'},
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    field_order = ['actor', 'periodo_mes', 'periodo_anio', 'monto', 'fecha_pago', 'metodo_pago', 'referencia']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['actor'].queryset = (
            Actor.objects.select_related('usuario').order_by('usuario__nombre'))
        self.fields['actor'].label_from_instance = lambda a: a.usuario.nombre


class PagoEdicionForm(_DatosDelPago):
    confirmo = forms.BooleanField(required=False)


class ReportePeriodoForm(forms.Form):
    """HU-41: selección del mes/año sobre el que se genera el reporte."""

    mes = forms.TypedChoiceField(
        label='Mes', choices=[('', 'Selecciona…')] + MESES, coerce=int,
        error_messages={'required': 'Selecciona el mes.', 'invalid_choice': 'Selecciona un mes válido.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    anio = forms.IntegerField(
        label='Año', min_value=ANIO_MIN, max_value=ANIO_MAX,
        error_messages={'required': 'Indica el año.'},
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )


def _contexto_pendiente(actor, mes, anio):
    total, filas = servicio.monto_pendiente(actor, mes, anio)
    existente = servicio.pago_del_periodo(actor, mes, anio)
    return {
        'actor': actor, 'mes': NOMBRE_MES[mes], 'anio': anio,
        'total': total, 'filas': filas, 'pago_existente': existente,
    }


def _leer_periodo(datos):
    try:
        actor = Actor.objects.select_related('usuario').get(pk=int(datos.get('actor')))
        mes, anio = int(datos.get('periodo_mes')), int(datos.get('periodo_anio'))
        if 1 <= mes <= 12 and ANIO_MIN <= anio <= ANIO_MAX:
            return actor, mes, anio
    except (TypeError, ValueError, Actor.DoesNotExist):
        pass
    return None


@modulo_requerido('pagos_actores')
def pagos_admin_view(request):
    """Listado de pagos con filtros por actor, mes y año."""
    pagos = Pago.objects.select_related('actor__usuario').order_by(
        '-periodo_anio', '-periodo_mes', 'actor__usuario__nombre')

    actor_id = request.GET.get('actor', '')
    mes = request.GET.get('mes', '')
    anio = request.GET.get('anio', '')
    if actor_id.isdigit():
        pagos = pagos.filter(actor_id=int(actor_id))
    if mes.isdigit():
        pagos = pagos.filter(periodo_mes=int(mes))
    if anio.isdigit():
        pagos = pagos.filter(periodo_anio=int(anio))

    return render(request, 'simulactores/pagos_admin.html', {
        'pagos': pagos,
        'actores': Actor.objects.select_related('usuario').order_by('usuario__nombre'),
        'meses': MESES,
        'filtro': {'actor': actor_id, 'mes': mes, 'anio': anio},
    })


@modulo_requerido('pagos_actores')
def registrar_pago_view(request):
    pendiente = None

    if request.method == 'POST':
        # «Consultar pendiente» solo calcula y rellena el monto; no guarda nada.
        if request.POST.get('accion') == 'calcular':
            inicial = {campo: request.POST.get(campo) for campo in PagoForm.base_fields}
            periodo = _leer_periodo(request.POST)
            if periodo:
                pendiente = _contexto_pendiente(*periodo)
                if pendiente['total'] > 0:
                    inicial['monto'] = pendiente['total']
            form = PagoForm(initial=inicial)
        else:
            form = PagoForm(request.POST)
            if form.is_valid():
                datos = form.cleaned_data
                try:
                    pago = servicio.registrar_pago(
                        actor=datos['actor'], mes=datos['periodo_mes'], anio=datos['periodo_anio'],
                        monto=datos['monto'], fecha_pago=datos['fecha_pago'],
                        metodo=datos['metodo_pago'], referencia=datos['referencia'],
                        realizado_por=request.user, ip_origen=_ip(request),
                    )
                except PagoError as error:
                    form.add_error(None, str(error))
                else:
                    messages.success(
                        request,
                        f'Pago registrado: {pago.actor.usuario.nombre}, '
                        f'{NOMBRE_MES[pago.periodo_mes]} {pago.periodo_anio}.'
                    )
                    return redirect('simulactores:pagos_admin')
            periodo = _leer_periodo(request.POST)
            if periodo:
                pendiente = _contexto_pendiente(*periodo)
    else:
        hoy = timezone.localdate()
        form = PagoForm(initial={
            'periodo_mes': hoy.month, 'periodo_anio': hoy.year, 'fecha_pago': hoy,
            'actor': request.GET.get('actor') or None,
        })

    return render(request, 'simulactores/pago_form.html', {
        'form': form, 'pendiente': pendiente, 'pago': None,
    })


def _pago_o_404(pago_id):
    return get_object_or_404(Pago.objects.select_related('actor__usuario'), pk=pago_id)


@modulo_requerido('pagos_actores')
def editar_pago_view(request, pago_id):
    pago = _pago_o_404(pago_id)
    if pago.estado == Pago.Estado.ANULADO:
        messages.error(request, 'Un pago anulado no se puede modificar.')
        return redirect('simulactores:pagos_admin')

    if request.method == 'POST':
        form = PagoEdicionForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                servicio.modificar_pago(
                    pago, monto=datos['monto'], fecha_pago=datos['fecha_pago'],
                    metodo=datos['metodo_pago'], referencia=datos['referencia'],
                    confirmado=datos['confirmo'],
                    realizado_por=request.user, ip_origen=_ip(request),
                )
            except PagoError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, 'Pago actualizado. El cambio quedó en la bitácora.')
                return redirect('simulactores:pagos_admin')
    else:
        form = PagoEdicionForm(initial={
            'monto': pago.monto_total, 'fecha_pago': pago.fecha_pago,
            'metodo_pago': pago.metodo_pago, 'referencia': pago.referencia,
        })

    return render(request, 'simulactores/pago_form.html', {'form': form, 'pago': pago, 'pendiente': None})


@modulo_requerido('pagos_actores')
def anular_pago_view(request, pago_id):
    pago = _pago_o_404(pago_id)
    error = None
    motivo = ''

    if request.method == 'POST':
        motivo = request.POST.get('motivo', '')
        try:
            servicio.anular_pago(
                pago, motivo=motivo, confirmado=request.POST.get('confirmar') == '1',
                realizado_por=request.user, ip_origen=_ip(request),
            )
        except PagoError as exc:
            error = str(exc)
        else:
            messages.success(request, 'Pago anulado. El motivo quedó en la bitácora.')
            return redirect('simulactores:pagos_admin')

    return render(request, 'simulactores/pago_anular.html', {'pago': pago, 'error': error, 'motivo': motivo})


@modulo_requerido('pagos_actores')
def reporte_mensual_view(request):

    hoy = timezone.localdate()
    generado = bool(request.GET.get('mes'))

    if generado:
        form = ReportePeriodoForm(request.GET)
    else:
        form = ReportePeriodoForm(initial={'mes': hoy.month, 'anio': hoy.year})

    resultado = None
    if generado and form.is_valid():
        resultado = servicio.reporte_mensual(form.cleaned_data['mes'], form.cleaned_data['anio'])
        resultado['mes_nombre'] = NOMBRE_MES[resultado['mes']]

    return render(request, 'simulactores/reporte_mensual.html', {
        'form': form, 'resultado': resultado, 'generado': generado,
    })
