from django.apps import AppConfig


class SimulactoresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'simulactores'

    def ready(self):
        from . import signals  # noqa: F401  (activa los avisos automáticos, HU-30)
