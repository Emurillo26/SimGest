import re

from django.core.exceptions import ValidationError


class MayusculaYNumeroValidator:
    """
    Exige al menos una letra mayúscula y un número.

    Se registra en settings.py (AUTH_PASSWORD_VALIDATORS), así aplica igual
    en el registro, en "restablecer contraseña" y al cambiarla desde el
    módulo de administración, y coincide con el cuadro de requisitos de
    las pantallas de acceso.
    """

    def validate(self, password, user=None):
        errores = []
        if not re.search(r"[A-ZÁÉÍÓÚÜÑ]", password):
            errores.append(ValidationError(
                "La contraseña debe tener al menos una letra mayúscula.",
                code="password_sin_mayuscula",
            ))
        if not re.search(r"\d", password):
            errores.append(ValidationError(
                "La contraseña debe tener al menos un número.",
                code="password_sin_numero",
            ))
        if errores:
            raise ValidationError(errores)

    def get_help_text(self):
        return "Tu contraseña debe tener al menos una letra mayúscula y un número."
