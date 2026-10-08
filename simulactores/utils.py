from django.conf import settings
from django.core.mail import send_mail

from .models import Bitacora, Notificacion


def registrar_cambios(usuario, accion, cambios, realizado_por=None, ip_origen=None, resultado='Exitoso'):

    filas = [
        Bitacora(
            usuario=usuario,
            realizado_por=realizado_por or usuario,
            accion=accion,
            campo_modificado=campo,
            valor_anterior=str(antes) if antes is not None else None,
            valor_nuevo=str(despues) if despues is not None else None,
            resultado=resultado,
            ip_origen=ip_origen,
        )
        for campo, antes, despues in cambios
    ]
    if filas:
        Bitacora.objects.bulk_create(filas)
    return filas


def notificar(usuario, mensaje, asunto=None, enviar_correo=True):

    Notificacion.objects.create(usuario=usuario, mensaje=mensaje)

    if enviar_correo and usuario.email:
        send_mail(
            asunto or 'Notificación de SimGest',
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            [usuario.email],
            fail_silently=True,
        )
