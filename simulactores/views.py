from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone

from .forms import (
    AsignarEscenarioForm, CambiarPasswordForm, CancelarSolicitudForm,
    PerfilForm, RechazarEscenarioForm, RegistroClienteForm, SolicitudForm,
)
from .models import Actor, Bitacora, HistorialAcceso, Rol, Solicitud, Usuario
from .permisos import modulo_requerido
from .utils import notificar, registrar_cambios

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
        return redirect('simulactores:home')

    return render(request, 'simulactores/login.html')


def logout_view(request):
    logout(request)
    return redirect('simulactores:login')


@login_required(login_url='simulactores:login')
def home_view(request):

    rol = getattr(request.user.rol, 'nombre', None)
    if rol == 'Cliente':
        return redirect('simulactores:dashboard_cliente')
    if rol == 'Administrador':
        return redirect('simulactores:dashboard_administrador')
    if rol == 'Actor':
        return redirect('simulactores:dashboard_actor')

    return redirect('simulactores:perfil')


@login_required(login_url='simulactores:login')
def perfil_view(request):
    usuario = request.user

    if request.method == 'POST':
        perfil_form = PerfilForm(request.POST, usuario=usuario)
        password_form = CambiarPasswordForm(request.POST, usuario=usuario)

        # Se validan los dos formularios para mostrar todos los errores a la vez.
        perfil_valido = perfil_form.is_valid()
        password_valido = password_form.is_valid()

        if perfil_valido and password_valido:
            datos = perfil_form.cleaned_data
            anteriores = {
                'nombre': usuario.nombre,
                'telefono': usuario.telefono,
            }

            # El correo es el identificador de acceso: nunca se modifica desde aquí.
            usuario.nombre = datos['nombre']
            usuario.telefono = datos['telefono']

            nueva_password = password_form.cleaned_data.get('password')
            if nueva_password:
                usuario.set_password(nueva_password)

            usuario.save()

            if nueva_password:
                # Mantiene la sesión abierta después de cambiar la contraseña.
                update_session_auth_hash(request, usuario)

            cambios = [
                (campo, anterior, getattr(usuario, campo))
                for campo, anterior in anteriores.items()
                if anterior != getattr(usuario, campo)
            ]
            if nueva_password:
                cambios.append(('password', '(oculto)', '(oculto)'))

            registrar_cambios(
                usuario, 'Edición de perfil propio', cambios,
                realizado_por=usuario, ip_origen=_ip_del_request(request),
            )
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('simulactores:perfil')

        return render(request, 'simulactores/perfil.html', {
            'usuario': usuario,
            'perfil_form': perfil_form,
            'password_form': password_form,
        })

    return render(request, 'simulactores/perfil.html', {
        'usuario': usuario,
        'perfil_form': PerfilForm(
            initial={
                'nombre': usuario.nombre,
                'telefono': usuario.telefono or '',
            },
            usuario=usuario,
        ),
        'password_form': CambiarPasswordForm(usuario=usuario),
    })


@modulo_requerido('listado_usuarios')
def listado_usuarios(request):
    usuarios = Usuario.objects.select_related('rol').all().order_by('nombre')

    busqueda = request.GET.get('q', '').strip()
    filtro_rol = request.GET.get('rol', '')
    filtro_estado = request.GET.get('estado', '')

    if busqueda:
        usuarios = usuarios.filter(
            Q(nombre__icontains=busqueda) | Q(email__icontains=busqueda)
        )
    if filtro_rol:
        usuarios = usuarios.filter(rol__id_rol=filtro_rol)
    if filtro_estado:
        usuarios = usuarios.filter(estado=filtro_estado)

    paginador = Paginator(usuarios, 10)
    pagina = request.GET.get('pagina')
    usuarios_pagina = paginador.get_page(pagina)

    roles = Rol.objects.all()
    return render(request, 'simulactores/usuarios.html', {
        'usuarios': usuarios_pagina,
        'roles': roles,
        'busqueda': busqueda,
        'filtro_rol': filtro_rol,
        'filtro_estado': filtro_estado,
        'estados': Usuario.ESTADO_CHOICES,
    })


