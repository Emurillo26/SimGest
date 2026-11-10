"""Disponibilidad: bloquear fechas (#37), editar o eliminar bloques (#40) y consulta del admin (#38)."""
import datetime
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.db import transaction
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


def recortar_disponibilidad(actor, fecha, hora_inicio, hora_fin, excluir_pk=None):
    """Quita de los bloques «Disponible» la parte que ocupa un bloqueo nuevo.

    Así el mismo horario nunca queda Disponible y Bloqueado a la vez:
      - si el bloqueo cubre todo el bloque, el bloque se elimina;
      - si cubre una punta, el bloque se acorta;
      - si cae en medio, el bloque se parte en dos.
    Devuelve True si se ajustó alguna disponibilidad.
    """
    ajustado = False
    bloques = Disponibilidad.objects.filter(
        actor=actor, fecha=fecha, tipo_bloque=Disponibilidad.TipoBloque.DISPONIBLE,
        hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio,
    )
    if excluir_pk:
        bloques = bloques.exclude(pk=excluir_pk)

    for bloque in bloques:
        ajustado = True
        queda_antes = bloque.hora_inicio < hora_inicio
        queda_despues = bloque.hora_fin > hora_fin
        fin_original = bloque.hora_fin

        if queda_antes and queda_despues:
            bloque.hora_fin = hora_inicio
            bloque.save()
            Disponibilidad.objects.create(
                actor=actor, fecha=fecha, hora_inicio=hora_fin, hora_fin=fin_original,
                tipo_bloque=Disponibilidad.TipoBloque.DISPONIBLE,
            )
        elif queda_antes:
            bloque.hora_fin = hora_inicio
            bloque.save()
        elif queda_despues:
            bloque.hora_inicio = hora_fin
            bloque.save()
        else:
            bloque.delete()
    return ajustado


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

        # Un mismo horario nunca puede quedar como Disponible y Bloqueado a la vez.
        #   - Mismo tipo: no se permiten cruces.
        #   - Bloquear sobre una disponibilidad: se permite; al guardar, la
        #     disponibilidad se recorta para que no queden bloques encimados.
        #   - Registrar disponibilidad sobre un bloqueo: no se permite.
        cruzados = Disponibilidad.objects.filter(
            actor=self.actor, fecha=fecha,
            hora_inicio__lt=fin, hora_fin__gt=inicio,
        )
        if self.instance.pk:
            cruzados = cruzados.exclude(pk=self.instance.pk)

        if cruzados.filter(tipo_bloque=tipo).exists():
            raise forms.ValidationError('Ya tienes otro bloque de ese tipo que se cruza con ese horario.')

        if tipo == Disponibilidad.TipoBloque.DISPONIBLE and cruzados.filter(
            tipo_bloque=Disponibilidad.TipoBloque.BLOQUEADO
        ).exists():
            raise forms.ValidationError(
                'Ese horario está bloqueado. Edita o elimina el bloqueo antes de registrar disponibilidad.'
            )

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
            ajustado = False
            with transaction.atomic():
                bloque.save()
                if bloque.tipo_bloque == Disponibilidad.TipoBloque.BLOQUEADO:
                    ajustado = recortar_disponibilidad(
                        actor, bloque.fecha, bloque.hora_inicio, bloque.hora_fin, excluir_pk=bloque.pk)
            if bloque.tipo_bloque == Disponibilidad.TipoBloque.BLOQUEADO:
                mensaje = 'Fecha bloqueada. No se te asignarán simulaciones en ese horario.'
                if ajustado:
                    mensaje += ' Tu disponibilidad en ese horario se ajustó para no cruzarse con el bloqueo.'
                messages.success(request, mensaje)
            else:
                messages.success(request, 'Disponibilidad guardada.')
            return redirect('simulactores:mi_disponibilidad')
    else:
        # HU-36: el calendario del actor enlaza aquí con ?fecha=AAAA-MM-DD.
        inicial = {}
        fecha_url = request.GET.get('fecha')
        if fecha_url:
            try:
                inicial['fecha'] = datetime.date.fromisoformat(fecha_url)
            except ValueError:
                pass
        form = DisponibilidadForm(actor=actor, initial=inicial)

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
            with transaction.atomic():
                bloque = form.save()
                if bloque.tipo_bloque == Disponibilidad.TipoBloque.BLOQUEADO:
                    recortar_disponibilidad(
                        bloque.actor, bloque.fecha, bloque.hora_inicio, bloque.hora_fin, excluir_pk=bloque.pk)
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


# --- #38: consulta de disponibilidad del administrador ----------------------

MENSAJE_SIN_ACTORES_FECHA = 'No hay actores disponibles para esta fecha'


MAX_DIAS_CONSULTA = 31


class ConsultaDisponibilidadForm(forms.Form):
    fecha = forms.DateField(
        label='Fecha (desde)',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
    )
    fecha_hasta = forms.DateField(
        label='Fecha hasta (opcional)', required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
    )
    hora_inicio = forms.TimeField(
        label='Desde (opcional)', required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
    )
    hora_fin = forms.TimeField(
        label='Hasta (opcional)', required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
    )

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('hora_inicio')
        fin = cleaned.get('hora_fin')

        desde = cleaned.get('fecha')
        hasta = cleaned.get('fecha_hasta')
        if desde and hasta:
            if hasta < desde:
                self.add_error('fecha_hasta', 'La fecha final no puede ser anterior a la inicial.')
            elif (hasta - desde).days + 1 > MAX_DIAS_CONSULTA:
                self.add_error('fecha_hasta', f'El rango máximo es de {MAX_DIAS_CONSULTA} días.')

        if bool(inicio) != bool(fin):
            raise forms.ValidationError('Indica las dos horas o deja ambas vacías.')
        if inicio and fin and fin <= inicio:
            self.add_error('hora_fin', 'La hora final debe ser posterior a la hora inicial.')
        return cleaned


