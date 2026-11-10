from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulactores', '0007_solicitud_ubicacion'),
    ]

    operations = [
        migrations.AddField(model_name='actor', name='estatura_cm',
                            field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='actor', name='peso_kg',
                            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
        migrations.AddField(model_name='actor', name='color_cabello',
                            field=models.CharField(blank=True, max_length=30, null=True)),
        migrations.AddField(model_name='actor', name='color_ojos',
                            field=models.CharField(blank=True, max_length=30, null=True)),
        migrations.AddField(model_name='actor', name='contextura',
                            field=models.CharField(blank=True, max_length=30, null=True)),
        migrations.AddField(model_name='actor', name='tono_piel',
                            field=models.CharField(blank=True, max_length=30, null=True)),
        migrations.AddField(model_name='actor', name='talla_ropa',
                            field=models.CharField(blank=True, max_length=10, null=True)),
        migrations.AddField(model_name='actor', name='talla_calzado',
                            field=models.DecimalField(blank=True, decimal_places=1, max_digits=3, null=True)),
        migrations.AddField(model_name='actor', name='otras_caracteristicas',
                            field=models.TextField(blank=True, default='', max_length=500)),
    ]