@modulo_requerido('actualizar_rol')
def actualizar_rol(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        nuevo_rol_id = request.POST.get('id_rol')
        nuevo_estado = request.POST.get('estado')

        rol = get_object_or_404(Rol, pk=nuevo_rol_id)

        rol_anterior = usuario.rol.nombre
        estado_anterior = usuario.estado

        usuario.rol = rol
        usuario.estado = nuevo_estado
        usuario.save()

        cambios = []
        if rol_anterior != rol.nombre:
            cambios.append(('rol', rol_anterior, rol.nombre))
        if estado_anterior != nuevo_estado:
            cambios.append(('estado', estado_anterior, nuevo_estado))

        registrar_cambios(
            usuario, 'Edición por administrador', cambios,
            realizado_por=request.user, ip_origen=_ip_del_request(request),
        )

    return redirect('simulactores:listado_usuarios')


@modulo_requerido('bitacora_actividad')
def bitacora_actividad_view(request):

    accesos = HistorialAcceso.objects.select_related('usuario', 'usuario__rol').all()
    cambios = Bitacora.objects.select_related('usuario', 'usuario__rol', 'realizado_por').all()

    filtro_usuario = request.GET.get('usuario', '')
    filtro_rol = request.GET.get('rol', '')
    filtro_tipo = request.GET.get('tipo', '')  # '' | 'acceso' | 'cambio'
    filtro_desde = request.GET.get('desde', '')
    filtro_hasta = request.GET.get('hasta', '')

    if filtro_usuario:
        accesos = accesos.filter(usuario__id_usuario=filtro_usuario)
        cambios = cambios.filter(usuario__id_usuario=filtro_usuario)
    if filtro_desde:
        accesos = accesos.filter(fecha__gte=filtro_desde)
        cambios = cambios.filter(fecha__date__gte=filtro_desde)
    if filtro_hasta:
        accesos = accesos.filter(fecha__lte=filtro_hasta)
        cambios = cambios.filter(fecha__date__lte=filtro_hasta)

    total_fallidos = accesos.filter(resultado=HistorialAcceso.Resultado.FALLIDO).count()

    eventos = []

    if filtro_tipo in ('', 'acceso'):
        for a in accesos:
            if a.hora:
                fecha_hora = datetime.combine(a.fecha, a.hora)

                if timezone.is_naive(fecha_hora):
                    fecha_hora = timezone.make_aware(fecha_hora)
            else:
                fecha_hora = a.fecha
            eventos.append({
                'fecha': fecha_hora,
                'usuario': a.usuario,
                'usuario_label': a.usuario.nombre if a.usuario else (a.correo_intento or '—'),
                'rol': a.rol,
                'tipo': 'Inicio de sesión',
                'detalle': 'Acceso exitoso' if a.resultado == HistorialAcceso.Resultado.EXITOSO else 'Intento fallido',
                'resultado': a.resultado,
                'ip': a.ip_origen,
                'realizado_por_label': None,
            })

    if filtro_tipo in ('', 'cambio'):
        for b in cambios:
            if b.campo_modificado:
                detalle = f'{b.campo_modificado}: {b.valor_anterior or "—"} → {b.valor_nuevo or "—"}'
            else:
                detalle = b.accion
            eventos.append({
                'fecha': b.fecha,
                'usuario': b.usuario,
                'usuario_label': b.usuario.nombre if b.usuario else '—',
                'rol': getattr(b.usuario.rol, 'nombre', None) if b.usuario else None,
                'tipo': b.accion,
                'detalle': detalle,
                'resultado': b.resultado,
                'ip': b.ip_origen,
                'realizado_por_label': b.realizado_por.nombre if b.realizado_por and b.realizado_por_id != b.usuario_id else None,
            })

    if filtro_rol:
        eventos = [e for e in eventos if e['rol'] == filtro_rol]

    eventos.sort(key=lambda e: e['fecha'], reverse=True)

    paginador = Paginator(eventos, 20)
    pagina = request.GET.get('pagina')
    eventos_pagina = paginador.get_page(pagina)

    return render(request, 'simulactores/bitacora_actividad.html', {
        'eventos': eventos_pagina,
        'usuarios': Usuario.objects.all().order_by('nombre'),
        'roles': Rol.objects.all(),
        'filtro_usuario': filtro_usuario,
        'filtro_rol': filtro_rol,
        'filtro_tipo': filtro_tipo,
        'filtro_desde': filtro_desde,
        'filtro_hasta': filtro_hasta,
        'total_fallidos': total_fallidos,
    })


@modulo_requerido('dashboard_administrador')
def dashboard_administrador_view(request):

    usuarios = Usuario.objects.all()
    solicitudes = Solicitud.objects.all()

    resumen = {
        'usuarios_total': usuarios.count(),
        'usuarios_activos': usuarios.filter(estado='Activo').count(),
        'solicitudes_pendientes': solicitudes.filter(estado=Solicitud.Estado.PENDIENTE).count(),
        'solicitudes_en_revision': solicitudes.filter(estado=Solicitud.Estado.EN_REVISION).count(),
        'solicitudes_confirmadas': solicitudes.filter(estado=Solicitud.Estado.CONFIRMADA).count(),
        'intentos_fallidos_recientes': HistorialAcceso.objects.filter(
            resultado=HistorialAcceso.Resultado.FALLIDO
        ).count(),
    }

    solicitudes_recientes = solicitudes.select_related('cliente', 'escenario').order_by('-fecha_solicitud')[:5]

    return render(request, 'simulactores/dashboard_administrador.html', {
        'resumen': resumen,
        'solicitudes_recientes': solicitudes_recientes,
    })


@modulo_requerido('dashboard_actor')
def dashboard_actor_view(request):

    actor = Actor.objects.filter(usuario=request.user).select_related('usuario').first()
    asignaciones = []
    resumen = {'total': 0, 'pendientes': 0, 'confirmadas': 0}

    if actor:
        asignaciones = actor.asignaciones.select_related('solicitud').order_by('-id_asignacion')
        resumen = {
            'total': asignaciones.count(),
            'pendientes': asignaciones.filter(estado='Pendiente').count(),
            'confirmadas': asignaciones.filter(estado='Confirmada').count(),
        }

    return render(request, 'simulactores/dashboard_actor.html', {
        'actor': actor,
        'asignaciones': asignaciones,
        'resumen': resumen,
    })


@modulo_requerido('gestion_solicitudes')
def solicitudes_admin_view(request):

    solicitudes = Solicitud.objects.select_related('cliente', 'escenario').all().order_by('-fecha_solicitud')

    filtro_estado = request.GET.get('estado', '')
    busqueda = request.GET.get('q', '').strip()

    if filtro_estado:
        solicitudes = solicitudes.filter(estado=filtro_estado)
    if busqueda:
        solicitudes = solicitudes.filter(
            Q(numero_solicitud__icontains=busqueda)
            | Q(cliente__nombre__icontains=busqueda)
            | Q(cliente__email__icontains=busqueda)
        )

    paginador = Paginator(solicitudes, 10)
    pagina = request.GET.get('pagina')
    solicitudes_pagina = paginador.get_page(pagina)

    return render(request, 'simulactores/solicitudes_admin.html', {
        'solicitudes': solicitudes_pagina,
        'busqueda': busqueda,
        'filtro_estado': filtro_estado,
        'estados': Solicitud.Estado.choices,
    })


@modulo_requerido('gestion_solicitudes')
def solicitud_admin_detalle_view(request, solicitud_uuid):

    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'escenario'), uuid=solicitud_uuid
    )

    form = AsignarEscenarioForm(initial={'escenario': solicitud.escenario_id})

    if request.method == 'POST':
        form = AsignarEscenarioForm(request.POST)
        if form.is_valid():
            if solicitud.estado not in (Solicitud.Estado.PENDIENTE, Solicitud.Estado.EN_REVISION):
                messages.error(request, 'Esta solicitud ya no está en un estado donde se pueda proponer un escenario.')
                return redirect('simulactores:solicitud_admin_detalle', solicitud_uuid=solicitud.uuid)

            escenario_anterior = solicitud.escenario.nombre if solicitud.escenario else None
            estado_anterior = solicitud.estado

            solicitud.escenario = form.cleaned_data['escenario']
            if solicitud.estado == Solicitud.Estado.PENDIENTE:
                solicitud.estado = Solicitud.Estado.EN_REVISION
            solicitud.save()

            cambios = [('escenario', escenario_anterior, solicitud.escenario.nombre)]
            if estado_anterior != solicitud.estado:
                cambios.append(('estado', estado_anterior, solicitud.estado))

            registrar_cambios(
                solicitud.cliente, 'Escenario propuesto por administrador', cambios,
                realizado_por=request.user, ip_origen=_ip_del_request(request),
            )
            notificar(
                solicitud.cliente,
                f'Te propusimos un escenario para tu solicitud {solicitud.numero_solicitud}. Revísalo y apruébalo o recházalo.',
                asunto='Escenario propuesto en SimGest',
            )
            messages.success(request, 'Escenario propuesto correctamente. El cliente fue notificado.')
            return redirect('simulactores:solicitud_admin_detalle', solicitud_uuid=solicitud.uuid)

    return render(request, 'simulactores/solicitud_admin_detalle.html', {
        'solicitud': solicitud,
        'form': form,
    })




