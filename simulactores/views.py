from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Usuario, Rol, Bitacora


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            messages.error(request, 'Correo o contraseña incorrectos.')
            return render(request, 'simulactores/login.html')

        if usuario.password_hash != password:
            messages.error(request, 'Correo o contraseña incorrectos.')
            return render(request, 'simulactores/login.html')

        if usuario.estado != 'Activo':
            messages.error(request, 'Esta cuenta no está habilitada.')
            return render(request, 'simulactores/login.html')

        request.session['usuario_id'] = usuario.id_usuario
        request.session['usuario_rol'] = usuario.id_rol.nombre
        return redirect('simulactores:listado_usuarios')

    return render(request, 'simulactores/login.html')


def logout_view(request):
    request.session.flush()
    return redirect('simulactores:login')


def perfil_view(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('simulactores:login')

    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        nombre_anterior = usuario.nombre
        telefono_anterior = usuario.telefono

        usuario.nombre = request.POST.get('nombre')
        usuario.telefono = request.POST.get('telefono')

        nueva_password = request.POST.get('password')
        cambio_password = False
        if nueva_password:
            usuario.password_hash = nueva_password
            cambio_password = True

        usuario.save()

        cambios = []
        if nombre_anterior != usuario.nombre:
            cambios.append('Nombre actualizado')
        if telefono_anterior != usuario.telefono:
            cambios.append('Teléfono actualizado')
        if cambio_password:
            cambios.append('Contraseña actualizada')

        if cambios:
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='Edición de perfil propio: ' + ', '.join(cambios),
                resultado='Exitoso'
            )
        messages.success(request, 'Perfil actualizado correctamente.')

    return render(request, 'simulactores/perfil.html', {'usuario': usuario})


def listado_usuarios(request):
    usuarios = Usuario.objects.select_related('id_rol').all().order_by('nombre')
    roles = Rol.objects.all()
    return render(request, 'simulactores/usuarios.html', {'usuarios': usuarios, 'roles': roles})


def actualizar_rol(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        nuevo_rol_id = request.POST.get('id_rol')
        nuevo_estado = request.POST.get('estado')
        nuevo_email = request.POST.get('email')
        rol = get_object_or_404(Rol, pk=nuevo_rol_id)

        rol_anterior = usuario.id_rol.nombre
        estado_anterior = usuario.estado
        email_anterior = usuario.email

        usuario.id_rol = rol
        usuario.estado = nuevo_estado
        usuario.email = nuevo_email
        usuario.save()

        cambios = []
        if rol_anterior != rol.nombre:
            cambios.append(f'Rol: {rol_anterior} -> {rol.nombre}')
        if estado_anterior != nuevo_estado:
            cambios.append(f'Estado: {estado_anterior} -> {nuevo_estado}')
        if email_anterior != nuevo_email:
            cambios.append(f'Correo: {email_anterior} -> {nuevo_email}')

        if cambios:
            Bitacora.objects.create(
                id_usuario=usuario,
                accion='Edición por administrador: ' + ' | '.join(cambios),
                resultado='Exitoso'
            )

    return redirect('simulactores:listado_usuarios')