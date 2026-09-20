from django.db import models


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column='id_rol')
    nombre = models.CharField(max_length=150)
    email = models.EmailField(max_length=150, unique=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    password_hash = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, default='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return self.nombre


class Actor(models.Model):
    id_actor = models.AutoField(primary_key=True)
    id_usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, db_column='id_usuario')
    edad = models.IntegerField(null=True, blank=True)
    genero = models.CharField(max_length=20, null=True, blank=True)
    habilidades = models.TextField(null=True, blank=True)
    tarifa = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tipo_tarifa = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        db_table = 'actor'

    def __str__(self):
        return self.id_usuario.nombre


class Disponibilidad(models.Model):
    id_disponibilidad = models.AutoField(primary_key=True)
    id_actor = models.ForeignKey(Actor, on_delete=models.CASCADE, db_column='id_actor', related_name='disponibilidades')
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        db_table = 'disponibilidad'


class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class Escenario(models.Model):
    id_escenario = models.AutoField(primary_key=True)
    id_categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column='id_categoria')
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'escenario'

    def __str__(self):
        return self.nombre


class Solicitud(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='id_cliente', related_name='solicitudes')
    id_escenario = models.ForeignKey(Escenario, on_delete=models.SET_NULL, db_column='id_escenario', null=True, blank=True)
    cantidad_interpretes = models.IntegerField(default=1)
    estado = models.CharField(max_length=30, default='Pendiente')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_evento = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'solicitud'


class Asignacion(models.Model):
    id_asignacion = models.AutoField(primary_key=True)
    id_solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, db_column='id_solicitud', related_name='asignaciones')
    id_actor = models.ForeignKey(Actor, on_delete=models.PROTECT, db_column='id_actor')
    estado = models.CharField(max_length=30, default='Pendiente')

    class Meta:
        db_table = 'asignacion'


class Pago(models.Model):
    id_pago = models.AutoField(primary_key=True)
    id_asignacion = models.ForeignKey(Asignacion, on_delete=models.PROTECT, db_column='id_asignacion')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=30, default='Pendiente')

    class Meta:
        db_table = 'pago'


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='id_usuario')
    mensaje = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        db_table = 'notificacion'


class Bitacora(models.Model):
    id_bitacora = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='id_usuario')
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    accion = models.CharField(max_length=150)
    resultado = models.CharField(max_length=50, null=True, blank=True)
    ip_origen = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = 'bitacora'


class HistorialAcceso(models.Model):
    id_historial = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='id_usuario')
    fecha = models.DateField(auto_now_add=True)
    hora = models.TimeField(auto_now_add=True)
    resultado = models.CharField(max_length=50, null=True, blank=True)
    ip_origen = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = 'historial_acceso'