def _es_cliente(request):
    return getattr(request.user.rol, 'nombre', None) == 'Cliente'


# HU 11 - Resumen del dashboard del cliente
# Las solicitudes "activas" son todas las que no están completadas ni canceladas
# (incluye Actor Asignado, que está entre Aprobada y Confirmada en el flujo).
ESTADOS_HISTORIAL = (Solicitud.Estado.COMPLETADA, Solicitud.Estado.CANCELADA)

# Orden y color (clase "estado-<clase>" / "seg-<clase>") del indicador de estados activos.
INDICADOR_ACTIVAS = (
    (Solicitud.Estado.PENDIENTE, 'pe'),
    (Solicitud.Estado.EN_REVISION, 'rv'),
    (Solicitud.Estado.APROBADA, 'ap'),
    (Solicitud.Estado.ACTOR_ASIGNADO, 'as'),
    (Solicitud.Estado.CONFIRMADA, 'ok'),
)


@modulo_requerido('dashboard_cliente')
def dashboard_cliente_view(request):

    todas = Solicitud.objects.filter(cliente=request.user)
    activas = (
        todas.exclude(estado__in=ESTADOS_HISTORIAL)
        .select_related('escenario')
        .order_by('-fecha_solicitud')
    )

    # Una sola consulta con el conteo por estado.
    conteo = {
        fila['estado']: fila['n']
        for fila in todas.values('estado').annotate(n=Count('pk')).order_by()
    }

    indicador = [
        {
            'etiqueta': estado.label,
            'clase': clase,
            'cantidad': conteo.get(estado.value, 0),
        }
        for estado, clase in INDICADOR_ACTIVAS
        if conteo.get(estado.value, 0)
    ]

    completadas = conteo.get(Solicitud.Estado.COMPLETADA.value, 0)
    canceladas = conteo.get(Solicitud.Estado.CANCELADA.value, 0)

    resumen = {
        'total': sum(conteo.values()),
        'activas': sum(item['cantidad'] for item in indicador),
        'completadas': completadas,
        'canceladas': canceladas,
        'historial': completadas + canceladas,
    }

    return render(request, 'simulactores/dashboard_cliente.html', {
        'solicitudes': activas,
        'resumen': resumen,
        'indicador': indicador,
    })


