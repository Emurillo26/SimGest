"""HU-37: el administrador administra el perfil operativo de los actores.

Perfil operativo = fecha de nacimiento (edad), género, habilidades, tarifa
(por hora o por evento) y estado activo/inactivo. La disponibilidad se muestra
como resumen y se consulta en «Disponibilidad de actores».
"""
import datetime
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .asignacion_service import ESTADOS_VIGENTES, edad_de
from .models import Actor, Asignacion, Disponibilidad, Habilidad, Solicitud, TarifaActor
from .permisos import modulo_requerido
from .utils import registrar_cambios

EDAD_MINIMA = 18
GENEROS = ['Femenino', 'Masculino', 'Otro']


def _ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class PerfilOperativoForm(forms.ModelForm):

    genero = forms.ChoiceField(
        label='Género', required=True,
        error_messages={'required': 'Selecciona el género del actor.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    tarifa = forms.DecimalField(
        label='Tarifa', required=True, max_digits=10, decimal_places=2,
        error_messages={
            'required': 'Indica la tarifa del actor.',
            'invalid': 'La tarifa debe ser un número (por ejemplo 15000 o 15000.50).',
            'max_digits': 'La tarifa es demasiado grande.',
            'max_decimal_places': 'La tarifa admite como máximo dos decimales.',
            'max_whole_digits': 'La tarifa es demasiado grande.',
        },
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    )
    habilidades = forms.ModelMultipleChoiceField(
        label='Habilidades', required=False, queryset=Habilidad.objects.order_by('nombre'),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Actor
        fields = ['fecha_nacimiento', 'genero', 'habilidades', 'tarifa', 'tipo_tarifa', 'estado']
        labels = {
            'fecha_nacimiento': 'Fecha de nacimiento',
            'tipo_tarifa': 'Tipo de tarifa',
            'estado': 'Estado',
        }
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'tipo_tarifa': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }
        error_messages = {
            'fecha_nacimiento': {
                'required': 'Indica la fecha de nacimiento.',
                'invalid': 'Escribe una fecha válida.',
            },
            'tipo_tarifa': {'required': 'Selecciona si la tarifa es por hora o por evento.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos obligatorios del perfil operativo.
        self.fields['fecha_nacimiento'].required = True
        self.fields['tipo_tarifa'].required = True
        self.fields['tipo_tarifa'].choices = [('', 'Selecciona…')] + list(Actor.TipoTarifa.choices)

        opciones = list(GENEROS)
        actual = (self.instance.genero or '').strip()
        if actual and actual not in opciones:
            opciones.append(actual)  # no perder un valor cargado antes
        self.fields['genero'].choices = [('', 'Selecciona…')] + [(o, o) for o in opciones]

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return fecha
        hoy = timezone.localdate()
        if fecha > hoy:
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
        if edad < EDAD_MINIMA:
            raise forms.ValidationError(f'El actor debe tener al menos {EDAD_MINIMA} años.')
        if edad > 100:
            raise forms.ValidationError('Revisa la fecha de nacimiento: la edad resultante es demasiado alta.')
        return fecha

    def clean_tarifa(self):
        tarifa = self.cleaned_data.get('tarifa')
        if tarifa is None:
            return tarifa
        if tarifa < 0:
            raise forms.ValidationError('La tarifa no puede ser negativa.')
        if tarifa == 0:
            raise forms.ValidationError('La tarifa debe ser mayor que cero.')
        return tarifa

    def full_clean(self):
        super().full_clean()
        # Resalta en rojo los campos con error.
        for nombre in self.errors:
            campo = self.fields.get(nombre)
            if campo and not isinstance(campo.widget, forms.CheckboxSelectMultiple):
                clases = campo.widget.attrs.get('class', '')
                campo.widget.attrs['class'] = (clases + ' is-invalid').strip()


def _perfil_completo(actor):
    return bool(actor.fecha_nacimiento and actor.genero and actor.tarifa and actor.tipo_tarifa)


@modulo_requerido('perfil_actores')
def actores_admin_view(request):
    """Lista de actores con su perfil operativo y acceso para editarlo."""
    actores = (
        Actor.objects.select_related('usuario').prefetch_related('habilidades')
        .order_by('usuario__nombre')
    )
    filas = [
        {
            'actor': a,
            'edad': edad_de(a),
            'habilidades': [h.nombre for h in a.habilidades.all()],
            'completo': _perfil_completo(a),
        }
        for a in actores
    ]
    return render(request, 'simulactores/actores_admin.html', {'filas': filas})


def _resumen_disponibilidad(actor):
    return list(
        Disponibilidad.objects.filter(actor=actor, fecha__gte=timezone.localdate())
        .order_by('fecha', 'hora_inicio')[:6]
    )


def _simulaciones_pendientes(actor):
    return Asignacion.objects.filter(
        actor=actor, estado__in=ESTADOS_VIGENTES,
        solicitud__fecha_evento__gte=timezone.localdate(),
    ).exclude(solicitud__estado=Solicitud.Estado.CANCELADA).count()


def _actualizar_historial_tarifas(actor, tarifa, tipo, hoy):
    """Mantiene el historial: cierra la tarifa anterior y abre la nueva."""
    vigente = actor.historial_tarifas.filter(vigente_hasta__isnull=True).first()
    if vigente and vigente.monto == tarifa and vigente.tipo_tarifa == tipo:
        return
    if vigente:
        if vigente.vigente_desde >= hoy:
            vigente.delete()  # cambio el mismo día: se reemplaza
        else:
            vigente.vigente_hasta = hoy - datetime.timedelta(days=1)
            vigente.save()
    TarifaActor.objects.create(actor=actor, monto=tarifa, tipo_tarifa=tipo, vigente_desde=hoy)


@modulo_requerido('perfil_actores')
def editar_perfil_actor_view(request, actor_id):
    """HU-37: editar el perfil operativo de un actor."""
    actor = get_object_or_404(Actor.objects.select_related('usuario'), pk=actor_id)

    if request.method == 'POST':
        # Copia aparte: validar el formulario ya modifica la instancia en memoria.
        previo = Actor.objects.prefetch_related('habilidades').get(pk=actor.pk)
        antes = {
            'fecha_nacimiento': previo.fecha_nacimiento,
            'genero': previo.genero,
            'tarifa': previo.tarifa,
            'tipo_tarifa': previo.tipo_tarifa,
            'estado': previo.estado,
            'habilidades': ', '.join(sorted(h.nombre for h in previo.habilidades.all())),
        }
        form = PerfilOperativoForm(request.POST, instance=actor)
        if form.is_valid():
            with transaction.atomic():
                actor = form.save()
                despues = {
                    'fecha_nacimiento': actor.fecha_nacimiento,
                    'genero': actor.genero,
                    'tarifa': actor.tarifa,
                    'tipo_tarifa': actor.tipo_tarifa,
                    'estado': actor.estado,
                    'habilidades': ', '.join(sorted(h.nombre for h in actor.habilidades.all())),
                }
                cambios = [
                    (campo, antes[campo], despues[campo])
                    for campo in antes
                    if str(antes[campo]) != str(despues[campo])
                ]
                if cambios:
                    if 'tarifa' in {c[0] for c in cambios} or 'tipo_tarifa' in {c[0] for c in cambios}:
                        _actualizar_historial_tarifas(
                            actor, actor.tarifa, actor.tipo_tarifa, timezone.localdate())
                    registrar_cambios(
                        actor.usuario, 'Perfil operativo del actor actualizado', cambios,
                        realizado_por=request.user, ip_origen=_ip(request),
                    )

            if cambios:
                messages.success(request, f'Perfil operativo de {actor.usuario.nombre} actualizado correctamente.')
            else:
                messages.info(request, 'No hiciste ningún cambio en el perfil.')

            pendientes = _simulaciones_pendientes(actor)
            if actor.estado == Actor.EstadoActor.INACTIVO and pendientes:
                messages.warning(
                    request,
                    f'El actor quedó inactivo pero tiene {pendientes} simulación(es) asignada(s) por venir. '
                    'Gestiona esas asignaciones (por ejemplo, con «Reasignar actor»).',
                )
            return redirect('simulactores:actores_admin')
        messages.error(request, 'Revisa los campos marcados en rojo. No se guardó ningún cambio.')
    else:
        form = PerfilOperativoForm(instance=actor)

    return render(request, 'simulactores/actor_perfil_form.html', {
        'actor': actor,
        'form': form,
        'edad': edad_de(actor),
        'bloques': _resumen_disponibilidad(actor),
    })