from django.db import migrations


# Áreas académicas reales que aparecen como hojas en los Excel de
# programación de Simulactores (Área de Salud, Educación, Administración).
# Sirven como categorías iniciales de la biblioteca de escenarios (HU-21).
CATEGORIAS_INICIALES = [
    'Medicina',
    'Enfermería',
    'Psicología',
    'Nutrición',
    'Comunicación en Salud',
    'Rehabilitación',
    'Ultrasonido',
    'Educación',
    'Administración',
]


def crear_categorias(apps, schema_editor):
    Categoria = apps.get_model('simulactores', 'Categoria')
    for nombre in CATEGORIAS_INICIALES:
        Categoria.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0004_alter_bitacora_options_remove_bitacora_hora_and_more'),
    ]

    operations = [
        # Al revertir no se borra nada: una categoría puede estar en uso.
        migrations.RunPython(crear_categorias, migrations.RunPython.noop),
    ]