@modulo_requerido('dashboard_cliente')
def historial_solicitudes_view(request):

    solicitudes = (
        Solicitud.objects.filter(cliente=request.user, estado__in=ESTADOS_HISTORIAL)
        .select_related('escenario')
        .order_by('-fecha_solicitud')
    )

    filtro_estado = request.GET.get('estado', '')
    if filtro_estado in ESTADOS_HISTORIAL:
        solicitudes = solicitudes.filter(estado=filtro_estado)
    else:
        filtro_estado = ''

    paginador = Paginator(solicitudes, 10)
    solicitudes_pagina = paginador.get_page(request.GET.get('pagina'))

    return render(request, 'simulactores/historial_solicitudes.html', {
        'solicitudes': solicitudes_pagina,
        'filtro_estado': filtro_estado,
    })


@modulo_requerido('dashboard_cliente')
def crear_solicitud_view(request):

    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.cliente = request.user
            solicitud.save()

            registrar_cambios(
                request.user, 'Creación de solicitud',
                [('numero_solicitud', None, solicitud.numero_solicitud)],
                realizado_por=request.user, ip_origen=_ip_del_request(request),
            )
            notificar(
                request.user,
                f'Tu solicitud {solicitud.numero_solicitud} fue registrada y está Pendiente de revisión.',
                asunto='Solicitud registrada en SimGest',
            )

            for admin_usuario in Usuario.objects.filter(rol__nombre='Administrador', estado='Activo'):
                notificar(
                    admin_usuario,
                    f'Hay una nueva solicitud {solicitud.numero_solicitud} pendiente de revisión.',
                    asunto='Nueva solicitud en SimGest',
                )

            messages.success(request, f'Solicitud {solicitud.numero_solicitud} creada correctamente.')
            return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)
    else:
        form = SolicitudForm()

    return render(request, 'simulactores/solicitud_form.html', {'form': form})


