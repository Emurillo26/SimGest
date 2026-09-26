from django.db import migrations


def crear_roles(apps, schema_editor):
    Rol = apps.get_model('simulactores', 'Rol')
    for nombre in ('Cliente', 'Actor', 'Administrador'):
        Rol.objects.get_or_create(nombre=nombre)


def eliminar_roles(apps, schema_editor):
    Rol = apps.get_model('simulactores', 'Rol')
    Rol.objects.filter(nombre__in=('Cliente', 'Actor', 'Administrador')).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_roles, eliminar_roles),
    ]
