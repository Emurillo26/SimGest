"""T02: el administrador consulta y modifica la tarifa por hora de cada modalidad."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render

from .models import Bitacora, Modalidad, TarifaModalidad
from .permisos import modulo_requerido


def _ip(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _campo(etiqueta):
    return forms.DecimalField(
        label=etiqueta, max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
        error_messages={'required': 'Indica la tarifa.', 'min_value': 'La tarifa debe ser mayor a cero.'},
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )


class TarifasModalidadForm(forms.Form):
    virtual = _campo('Tarifa por hora, modalidad virtual (₡)')
    presencial = _campo('Tarifa por hora, modalidad presencial (₡)')


@modulo_requerido('tarifas_modalidad')
def tarifas_modalidad_view(request):
    actuales = {t.modalidad: t.monto_hora for t in TarifaModalidad.objects.all()}

    if request.method == 'POST':
        form = TarifasModalidadForm(request.POST)
        if form.is_valid():
            cambios = 0
            for modalidad, clave in ((Modalidad.VIRTUAL, 'virtual'), (Modalidad.PRESENCIAL, 'presencial')):
                nuevo = form.cleaned_data[clave]
                anterior = actuales.get(modalidad)
                if anterior is not None and anterior == nuevo:
                    continue
                TarifaModalidad.objects.update_or_create(modalidad=modalidad, defaults={'monto_hora': nuevo})
                Bitacora.objects.create(
                    usuario=request.user, realizado_por=request.user,
                    accion='Cambio de tarifa por modalidad', campo_modificado=f'Tarifa {modalidad}',
                    valor_anterior='' if anterior is None else str(anterior), valor_nuevo=str(nuevo),
                    ip_origen=_ip(request),
                )
                cambios += 1
            if cambios:
                messages.success(request, 'Tarifas actualizadas. Se aplican a las solicitudes nuevas; las anteriores conservan la suya.')
            else:
                messages.info(request, 'No hubo cambios en las tarifas.')
            return redirect('simulactores:tarifas_modalidad')
    else:
        form = TarifasModalidadForm(initial={
            'virtual': actuales.get(Modalidad.VIRTUAL), 'presencial': actuales.get(Modalidad.PRESENCIAL),
        })

    return render(request, 'simulactores/tarifas_modalidad.html', {'form': form})