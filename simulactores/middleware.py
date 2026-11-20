import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

CLAVE_ULTIMA_ACTIVIDAD = 'ultima_actividad'
MENSAJE_INACTIVIDAD = 'Tu sesión se cerró por inactividad. Inicia sesión nuevamente para continuar.'


class CierreSesionPorInactividadMiddleware:


    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = time.time()
            limite = settings.INACTIVITY_TIMEOUT_MINUTES * 60
            ultima = request.session.get(CLAVE_ULTIMA_ACTIVIDAD)

            if ultima is not None and ahora - ultima > limite:
                logout(request)
                messages.warning(request, MENSAJE_INACTIVIDAD)
                return redirect('simulactores:login')

            request.session[CLAVE_ULTIMA_ACTIVIDAD] = ahora

        return self.get_response(request)
