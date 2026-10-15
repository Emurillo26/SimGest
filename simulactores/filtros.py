from django import forms

from .models import Solicitud


class FiltroSolicitudesForm(forms.Form):
    """
    Filtros del listado "Mis solicitudes" (HU 17): estado y/o rango de fechas
    del evento. Se lee por GET, así que todos los campos son opcionales.
    """

    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas')] + list(Solicitud.Estado.choices),
        error_messages={'invalid_choice': 'Ese estado no es válido.'},
    )
    desde = forms.DateField(
        required=False,
        error_messages={'invalid': 'La fecha inicial no es válida.'},
    )
    hasta = forms.DateField(
        required=False,
        error_messages={'invalid': 'La fecha final no es válida.'},
    )

    def clean(self):
        cleaned = super().clean()
        desde = cleaned.get('desde')
        hasta = cleaned.get('hasta')
        if desde and hasta and desde > hasta:
            self.add_error('hasta', 'La fecha final no puede ser anterior a la inicial.')
        return cleaned
