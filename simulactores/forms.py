from django import forms

from .models import Usuario


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
        min_length=8, label="Contraseña",
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

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        password2 = cleaned.get("password2")
        if password and password2 and password != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned
