from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.conf import settings
from django.db import models


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un correo electrónico.')
        email = self.normalize_email(email)
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('estado', 'Activo')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')
        if not extra_fields.get('rol'):
            extra_fields['rol'], _ = Rol.objects.get_or_create(nombre='Administrador')
        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):

    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente de confirmación'),
        ('Activo', 'Activo'),
        ('Desactivado', 'Desactivado'),
    ]

    id_usuario = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=150, unique=True)
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column='id_rol', related_name='usuarios')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return self.nombre

    def get_full_name(self):
        return self.nombre

    def get_short_name(self):
        return self.nombre

    @property
    def is_active(self):
        return self.estado == 'Activo'


MATRIZ_PERMISOS = {
    'Administrador': {
        'listado_usuarios', 'actualizar_rol', 'historial_accesos',
        'perfil', 'biblioteca_escenarios',
    },
    'Actor': {'perfil', 'dashboard_actor'},
    'Cliente': {'perfil', 'dashboard_cliente'},
}


class Habilidad(models.Model):
    id_habilidad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'habilidad'

    def __str__(self):
        return self.nombre



class Actor(models.Model):

    class TipoTarifa(models.TextChoices):
        POR_HORA = 'Por Hora', 'Por Hora'
        POR_EVENTO = 'Por Evento', 'Por Evento'

    class EstadoActor(models.TextChoices):
        ACTIVO = 'Activo', 'Activo'
        INACTIVO = 'Inactivo', 'Inactivo'

    id_actor = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        db_column='id_usuario', related_name='actor',
    )
    fecha_nacimiento = models.DateField(null=True, blank=True)
    genero = models.CharField(max_length=20, null=True, blank=True)
    habilidades = models.ManyToManyField(Habilidad, blank=True, related_name='actores')
    tarifa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tipo_tarifa = models.CharField(max_length=20, choices=TipoTarifa.choices, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoActor.choices, default=EstadoActor.ACTIVO)

    class Meta:
        db_table = 'actor'

    def __str__(self):
        return self.usuario.nombre


class TarifaActor(models.Model):

    id_tarifa = models.AutoField(primary_key=True)
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name='historial_tarifas')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    tipo_tarifa = models.CharField(max_length=20, choices=Actor.TipoTarifa.choices)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)  # null = vigente actualmente

    class Meta:
        db_table = 'tarifa_actor'
        ordering = ['-vigente_desde']

    def __str__(self):
        return f'{self.actor} - {self.monto} ({self.vigente_desde})'

    @classmethod
    def vigente_en(cls, actor, fecha):

        return cls.objects.filter(
            actor=actor, vigente_desde__lte=fecha
        ).filter(
            models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha)
        ).order_by('-vigente_desde').first()


class Disponibilidad(models.Model):

    class TipoBloque(models.TextChoices):
        DISPONIBLE = 'Disponible', 'Disponible'
        BLOQUEADO = 'Bloqueado', 'Bloqueado'

    id_disponibilidad = models.AutoField(primary_key=True)
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, db_column='id_actor', related_name='disponibilidades')
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tipo_bloque = models.CharField(max_length=20, choices=TipoBloque.choices, default=TipoBloque.DISPONIBLE)

    class Meta:
        db_table = 'disponibilidad'



class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class TipoSimulacion(models.TextChoices):

    ECOE = 'Examen ECOE', 'Examen ECOE (Evaluación Clínica Objetiva Estructurada)'
    MANEJO_CRISIS = 'Manejo de Crisis', 'Manejo de Crisis (CRM)'
    COMUNICACION_SPIKES = 'Comunicación SPIKES', 'Comunicación SPIKES'
    SEGURIDAD_PACIENTE = 'Seguridad del Paciente', 'Seguridad del Paciente'
    SIMULACION_CORPORATIVA = 'Simulación Corporativa', 'Simulación Corporativa'
    OTRO = 'Otro', 'Otro'


class Escenario(models.Model):

    class Estado(models.TextChoices):
        ACTIVO = 'Activo', 'Activo'
        ARCHIVADO = 'Archivado', 'Archivado'

    id_escenario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField(null=True, blank=True)
    guion = models.TextField(null=True, blank=True)
    tipo = models.CharField(max_length=30, choices=TipoSimulacion.choices, default=TipoSimulacion.OTRO)
    categorias = models.ManyToManyField(Categoria, related_name='escenarios', blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)

    class Meta:
        db_table = 'escenario'

    def __str__(self):
        return self.nombre



class Solicitud(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente', 'Pendiente'
        EN_REVISION = 'En Revisión', 'En Revisión'
        APROBADA = 'Aprobada', 'Aprobada'
        ACTOR_ASIGNADO = 'Actor Asignado', 'Actor Asignado'
        CONFIRMADA = 'Confirmada', 'Confirmada'
        COMPLETADA = 'Completada', 'Completada'
        CANCELADA = 'Cancelada', 'Cancelada'

    TRANSICIONES_VALIDAS = {
        Estado.PENDIENTE: {Estado.EN_REVISION, Estado.CANCELADA},
        Estado.EN_REVISION: {Estado.APROBADA, Estado.PENDIENTE, Estado.CANCELADA},
        Estado.APROBADA: {Estado.ACTOR_ASIGNADO, Estado.CANCELADA},
        Estado.ACTOR_ASIGNADO: {Estado.CONFIRMADA, Estado.CANCELADA},
        Estado.CONFIRMADA: {Estado.COMPLETADA, Estado.CANCELADA},
        Estado.COMPLETADA: set(),
        Estado.CANCELADA: set(),
    }

    id_solicitud = models.AutoField(primary_key=True)
    numero_solicitud = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='id_cliente', related_name='solicitudes',
    )
    escenario = models.ForeignKey(
        Escenario, on_delete=models.SET_NULL, db_column='id_escenario',
        null=True, blank=True, related_name='solicitudes',
    )
    tipo_simulacion = models.CharField(max_length=30, choices=TipoSimulacion.choices)
    cantidad_interpretes = models.IntegerField(default=1)
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_evento = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    observaciones = models.TextField(null=True, blank=True)
    motivo_cancelacion = models.TextField(null=True, blank=True)
    comentario_rechazo = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'solicitud'

    def __str__(self):
        return self.numero_solicitud

    def save(self, *args, **kwargs):
        if not self.numero_solicitud:
            from datetime import date
            anio = self.fecha_evento.year if self.fecha_evento else date.today().year
            consecutivo = Solicitud.objects.filter(
                numero_solicitud__startswith=f'SIM-{anio}-'
            ).count() + 1
            self.numero_solicitud = f'SIM-{anio}-{consecutivo:04d}'
        super().save(*args, **kwargs)

    def puede_transicionar_a(self, nuevo_estado):
        return nuevo_estado in self.TRANSICIONES_VALIDAS.get(self.estado, set())



class Asignacion(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente', 'Pendiente de confirmación'
        CONFIRMADA = 'Confirmada', 'Confirmada'
        RECHAZADA = 'Rechazada', 'Rechazada'
        EJECUTADA = 'Ejecutada', 'Ejecutada'
        CANCELADA = 'Cancelada', 'Cancelada'

    id_asignacion = models.AutoField(primary_key=True)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, db_column='id_solicitud', related_name='asignaciones')
    actor = models.ForeignKey(Actor, on_delete=models.PROTECT, db_column='id_actor', related_name='asignaciones')
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.TextField(null=True, blank=True)
    hora_inicio_real = models.TimeField(null=True, blank=True)
    hora_fin_real = models.TimeField(null=True, blank=True)
    tarifa_aplicada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'asignacion'

    def horas_ejecutadas(self):
        """Duración real (HU-31): hora_fin_real - hora_inicio_real."""
        if self.hora_inicio_real and self.hora_fin_real:
            from datetime import datetime
            inicio = datetime.combine(self.solicitud.fecha_evento, self.hora_inicio_real)
            fin = datetime.combine(self.solicitud.fecha_evento, self.hora_fin_real)
            return (fin - inicio).total_seconds() / 3600
        return None


class Pago(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = 'Pendiente', 'Pendiente'
        PAGADO = 'Pagado', 'Pagado'
        ANULADO = 'Anulado', 'Anulado'

    class MetodoPago(models.TextChoices):
        TRANSFERENCIA = 'Transferencia', 'Transferencia'
        EFECTIVO = 'Efectivo', 'Efectivo'
        SINPE = 'SINPE Móvil', 'SINPE Móvil'
        OTRO = 'Otro', 'Otro'

    id_pago = models.AutoField(primary_key=True)
    actor = models.ForeignKey(Actor, on_delete=models.PROTECT, db_column='id_actor', related_name='pagos')
    periodo_mes = models.PositiveSmallIntegerField()
    periodo_anio = models.PositiveSmallIntegerField()
    asignaciones = models.ManyToManyField(
        Asignacion, related_name='pagos', blank=True,
        help_text='Asignaciones ejecutadas cubiertas por este pago mensual.',
    )
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices, null=True, blank=True)
    referencia = models.CharField(max_length=100, null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)

    class Meta:
        db_table = 'pago'
        unique_together = ('actor', 'periodo_mes', 'periodo_anio')

    def __str__(self):
        return f'{self.actor} - {self.periodo_mes}/{self.periodo_anio}'


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='id_usuario', related_name='notificaciones')
    mensaje = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        db_table = 'notificacion'


class Bitacora(models.Model):
    id_bitacora = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='id_usuario', related_name='bitacoras')
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    accion = models.CharField(max_length=150)
    resultado = models.CharField(max_length=50, null=True, blank=True)
    ip_origen = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = 'bitacora'


class HistorialAcceso(models.Model):


    class Resultado(models.TextChoices):
        EXITOSO = 'Exitoso', 'Exitoso'
        FALLIDO = 'Fallido', 'Fallido'

    id_historial = models.AutoField(primary_key=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='id_usuario',
        related_name='historial_accesos', null=True, blank=True,
    )
    correo_intento = models.EmailField(max_length=150, null=True, blank=True)
    rol = models.CharField(max_length=50, null=True, blank=True)
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    ip_origen = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = 'historial_acceso'
        ordering = ['-fecha', '-hora']
