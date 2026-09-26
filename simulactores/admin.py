from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Usuario, Rol, Bitacora, HistorialAcceso, Habilidad, Actor, TarifaActor,
    Disponibilidad, Categoria, Escenario, Solicitud, Asignacion, Pago,
    Notificacion,
)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('id_rol', 'nombre')


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    model = Usuario
    list_display = ('id_usuario', 'nombre', 'email', 'rol', 'estado', 'is_staff')
    list_filter = ('rol', 'estado', 'is_staff')
    search_fields = ('nombre', 'email')
    ordering = ('nombre',)
    filter_horizontal = ()
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Datos personales', {'fields': ('nombre', 'telefono', 'rol', 'estado')}),
        ('Permisos', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'rol', 'password1', 'password2'),
        }),
    )


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ('id_bitacora', 'usuario', 'accion', 'resultado', 'fecha', 'hora')


@admin.register(HistorialAcceso)
class HistorialAccesoAdmin(admin.ModelAdmin):
    list_display = ('id_historial', 'usuario', 'correo_intento', 'rol', 'resultado', 'fecha', 'hora', 'ip_origen')
    list_filter = ('resultado', 'rol', 'fecha')
    search_fields = ('correo_intento', 'usuario__nombre', 'usuario__email')


@admin.register(Habilidad)
class HabilidadAdmin(admin.ModelAdmin):
    list_display = ('id_habilidad', 'nombre')


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ('id_actor', 'usuario', 'fecha_nacimiento', 'genero', 'tarifa', 'tipo_tarifa', 'estado')
    filter_horizontal = ('habilidades',)


@admin.register(TarifaActor)
class TarifaActorAdmin(admin.ModelAdmin):
    list_display = ('id_tarifa', 'actor', 'monto', 'tipo_tarifa', 'vigente_desde', 'vigente_hasta')


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('id_disponibilidad', 'actor', 'fecha', 'hora_inicio', 'hora_fin', 'tipo_bloque')
    list_filter = ('tipo_bloque',)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id_categoria', 'nombre')


@admin.register(Escenario)
class EscenarioAdmin(admin.ModelAdmin):
    list_display = ('id_escenario', 'nombre', 'tipo', 'estado')
    list_filter = ('tipo', 'estado', 'categorias')
    filter_horizontal = ('categorias',)


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ('numero_solicitud', 'cliente', 'tipo_simulacion', 'estado', 'fecha_evento')
    list_filter = ('estado', 'tipo_simulacion')
    search_fields = ('numero_solicitud', 'cliente__nombre', 'cliente__email')


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('id_asignacion', 'solicitud', 'actor', 'estado', 'tarifa_aplicada')
    list_filter = ('estado',)


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id_pago', 'actor', 'periodo_mes', 'periodo_anio', 'monto_total', 'estado')
    list_filter = ('estado', 'periodo_anio', 'periodo_mes')
    filter_horizontal = ('asignaciones',)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id_notificacion', 'usuario', 'mensaje', 'fecha', 'leido')
