import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _asignar_uuids_unicos(apps, schema_editor):
    Usuario = apps.get_model('simulactores', 'Usuario')
    Solicitud = apps.get_model('simulactores', 'Solicitud')

    for usuario in Usuario.objects.all():
        usuario.uuid = uuid.uuid4()
        usuario.save(update_fields=['uuid'])

    for solicitud in Solicitud.objects.all():
        solicitud.uuid = uuid.uuid4()
        solicitud.save(update_fields=['uuid'])


def _reversa_noop(apps, schema_editor):

    pass


class Migration(migrations.Migration):

    dependencies = [
        ("simulactores", "0003_cuentas_desarrollo"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="bitacora",
            options={"ordering": ["-fecha"]},
        ),
        migrations.RemoveField(
            model_name="bitacora",
            name="hora",
        ),
        migrations.AddField(
            model_name="bitacora",
            name="campo_modificado",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="bitacora",
            name="realizado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bitacoras_realizadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="bitacora",
            name="valor_anterior",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bitacora",
            name="valor_nuevo",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="fecha_limite_aprobacion",
            field=models.DateTimeField(blank=True, null=True),
        ),


        migrations.AddField(
            model_name="solicitud",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Identificador público usado en las URLs, para no exponer el id secuencial ni permitir enumerar solicitudes de otros clientes.",
                null=True,
            ),
        ),

        migrations.AddField(
            model_name="usuario",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Identificador único público, para no exponer el id interno secuencial.",
                null=True,
            ),
        ),


        migrations.RunPython(_asignar_uuids_unicos, _reversa_noop),


        migrations.AlterField(
            model_name="solicitud",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Identificador público usado en las URLs, para no exponer el id secuencial ni permitir enumerar solicitudes de otros clientes.",
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="usuario",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Identificador único público, para no exponer el id interno secuencial.",
                unique=True,
            ),
        ),

        migrations.AlterField(
            model_name="bitacora",
            name="accion",
            field=models.CharField(
                help_text="Categoría del cambio, p. ej. 'Edición por administrador'.",
                max_length=150,
            ),
        ),
        migrations.AlterField(
            model_name="bitacora",
            name="fecha",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="bitacora",
            name="resultado",
            field=models.CharField(
                blank=True, default="Exitoso", max_length=50, null=True
            ),
        ),
    ]
