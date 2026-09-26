from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .forms import RegistroClienteForm
from .models import Usuario, Rol, Bitacora, HistorialAcceso
from .permisos import modulo_requerido

# Token firmado para el enlace de confirmación de correo (sin migraciones nuevas)
_signer = TimestampSigner()
CONFIRMACION_MAX_AGE = 60 * 60 * 48  # 48 horas


def _ip_del_request(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registro_view(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            rol_cliente = Rol.objects.get(nombre='Cliente')
            usuario = Usuario.objects.create_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                nombre=form.cleaned_data['nombre'],
                telefono=form.cleaned_data.get('telefono') or None,
                rol=rol_cliente,
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
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')
        ip = _ip_del_request(request)

        usuario = authenticate(request, username=email, password=password)

        if usuario is None:
            usuario_existente = Usuario.objects.filter(email=email).first()
            HistorialAcceso.objects.create(
                usuario=usuario_existente,
                correo_intento=email,
                rol=getattr(usuario_existente.rol, 'nombre', None) if usuario_existente else None,
                resultado=HistorialAcceso.Resultado.FALLIDO,
                ip_origen=ip,
            )
            if usuario_existente and usuario_existente.estado != 'Activo':
                messages.error(request, 'Esta cuenta no está habilitada.')
            else:
                messages.error(request, 'Correo o contraseña incorrectos.')
            return render(request, 'simulactores/login.html')

        login(request, usuario)
        HistorialAcceso.objects.create(
            usuario=usuario,
            correo_intento=usuario.email,
            rol=usuario.rol.nombre,
            resultado=HistorialAcceso.Resultado.EXITOSO,
            ip_origen=ip,
        )
        return redirect('simulactores:listado_usuarios')

    return render(request, 'simulactores/login.html')


def logout_view(request):
    logout(request)
    return redirect('simulactores:login')


@login_required(login_url='simulactores:login')
def perfil_view(request):
    usuario = request.user

    if request.method == 'POST':
        nombre_anterior = usuario.nombre
        telefono_anterior = usuario.telefono

        usuario.nombre = request.POST.get('nombre')
        usuario.telefono = request.POST.get('telefono')

        nueva_password = request.POST.get('password')
        cambio_password = False
        if nueva_password:
            usuario.set_password(nueva_password)
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
                usuario=usuario,
                accion='Edición de perfil propio: ' + ', '.join(cambios),
                resultado='Exitoso'
            )
        messages.success(request, 'Perfil actualizado correctamente.')

    return render(request, 'simulactores/perfil.html', {'usuario': usuario})


@modulo_requerido('listado_usuarios')
def listado_usuarios(request):
    usuarios = Usuario.objects.select_related('rol').all().order_by('nombre')
    roles = Rol.objects.all()
    return render(request, 'simulactores/usuarios.html', {'usuarios': usuarios, 'roles': roles})


@modulo_requerido('actualizar_rol')
def actualizar_rol(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        nuevo_rol_id = request.POST.get('id_rol')
        nuevo_estado = request.POST.get('estado')
        nuevo_email = request.POST.get('email')
        rol = get_object_or_404(Rol, pk=nuevo_rol_id)

        rol_anterior = usuario.rol.nombre
        estado_anterior = usuario.estado
        email_anterior = usuario.email

        usuario.rol = rol
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
                usuario=usuario,
                accion='Edición por administrador: ' + ' | '.join(cambios),
                resultado='Exitoso'
            )

    return redirect('simulactores:listado_usuarios')


@modulo_requerido('historial_accesos')
def historial_accesos_view(request):

    registros = HistorialAcceso.objects.select_related('usuario', 'usuario__rol').all()

    filtro_usuario = request.GET.get('usuario', '')
    filtro_rol = request.GET.get('rol', '')
    filtro_desde = request.GET.get('desde', '')
    filtro_hasta = request.GET.get('hasta', '')

    if filtro_usuario:
        registros = registros.filter(usuario__id_usuario=filtro_usuario)
    if filtro_rol:
        registros = registros.filter(rol=filtro_rol)
    if filtro_desde:
        registros = registros.filter(fecha__gte=filtro_desde)
    if filtro_hasta:
        registros = registros.filter(fecha__lte=filtro_hasta)

    total_fallidos = registros.filter(resultado=HistorialAcceso.Resultado.FALLIDO).count()

    return render(request, 'simulactores/historial_accesos.html', {
        'registros': registros,
        'usuarios': Usuario.objects.all().order_by('nombre'),
        'roles': Rol.objects.all(),
        'filtro_usuario': filtro_usuario,
        'filtro_rol': filtro_rol,
        'filtro_desde': filtro_desde,
        'filtro_hasta': filtro_hasta,
        'total_fallidos': total_fallidos,
    })
