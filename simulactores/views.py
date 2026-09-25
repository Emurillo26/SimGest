from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .forms import RegistroClienteForm
from .models import Usuario, Rol, Bitacora

# Token firmado para el enlace de confirmación de correo (sin migraciones nuevas)
_signer = TimestampSigner()
CONFIRMACION_MAX_AGE = 60 * 60 * 48  # 48 horas


def registro_view(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            rol_cliente = Rol.objects.get(nombre='Cliente')
            usuario = Usuario.objects.create(
                nombre=form.cleaned_data['nombre'],
                email=form.cleaned_data['email'],
                telefono=form.cleaned_data.get('telefono') or None,
                password_hash=make_password(form.cleaned_data['password']),
                id_rol=rol_cliente,
                estado='Pendiente',  # se activa al confirmar el correo
            )
            _enviar_correo_confirmacion(request, usuario)
            messages.success(request, 'Cuenta creada. Revisa tu correo para confirmarla.')
            return redirect('simulactores:login')
        return render(request, 'simulactores/registro.html', {'form': form})

    return render(request, 'simulactores/registro.html', {'form': RegistroClienteForm()})


def _enviar_correo_confirmacion(request, usuario):
    token = _signer.sign(usuario.pk)
    enlace = request.build_absolute_uri(
        reverse('simulactores:confirmar_correo', kwargs={'token': token})
    )
    send_mail(
        'Confirma tu cuenta en Simulactores',
        f'Hola {usuario.nombre},\n\nConfirma tu cuenta haciendo clic aquí:\n{enlace}\n\n'
        f'Este enlace vence en 48 horas.',
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email],
        fail_silently=False,
    )


def confirmar_correo_view(request, token):
    try:
        usuario_id = _signer.unsign(token, max_age=CONFIRMACION_MAX_AGE)
        usuario = Usuario.objects.get(pk=usuario_id)
    except (BadSignature, SignatureExpired, Usuario.DoesNotExist):
        return render(request, 'simulactores/confirmacion_invalida.html')

    if usuario.estado == 'Pendiente':
        usuario.estado = 'Activo'
        usuario.save(update_fields=['estado'])
    return render(request, 'simulactores/confirmacion_exitosa.html')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            messages.error(request, 'Correo o contraseña incorrectos.')
            return render(request, 'simulactores/login.html')

        if not check_password(password, usuario.password_hash):
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