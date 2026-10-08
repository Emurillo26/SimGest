from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Escenario, Solicitud, TipoSimulacion, Usuario


class RegistroClienteForm(forms.Form):
    """
    Formulario público de registro (HU: Registro de clientes).
    Solo crea usuarios con rol Cliente. Actor/Administrador se
    gestionan aparte, desde el módulo de administración
    (ver simulactores/views.py: listado_usuarios / actualizar_rol).
    """

    nombre = forms.CharField(
        max_length=150, label="Nombre completo",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    telefono = forms.CharField(
        max_length=20, required=False, label="Teléfono (opcional)",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Contraseña",
        help_text=(

        ),
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Confirmar contraseña",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # Regla de negocio: correo duplicado -> error explícito
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo ya está en uso.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        usuario_temporal = Usuario(
            email=self.data.get("email", ""),
            nombre=self.data.get("nombre", ""),
        )
        validate_password(password, user=usuario_temporal)
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        password2 = cleaned.get("password2")
        if password and password2 and password != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned


class CambiarPasswordForm(forms.Form):


    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Nueva contraseña",
        help_text="Dejar en blanco para no cambiarla.",
    )
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        label="Confirmar nueva contraseña",
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self._usuario = usuario
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        password2 = cleaned.get("password2")
        if password:
            if password != password2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(password, user=self._usuario)
                except forms.ValidationError as error:
                    self.add_error("password", error)
        return cleaned


class SolicitudForm(forms.ModelForm):


    class Meta:
        model = Solicitud
        fields = [
            'tipo_simulacion', 'fecha_evento', 'hora_inicio', 'hora_fin',
            'cantidad_interpretes', 'observaciones',
        ]
        widgets = {
            'tipo_simulacion': forms.Select(attrs={'class': 'form-select'}),
            'fecha_evento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'cantidad_interpretes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'tipo_simulacion': 'Tipo de simulación',
            'fecha_evento': 'Fecha del evento',
            'hora_inicio': 'Hora de inicio',
            'hora_fin': 'Hora de fin',
            'cantidad_interpretes': 'Cantidad de intérpretes',
            'observaciones': 'Observaciones (opcional)',
        }

    def clean(self):
        cleaned = super().clean()
        fecha = cleaned.get('fecha_evento')
        inicio = cleaned.get('hora_inicio')
        fin = cleaned.get('hora_fin')

        if fecha and inicio and fin:
            if fin <= inicio:
                self.add_error('hora_fin', 'La hora de fin debe ser posterior a la hora de inicio.')
                return cleaned

            traslape = Solicitud.objects.filter(
                fecha_evento=fecha,
                hora_inicio__lt=fin,
                hora_fin__gt=inicio,
            ).exclude(estado=Solicitud.Estado.CANCELADA)
            if traslape.exists():
                self.add_error(
                    'fecha_evento',
                    'Ese horario ya está ocupado por otra solicitud. Por favor elige otra fecha u horario.',
                )
                self.add_error('hora_inicio', '')
                self.add_error('hora_fin', '')
        return cleaned


class RechazarEscenarioForm(forms.Form):

    comentario = forms.CharField(
        label='Motivo del rechazo',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )


class CancelarSolicitudForm(forms.Form):

    motivo = forms.CharField(
        required=False,
        label='Motivo de la cancelación (opcional)',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )


class AsignarEscenarioForm(forms.Form):


    escenario = forms.ModelChoiceField(
        queryset=Escenario.objects.filter(estado=Escenario.Estado.ACTIVO),
        label='Escenario a proponer',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
