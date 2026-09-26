from django.contrib.auth.hashers import make_password
from django.db import migrations


CUENTAS_DESARROLLO = [
    {
        'email': 'cliente@simgest.com',
        'password': 'Cliente123!',
        'nombre': 'Cliente de Prueba',
        'rol': 'Cliente',
    },
    {
        'email': 'actor@simgest.com',
        'password': 'Actor123!',
        'nombre': 'Actor de Prueba',
        'rol': 'Actor',
    },
    {
        'email': 'admin@simgest.com',
        'password': 'Admin123!',
        'nombre': 'Administrador de Prueba',
        'rol': 'Administrador',
    },
]


def crear_cuentas(apps, schema_editor):
    Usuario = apps.get_model('simulactores', 'Usuario')
    Rol = apps.get_model('simulactores', 'Rol')
    Actor = apps.get_model('simulactores', 'Actor')

    for datos in CUENTAS_DESARROLLO:
        if Usuario.objects.filter(email=datos['email']).exists():
            continue
        rol = Rol.objects.get(nombre=datos['rol'])
        usuario = Usuario(
            email=datos['email'],
            nombre=datos['nombre'],
            rol=rol,
            estado='Activo',
            password=make_password(datos['password']),
        )
        usuario.save()

        if datos['rol'] == 'Actor':
            Actor.objects.create(usuario=usuario, estado='Activo')


def eliminar_cuentas(apps, schema_editor):
    Usuario = apps.get_model('simulactores', 'Usuario')
    correos = [c['email'] for c in CUENTAS_DESARROLLO]
    Usuario.objects.filter(email__in=correos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0002_seed_roles'),
    ]

    operations = [
        migrations.RunPython(crear_cuentas, eliminar_cuentas),
    ]
