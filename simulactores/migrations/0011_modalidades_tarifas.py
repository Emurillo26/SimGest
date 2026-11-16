from decimal import Decimal

from django.db import migrations, models


def cargar_tarifas_iniciales(apps, schema_editor):
    TarifaModalidad = apps.get_model('simulactores', 'TarifaModalidad')
    TarifaModalidad.objects.get_or_create(modalidad='Virtual', defaults={'monto_hora': Decimal('5500.00')})
    TarifaModalidad.objects.get_or_create(modalidad='Presencial', defaults={'monto_hora': Decimal('6500.00')})


def fijar_tarifa_en_solicitudes_existentes(apps, schema_editor):
    Solicitud = apps.get_model('simulactores', 'Solicitud')
    TarifaModalidad = apps.get_model('simulactores', 'TarifaModalidad')
    for t in TarifaModalidad.objects.all():
        Solicitud.objects.filter(modalidad=t.modalidad, tarifa_hora__isnull=True).update(tarifa_hora=t.monto_hora)


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0010_usuario_foto'),
    ]

    operations = [
        migrations.CreateModel(
            name='TarifaModalidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modalidad', models.CharField(choices=[('Virtual', 'Virtual'), ('Presencial', 'Presencial')], max_length=20, unique=True)),
                ('monto_hora', models.DecimalField(decimal_places=2, max_digits=10)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'tarifa_modalidad', 'ordering': ['modalidad']},
        ),
        migrations.AddField(
            model_name='solicitud',
            name='modalidad',
            field=models.CharField(choices=[('Virtual', 'Virtual'), ('Presencial', 'Presencial')], default='Presencial', max_length=20),
        ),
        migrations.AddField(
            model_name='solicitud',
            name='tarifa_hora',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(cargar_tarifas_iniciales, migrations.RunPython.noop),
        migrations.RunPython(fijar_tarifa_en_solicitudes_existentes, migrations.RunPython.noop),
    ]