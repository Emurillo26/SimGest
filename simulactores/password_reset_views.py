from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Usuario


def recuperar_contrasena_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()

        usuario = Usuario.objects.filter(
            email__iexact=email,
            estado='Activo'
        ).first()

        if usuario and usuario.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)

            enlace = request.build_absolute_uri(
                reverse(
                    'simulactores:password_reset_confirm',
                    kwargs={
                        'uidb64': uid,
                        'token': token
                    }
                )
            )

            asunto = 'Restablecimiento de contraseña - SimGest'

            mensaje = (
                f'Hola {usuario.nombre},\n\n'
                'Recibimos una solicitud para restablecer la contraseña '
                'de tu cuenta en SimGest.\n\n'
                'Puedes crear una nueva contraseña usando el siguiente enlace:\n\n'
                f'{enlace}\n\n'
                'Este enlace es de un solo uso y vence en 30 minutos.\n\n'
                'Si no solicitaste este cambio, puedes ignorar este mensaje.\n\n'
                'SimGest'
            )

            send_mail(
                asunto,
                mensaje,
                settings.DEFAULT_FROM_EMAIL,
                [usuario.email],
                fail_silently=False,
            )

        return redirect('simulactores:password_reset_done')

    return render(
        request,
        'simulactores/password_reset.html'
    )