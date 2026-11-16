"""Perfil del actor editado por él mismo desde «Mi perfil».

Datos personales (fecha de nacimiento, género), habilidades y
características físicas. El estado activo/inactivo lo sigue manejando el
administrador (HU-37), que también puede corregir estos datos.
"""
from django import forms
from django.utils import timezone

from .habilidades import HabilidadesField, guardar_habilidades, nombres_de
from .models import Actor
from .perfil_actor_views import EDAD_MINIMA, GENEROS

CAMPOS_FISICOS = [
    ('estatura_cm', 'Estatura', ' cm'),
    ('peso_kg', 'Peso', ' kg'),
    ('color_cabello', 'Color de cabello', ''),
    ('color_ojos', 'Color de ojos', ''),
    ('contextura', 'Contextura', ''),
    ('tono_piel', 'Tono de piel', ''),
    ('talla_ropa', 'Talla de ropa', ''),
    ('talla_calzado', 'Talla de calzado', ''),
]


def _opciones(lista):
    return [('', 'Selecciona…')] + [(o, o) for o in lista]


def resumen_fisico(actor):
    """Lista de (etiqueta, valor) para mostrar las características físicas."""
    filas = []
    for campo, etiqueta, sufijo in CAMPOS_FISICOS:
        valor = getattr(actor, campo)
        if valor in (None, ''):
            texto = None
        else:
            if campo in ('peso_kg', 'talla_calzado'):
                valor = f'{valor:g}'
            texto = f'{valor}{sufijo}'
        filas.append((etiqueta, texto))
    filas.append(('Otras características', actor.otras_caracteristicas or None))
    return filas


def valores_actor(actor):
    """Foto de los datos editables, para la bitácora de cambios."""
    datos = {campo: getattr(actor, campo) for campo in CAMPOS_EDITABLES if campo != 'habilidades'}
    datos['habilidades'] = ', '.join(sorted(h.nombre for h in actor.habilidades.all()))
    return datos


class PerfilActorForm(forms.ModelForm):

    genero = forms.ChoiceField(
        label='Género', required=True,
        error_messages={'required': 'Selecciona tu género.'},
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    habilidades = HabilidadesField()

    class Meta:
        model = Actor
        fields = [
            'fecha_nacimiento', 'genero',
            'estatura_cm', 'peso_kg', 'color_cabello', 'color_ojos', 'contextura',
            'tono_piel', 'talla_ropa', 'talla_calzado', 'otras_caracteristicas',
        ]
        labels = {
            'fecha_nacimiento': 'Fecha de nacimiento',
            'estatura_cm': 'Estatura (cm)',
            'peso_kg': 'Peso (kg)',
            'color_cabello': 'Color de cabello',
            'color_ojos': 'Color de ojos',
            'contextura': 'Contextura',
            'tono_piel': 'Tono de piel',
            'talla_ropa': 'Talla de ropa',
            'talla_calzado': 'Talla de calzado',
            'otras_caracteristicas': 'Otras características',
        }
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'estatura_cm': forms.NumberInput(attrs={'class': 'form-control', 'min': '100', 'max': '230', 'placeholder': 'Ej. 170'}),
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '30', 'max': '250', 'placeholder': 'Ej. 65.5'}),
            'talla_calzado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '20', 'max': '50', 'placeholder': 'Ej. 38'}),
            'otras_caracteristicas': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'maxlength': '500',
                'placeholder': 'Tatuajes, cicatrices, barba, uso de lentes, acento, etc.'}),
        }
        error_messages = {
            'fecha_nacimiento': {
                'required': 'Indica tu fecha de nacimiento.',
                'invalid': 'Escribe una fecha válida.',
            },
            'estatura_cm': {'invalid': 'La estatura debe ser un número entero en centímetros.'},
            'peso_kg': {'invalid': 'El peso debe ser un número (por ejemplo 65.5).'},
            'talla_calzado': {'invalid': 'La talla de calzado debe ser un número (por ejemplo 38 o 38.5).'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_nacimiento'].required = True
        self.initial['habilidades'] = nombres_de(self.instance)

        opciones = list(GENEROS)
        actual = (self.instance.genero or '').strip()
        if actual and actual not in opciones:
            opciones.append(actual)
        self.fields['genero'].choices = _opciones(opciones)

        listas = {
            'color_cabello': Actor.COLORES_CABELLO,
            'color_ojos': Actor.COLORES_OJOS,
            'contextura': Actor.CONTEXTURAS,
            'tono_piel': Actor.TONOS_PIEL,
            'talla_ropa': Actor.TALLAS_ROPA,
        }
        for nombre, lista in listas.items():
            self.fields[nombre] = forms.ChoiceField(
                label=self.Meta.labels[nombre], required=False,
                choices=_opciones(lista),
                widget=forms.Select(attrs={'class': 'form-select'}),
            )

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return fecha
        hoy = timezone.localdate()
        if fecha > hoy:
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
        if edad < EDAD_MINIMA:
            raise forms.ValidationError(f'Debes tener al menos {EDAD_MINIMA} años.')
        if edad > 100:
            raise forms.ValidationError('Revisa la fecha de nacimiento: la edad resultante es demasiado alta.')
        return fecha

    def clean_estatura_cm(self):
        valor = self.cleaned_data.get('estatura_cm')
        if valor is not None and not 100 <= valor <= 230:
            raise forms.ValidationError('La estatura debe estar entre 100 y 230 cm.')
        return valor

    def clean_peso_kg(self):
        valor = self.cleaned_data.get('peso_kg')
        if valor is not None and not 30 <= valor <= 250:
            raise forms.ValidationError('El peso debe estar entre 30 y 250 kg.')
        return valor

    def clean_talla_calzado(self):
        valor = self.cleaned_data.get('talla_calzado')
        if valor is not None and not 20 <= valor <= 50:
            raise forms.ValidationError('La talla de calzado debe estar entre 20 y 50.')
        return valor

    def clean_otras_caracteristicas(self):
        return (self.cleaned_data.get('otras_caracteristicas') or '').strip()

    def clean(self):
        cleaned = super().clean()
        # Los selects vacíos se guardan como "sin dato", no como texto vacío.
        for nombre in ('color_cabello', 'color_ojos', 'contextura', 'tono_piel', 'talla_ropa'):
            if cleaned.get(nombre) == '':
                cleaned[nombre] = None
        return cleaned

    def save(self, commit=True):
        actor = super().save(commit=commit)
        if commit:
            guardar_habilidades(actor, self.cleaned_data.get('habilidades', []))
        return actor

    def full_clean(self):
        super().full_clean()
        for nombre in self.errors:
            campo = self.fields.get(nombre)
            if campo and not isinstance(campo.widget, forms.CheckboxSelectMultiple):
                clases = campo.widget.attrs.get('class', '')
                campo.widget.attrs['class'] = (clases + ' is-invalid').strip()


CAMPOS_EDITABLES = list(PerfilActorForm.Meta.fields)