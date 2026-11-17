from django.db import migrations


def crear_rol(apps, schema_editor):
    Rol = apps.get_model('simulactores', 'Rol')
    Rol.objects.get_or_create(nombre='Contador')


def quitar_rol(apps, schema_editor):
    Rol = apps.get_model('simulactores', 'Rol')
    Usuario = apps.get_model('simulactores', 'Usuario')
    rol = Rol.objects.filter(nombre='Contador').first()
    if rol and not Usuario.objects.filter(rol=rol).exists():
        rol.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0011_modalidades_tarifas'),
    ]

    operations = [
        migrations.RunPython(crear_rol, quitar_rol),
    ]
