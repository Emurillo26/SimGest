
from django import forms

from .models import Actor


def _select(etiqueta, valores):
    return forms.ChoiceField(
        label=etiqueta, required=False,
        choices=[('', 'Todos')] + [(v, v) for v in valores],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


def _numero(etiqueta, placeholder, minimo, maximo, **extra):
    return forms.IntegerField(
        label=etiqueta, required=False, min_value=minimo, max_value=maximo,
        error_messages={'invalid': f'{etiqueta}: escribe un número entero.',
                        'min_value': f'{etiqueta}: el valor es demasiado bajo.',
                        'max_value': f'{etiqueta}: el valor es demasiado alto.'},
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': placeholder}),
        **extra,
    )


CAMPOS_FISICOS = (
    'estatura_min', 'estatura_max', 'color_cabello', 'color_ojos',
    'contextura', 'tono_piel', 'talla_ropa', 'talla_calzado',
)


class CaracteristicasFisicasMixin(forms.Form):
    estatura_min = _numero('Estatura desde (cm)', 'Mín.', 50, 250)
    estatura_max = _numero('Estatura hasta (cm)', 'Máx.', 50, 250)
    color_cabello = _select('Cabello', Actor.COLORES_CABELLO)
    color_ojos = _select('Ojos', Actor.COLORES_OJOS)
    contextura = _select('Contextura', Actor.CONTEXTURAS)
    tono_piel = _select('Tono de piel', Actor.TONOS_PIEL)
    talla_ropa = _select('Talla de ropa', Actor.TALLAS_ROPA)
    talla_calzado = forms.DecimalField(
        label='Talla de calzado', required=False, min_value=20, max_value=50,
        max_digits=3, decimal_places=1,
        error_messages={'invalid': 'Talla de calzado: escribe un número.',
                        'min_value': 'La talla de calzado debe estar entre 20 y 50.',
                        'max_value': 'La talla de calzado debe estar entre 20 y 50.'},
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 42', 'step': '0.5'}),
    )

    def clean(self):
        datos = super().clean()
        minimo, maximo = datos.get('estatura_min'), datos.get('estatura_max')
        if minimo is not None and maximo is not None and minimo > maximo:
            self.add_error('estatura_max', 'La estatura máxima no puede ser menor que la mínima.')
        return datos

    def filtrar_fisico(self, queryset):
        d = self.cleaned_data
        if d.get('estatura_min') is not None:
            queryset = queryset.filter(estatura_cm__gte=d['estatura_min'])
        if d.get('estatura_max') is not None:
            queryset = queryset.filter(estatura_cm__lte=d['estatura_max'])
        for campo in ('color_cabello', 'color_ojos', 'contextura', 'tono_piel', 'talla_ropa'):
            if d.get(campo):
                queryset = queryset.filter(**{campo: d[campo]})
        if d.get('talla_calzado') is not None:
            queryset = queryset.filter(talla_calzado=d['talla_calzado'])
        return queryset

    def hay_criterios_fisicos(self):
        d = self.cleaned_data
        return any(d.get(c) not in (None, '') for c in CAMPOS_FISICOS)


class FiltroFisicoForm(CaracteristicasFisicasMixin):
    """Filtro solo físico, para la pantalla de asignación."""
