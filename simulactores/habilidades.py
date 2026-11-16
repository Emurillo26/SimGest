"""T13: las habilidades las escribe el propio actor (y el administrador al corregir un perfil).

Cada habilidad se escribe y se agrega como etiqueta. Se guardan sin repetir:
«teatro» y «Teatro» son la misma habilidad, y si ya existe se reutiliza.
"""
from django import forms

from .models import Habilidad

MAX_HABILIDADES = 20
MAX_LARGO = 100


def normalizar(texto):
    """Quita espacios sobrantes y deja la primera letra en mayúscula."""
    limpio = ' '.join(str(texto).split())
    return limpio[:1].upper() + limpio[1:]


class HabilidadesField(forms.Field):
    """Lista de habilidades escritas; cada una llega como un campo oculto «habilidades»."""

    widget = forms.MultipleHiddenInput

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('label', 'Habilidades')
        super().__init__(**kwargs)

    def to_python(self, value):
        if not value:
            return []
        nombres, vistos = [], set()
        for bruto in value:
            nombre = normalizar(bruto)
            if not nombre:
                continue
            if len(nombre) > MAX_LARGO:
                raise forms.ValidationError(f'Cada habilidad admite como máximo {MAX_LARGO} caracteres.')
            clave = nombre.casefold()
            if clave not in vistos:
                vistos.add(clave)
                nombres.append(nombre)
        if len(nombres) > MAX_HABILIDADES:
            raise forms.ValidationError(f'Puedes agregar hasta {MAX_HABILIDADES} habilidades.')
        return nombres

    def has_changed(self, initial, data):
        return True


def nombres_de(actor):
    if not actor or not actor.pk:
        return []
    return sorted(h.nombre for h in actor.habilidades.all())


def guardar_habilidades(actor, nombres):
    """Deja al actor con exactamente esas habilidades, reutilizando las que ya existen."""
    objetos = []
    for nombre in nombres:
        habilidad = Habilidad.objects.filter(nombre__iexact=nombre).first()
        if habilidad is None:
            habilidad = Habilidad.objects.create(nombre=nombre)
        objetos.append(habilidad)
    actor.habilidades.set(objetos)