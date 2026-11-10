from django.db import migrations

HABILIDADES = [
    'Actuación de paciente simulado',
    'Improvisación',
    'Teatro',
    'Voz y dicción',
    'Bilingüe (inglés)',
    'Lengua de señas',
    'Manejo de emociones intensas',
    'Maquillaje de caracterización',
    'Primeros auxilios',
]


def crear(apps, schema_editor):
    Habilidad = apps.get_model('simulactores', 'Habilidad')
    for nombre in HABILIDADES:
        Habilidad.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0008_actor_caracteristicas_fisicas'),
    ]

    operations = [
        migrations.RunPython(crear, migrations.RunPython.noop),
    ]