def actores_disponibles(fecha, hora_inicio=None, hora_fin=None):
    """Actores activos con disponibilidad registrada para la fecha.

    Con horario: solo los que tienen un bloque disponible que lo cubre completo,
    sin bloqueos ni simulaciones que se crucen.
    Sin horario: todos los que registraron disponibilidad ese día, con sus
    compromisos (bloqueos y simulaciones) para que el administrador los vea.
    """
    bloques = (
        Disponibilidad.objects
        .filter(
            fecha=fecha,
            tipo_bloque=Disponibilidad.TipoBloque.DISPONIBLE,
            actor__estado=Actor.EstadoActor.ACTIVO,
            actor__usuario__estado='Activo',
        )
        .select_related('actor__usuario')
        .order_by('actor__usuario__nombre', 'hora_inicio')
    )
    if hora_inicio and hora_fin:
        bloques = bloques.filter(hora_inicio__lte=hora_inicio, hora_fin__gte=hora_fin)

    filas = {}
    for bloque in bloques:
        actor = bloque.actor
        if actor.pk not in filas:
            filas[actor.pk] = {'actor': actor, 'bloques': [], 'bloqueos': [], 'simulaciones': []}
        filas[actor.pk]['bloques'].append(bloque)

    for actor_id, fila in list(filas.items()):
        actor = fila['actor']
        if hora_inicio and hora_fin:
            inicio, fin = hora_inicio, hora_fin
        else:
            inicio = min(b.hora_inicio for b in fila['bloques'])
            fin = max(b.hora_fin for b in fila['bloques'])

        fila['bloqueos'] = list(Disponibilidad.objects.filter(
            actor=actor, fecha=fecha, tipo_bloque=Disponibilidad.TipoBloque.BLOQUEADO,
            hora_inicio__lt=fin, hora_fin__gt=inicio,
        ).order_by('hora_inicio'))
        fila['simulaciones'] = list(simulaciones_en_rango(actor, fecha, inicio, fin)
                                    .order_by('solicitud__hora_inicio'))

        if hora_inicio and hora_fin and (fila['bloqueos'] or fila['simulaciones']):
            del filas[actor_id]

    return list(filas.values())


def _atajos_de_fechas(request):
    """Enlaces rápidos (hoy, mañana, esta semana...) que conservan el horario elegido."""
    hoy = timezone.localdate()
    lunes = hoy - datetime.timedelta(days=hoy.weekday())
    if hoy.month == 12:
        fin_de_mes = datetime.date(hoy.year, 12, 31)
    else:
        fin_de_mes = datetime.date(hoy.year, hoy.month + 1, 1) - datetime.timedelta(days=1)

    horario = {
        k: request.GET.get(k) for k in ('hora_inicio', 'hora_fin') if request.GET.get(k)
    }

    def enlace(etiqueta, desde, hasta=None):
        datos = {'fecha': desde.isoformat(), **horario}
        if hasta and hasta != desde:
            datos['fecha_hasta'] = hasta.isoformat()
        return {'etiqueta': etiqueta, 'query': urlencode(datos)}

    return [
        enlace('Hoy', hoy),
        enlace('Mañana', hoy + datetime.timedelta(days=1)),
        enlace('Esta semana', lunes, lunes + datetime.timedelta(days=6)),
        enlace('Próximos 7 días', hoy, hoy + datetime.timedelta(days=6)),
        enlace('Este mes', hoy, fin_de_mes),
    ]


@modulo_requerido('disponibilidad_actores')
def consulta_disponibilidad_view(request):
    """#38: el administrador consulta qué actores están disponibles en una fecha, o en un
    rango de fechas (por día, semana o mes), con o sin horario."""
    form = ConsultaDisponibilidadForm(request.GET or None)
    filas = None
    resultados = []
    es_rango = False

    if form.is_bound and form.is_valid():
        desde = form.cleaned_data['fecha']
        hasta = form.cleaned_data.get('fecha_hasta') or desde
        inicio = form.cleaned_data.get('hora_inicio')
        fin = form.cleaned_data.get('hora_fin')
        es_rango = hasta != desde

        for i in range((hasta - desde).days + 1):
            dia = desde + datetime.timedelta(days=i)
            resultados.append({'fecha': dia, 'filas': actores_disponibles(dia, inicio, fin)})

        if es_rango:
            filas = [f for r in resultados for f in r['filas']]  # vacío = nadie en todo el rango
        else:
            filas = resultados[0]['filas']

    return render(request, 'simulactores/consulta_disponibilidad.html', {
        'form': form,
        'filas': filas,
        'es_rango': es_rango,
        'resultados': resultados,
        'dias_con_actores': sum(1 for r in resultados if r['filas']),
        'atajos': _atajos_de_fechas(request),
        'mensaje_sin_actores': MENSAJE_SIN_ACTORES_FECHA,
    })