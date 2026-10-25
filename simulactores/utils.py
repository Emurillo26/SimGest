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


def notificar(usuario, mensaje, asunto=None, enviar_correo=True, enlace=''):
    """Crea la notificación interna y, si se pide, envía el correo (HU-30).

    - La notificación interna SIEMPRE se guarda, aunque el correo falle.
    - Si el correo falla, queda marcado en la notificación (correo_enviado=False)
      y se registra el fallo en la bitácora; el flujo del usuario no se rompe.
    """
    notificacion = Notificacion.objects.create(usuario=usuario, mensaje=mensaje, enlace=enlace)

    if enviar_correo and usuario.email:
        try:
            send_mail(
                asunto or 'Notificación de Simulactores',
                mensaje,
                settings.DEFAULT_FROM_EMAIL,
                [usuario.email],
                fail_silently=False,
            )
            notificacion.correo_enviado = True
        except Exception as error:
            notificacion.correo_enviado = False
            notificacion.error_correo = str(error)[:255]
            registrar_cambios(
                usuario,
                'Fallo de envío de correo',
                [('correo', None, usuario.email)],
                resultado='Fallido',
            )
        notificacion.save(update_fields=['correo_enviado', 'error_correo'])

    return notificacion


def notificar_administradores(mensaje, asunto=None, enlace=''):
    """Envía el mismo aviso a todos los administradores activos (para HU-29 y HU-45)."""
    from .models import Usuario

    administradores = Usuario.objects.filter(rol__nombre='Administrador', estado='Activo')
    return [notificar(admin, mensaje, asunto=asunto, enlace=enlace) for admin in administradores]