def _obtener_solicitud_del_cliente(request, solicitud_uuid):

    return get_object_or_404(Solicitud, uuid=solicitud_uuid, cliente=request.user)


@modulo_requerido('dashboard_cliente')
def detalle_solicitud_view(request, solicitud_uuid):

    try:
        solicitud = _obtener_solicitud_del_cliente(request, solicitud_uuid)
    except Http404:
        return render(request, 'simulactores/solicitud_no_encontrada.html', status=404)

    return render(request, 'simulactores/solicitud_detalle.html', {
        'solicitud': solicitud,
        'rechazar_form': RechazarEscenarioForm(),
        'cancelar_form': CancelarSolicitudForm(),
    })


@modulo_requerido('dashboard_cliente')
def aprobar_escenario_view(request, solicitud_uuid):

    try:
        solicitud = _obtener_solicitud_del_cliente(request, solicitud_uuid)
    except Http404:
        return render(request, 'simulactores/solicitud_no_encontrada.html', status=404)

    if request.method != 'POST' or not solicitud.esperando_aprobacion_cliente():
        if solicitud.plazo_aprobacion_vencido():
            messages.error(request, 'El plazo para aprobar o rechazar este escenario ya venció. Por favor contacta al administrador.')
        return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)

    estado_anterior = solicitud.estado
    solicitud.estado = Solicitud.Estado.APROBADA
    solicitud.save()

    registrar_cambios(
        request.user, 'Aprobación de escenario propuesto',
        [('estado', estado_anterior, solicitud.estado)],
        realizado_por=request.user, ip_origen=_ip_del_request(request),
    )
    for admin_usuario in Usuario.objects.filter(rol__nombre='Administrador', estado='Activo'):
        notificar(
            admin_usuario,
            f'El cliente aprobó el escenario propuesto para la solicitud {solicitud.numero_solicitud}.',
            asunto='Escenario aprobado en SimGest',
        )
    messages.success(request, 'Escenario aprobado correctamente.')
    return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)


