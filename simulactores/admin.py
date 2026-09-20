from django.contrib import admin
from .models import Usuario, Rol, Bitacora

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('id_rol', 'nombre')

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_usuario', 'nombre', 'email', 'id_rol', 'estado')

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ('id_bitacora', 'id_usuario', 'accion', 'resultado', 'fecha', 'hora')