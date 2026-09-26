from functools import wraps

from django.shortcuts import redirect, render

from .models import MATRIZ_PERMISOS


def modulo_requerido(nombre_modulo):
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('simulactores:login')

            rol = getattr(request.user.rol, 'nombre', None)
            modulos_permitidos = MATRIZ_PERMISOS.get(rol, set())

            if nombre_modulo not in modulos_permitidos:
                return render(request, 'simulactores/permisos_insuficientes.html', status=403)

            return vista(request, *args, **kwargs)
        return envoltura
    return decorador