@modulo_requerido('dashboard_cliente')
def rechazar_escenario_view(request, solicitud_uuid):

    try:
        solicitud = _obtener_solicitud_del_cliente(request, solicitud_uuid)
    except Http404:
        return render(request, 'simulactores/solicitud_no_encontrada.html', status=404)

    if not solicitud.esperando_aprobacion_cliente():
        if solicitud.plazo_aprobacion_vencido():
            messages.error(request, 'El plazo para aprobar o rechazar este escenario ya venció. Por favor contacta al administrador.')
        return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)

    if request.method == 'POST':
        form = RechazarEscenarioForm(request.POST)
        if form.is_valid():
            estado_anterior = solicitud.estado
            solicitud.estado = Solicitud.Estado.PENDIENTE
            solicitud.comentario_rechazo = form.cleaned_data['comentario']
            solicitud.escenario = None
            solicitud.fecha_limite_aprobacion = None
            solicitud.save()

            registrar_cambios(
                request.user, 'Rechazo de escenario propuesto',
                [
                    ('estado', estado_anterior, solicitud.estado),
                    ('comentario_rechazo', None, solicitud.comentario_rechazo),
                ],
                realizado_por=request.user, ip_origen=_ip_del_request(request),
            )
            for admin_usuario in Usuario.objects.filter(rol__nombre='Administrador', estado='Activo'):
                notificar(
                    admin_usuario,
                    f'El cliente rechazó el escenario propuesto para la solicitud {solicitud.numero_solicitud}: {solicitud.comentario_rechazo}',
                    asunto='Escenario rechazado en SimGest',
                )
            messages.success(request, 'Escenario rechazado. La solicitud vuelve a estar Pendiente de reasignación.')
            return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)
    else:
        form = RechazarEscenarioForm()

    return render(request, 'simulactores/solicitud_detalle.html', {
        'solicitud': solicitud,
        'rechazar_form': form,
        'cancelar_form': CancelarSolicitudForm(),
        'mostrar_modal_rechazo': True,
    })


@modulo_requerido('dashboard_cliente')
def cancelar_solicitud_view(request, solicitud_uuid):

    try:
        solicitud = _obtener_solicitud_del_cliente(request, solicitud_uuid)
    except Http404:
        return render(request, 'simulactores/solicitud_no_encontrada.html', status=404)

    if not solicitud.puede_cancelar():
        messages.error(request, 'Esta solicitud ya tiene un actor confirmado; para cancelarla debes contactar al administrador.')
        return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)

    if request.method == 'POST':
        form = CancelarSolicitudForm(request.POST)
        if form.is_valid():
            estado_anterior = solicitud.estado
            solicitud.estado = Solicitud.Estado.CANCELADA
            solicitud.motivo_cancelacion = form.cleaned_data.get('motivo') or None
            solicitud.save()

            registrar_cambios(
                request.user, 'Cancelación de solicitud',
                [('estado', estado_anterior, solicitud.estado)],
                realizado_por=request.user, ip_origen=_ip_del_request(request),
            )
            for admin_usuario in Usuario.objects.filter(rol__nombre='Administrador', estado='Activo'):
                notificar(
                    admin_usuario,
                    f'El cliente canceló la solicitud {solicitud.numero_solicitud}.',
                    asunto='Solicitud cancelada en SimGest',
                )
            messages.success(request, f'Solicitud {solicitud.numero_solicitud} cancelada. La fecha queda libre nuevamente.')
            return redirect('simulactores:dashboard_cliente')

    return redirect('simulactores:detalle_solicitud', solicitud_uuid=solicitud.uuid)
