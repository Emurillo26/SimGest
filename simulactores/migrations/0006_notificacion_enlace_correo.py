from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0005_categorias_iniciales'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificacion',
            name='enlace',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='notificacion',
            name='correo_enviado',
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='notificacion',
            name='error_correo',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
