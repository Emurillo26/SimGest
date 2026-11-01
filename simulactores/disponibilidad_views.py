"""Disponibilidad del actor: bloquear fechas (#37) y editar o eliminar bloques (#40)."""
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .asignacion_service import ESTADOS_VIGENTES
from .models import Actor, Asignacion, Disponibilidad, Solicitud
from .permisos import modulo_requerido


def simulaciones_en_rango(actor, fecha, hora_inicio, hora_fin):
    """Asignaciones vigentes del actor que se cruzan con la fecha y el horario."""
    return (
        Asignacion.objects
        .filter(
            actor=actor,
            estado__in=ESTADOS_VIGENTES,
            solicitud__fecha_evento=fecha,
            solicitud__hora_inicio__lt=hora_fin,
            solicitud__hora_fin__gt=hora_inicio,
        )
        .exclude(solicitud__estado=Solicitud.Estado.CANCELADA)
        .select_related('solicitud')
    )


class DisponibilidadForm(forms.ModelForm):

    class Meta:
        model = Disponibilidad
        fields = ['fecha', 'hora_inicio', 'hora_fin', 'tipo_bloque']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'tipo_bloque': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'fecha': 'Fecha',
            'hora_inicio': 'Desde',
            'hora_fin': 'Hasta',
            'tipo_bloque': 'Tipo',
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor

    def clean(self):
        cleaned = super().clean()
        fecha = cleaned.get('fecha')
        inicio = cleaned.get('hora_inicio')
        fin = cleaned.get('hora_fin')
        tipo = cleaned.get('tipo_bloque')

        if not (fecha and inicio and fin):
            return cleaned

        if fecha < timezone.localdate():
            self.add_error('fecha', 'No puedes registrar bloques en fechas pasadas.')
            return cleaned

        if fin <= inicio:
            self.add_error('hora_fin', 'La hora final debe ser posterior a la hora inicial.')
            return cleaned

        # Un bloqueo puede ir encima de un bloque disponible; solo se evitan
        # cruces entre bloques del mismo tipo.
        otros_bloques = Disponibilidad.objects.filter(
            actor=self.actor, fecha=fecha, tipo_bloque=tipo,
            hora_inicio__lt=fin, hora_fin__gt=inicio,
        )
        if self.instance.pk:
            otros_bloques = otros_bloques.exclude(pk=self.instance.pk)
        if otros_bloques.exists():
            raise forms.ValidationError('Ya tienes otro bloque de ese tipo que se cruza con ese horario.')

        # #37 escenario 2: no se puede bloquear un horario con una simulación asignada.
        if tipo == Disponibilidad.TipoBloque.BLOQUEADO:
            conflicto = simulaciones_en_rango(self.actor, fecha, inicio, fin).first()
            if conflicto:
                raise forms.ValidationError(
                    f'Tienes la simulación {conflicto.solicitud.numero_solicitud} asignada en ese horario. '
                    'Debes gestionar primero su cancelación antes de bloquear la fecha.'
                )

        return cleaned


def _actor_de(request):
    return Actor.objects.filter(usuario=request.user).first()


def _bloque_del_actor(request, bloque_id):
    # Filtrar por el usuario evita que un actor toque bloques de otro (da 404).
    return get_object_or_404(Disponibilidad, pk=bloque_id, actor__usuario=request.user)


def _simulacion_del_bloque(bloque):
    return simulaciones_en_rango(bloque.actor, bloque.fecha, bloque.hora_inicio, bloque.hora_fin).first()


def _pantalla(request, actor, form, editando=None):
    bloques = []
    if actor:
        bloques = (
            Disponibilidad.objects
            .filter(actor=actor, fecha__gte=timezone.localdate())
            .order_by('fecha', 'hora_inicio')
        )
    return render(request, 'simulactores/mi_disponibilidad.html', {
        'actor': actor,
        'form': form,
        'bloques': bloques,
        'editando': editando,
    })


@modulo_requerido('disponibilidad_actor')
def mi_disponibilidad_view(request):
    """Lista los bloques del actor y permite registrar o bloquear fechas (#37)."""
    actor = _actor_de(request)

    if request.method == 'POST' and actor:
        form = DisponibilidadForm(request.POST, actor=actor)
        if form.is_valid():
            bloque = form.save(commit=False)
            bloque.actor = actor
            bloque.save()
            if bloque.tipo_bloque == Disponibilidad.TipoBloque.BLOQUEADO:
                messages.success(request, 'Fecha bloqueada. No se te asignarán simulaciones en ese horario.')
            else:
                messages.success(request, 'Disponibilidad guardada.')
            return redirect('simulactores:mi_disponibilidad')
    else:
        form = DisponibilidadForm(actor=actor)

    return _pantalla(request, actor, form)


@modulo_requerido('disponibilidad_actor')
def editar_disponibilidad_view(request, bloque_id):
    """#40 escenario 1: modificar la fecha u horario de un bloque sin simulaciones."""
    bloque = _bloque_del_actor(request, bloque_id)

    conflicto = _simulacion_del_bloque(bloque)
    if conflicto:
        messages.error(
            request,
            f'Este bloque tiene la simulación {conflicto.solicitud.numero_solicitud} asignada. '
            'Debes gestionar esa simulación primero.'
        )
        return redirect('simulactores:mi_disponibilidad')

    if request.method == 'POST':
        form = DisponibilidadForm(request.POST, instance=bloque, actor=bloque.actor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bloque actualizado correctamente.')
            return redirect('simulactores:mi_disponibilidad')
    else:
        form = DisponibilidadForm(instance=bloque, actor=bloque.actor)

    return _pantalla(request, bloque.actor, form, editando=bloque)


@modulo_requerido('disponibilidad_actor')
@require_POST
def eliminar_disponibilidad_view(request, bloque_id):
    """#40 escenario 2: no se elimina un bloque con una simulación asignada."""
    bloque = _bloque_del_actor(request, bloque_id)

    conflicto = _simulacion_del_bloque(bloque)
    if conflicto:
        messages.error(
            request,
            f'No puedes eliminar este bloque: tienes la simulación {conflicto.solicitud.numero_solicitud} '
            'asignada en ese horario. Debes gestionar esa simulación primero.'
        )
    else:
        bloque.delete()
        messages.success(request, 'Bloque eliminado.')

    return redirect('simulactores:mi_disponibilidad')
