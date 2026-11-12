"""
Pruebas del rediseño del portal del actor.

Cómo correrlas:  python manage.py test simulactores.tests_rediseno_actor
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Asignacion, Notificacion, Rol, Solicitud, Usuario
from .templatetags.simulactores_extras import seguimiento, siguiente_paso
from .tests import BaseSprint2


class PortalActorRediseñoTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='actor.rediseno@simgest.com', password='Actor123!',
            nombre='Actor Rediseño', rol=rol, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.client.force_login(self.usuario_actor)
        self.hoy = timezone.localdate()

    def _asignar(self, dias, estado='Pendiente', estado_solicitud='Actor Asignado'):
        s = self.crear_solicitud(estado=estado_solicitud, fecha=self.hoy + datetime.timedelta(days=dias),
                                 hora=9, escenario=self.escenario)
        return s, Asignacion.objects.create(solicitud=s, actor=self.actor, estado=estado)

    def test_panel_cuenta_realizadas_y_muestra_proxima(self):
        self._asignar(-3, estado='Ejecutada', estado_solicitud='Completada')
        proxima, _ = self._asignar(2)
        r = self.client.get(reverse('simulactores:dashboard_actor'))
        self.assertEqual(r.context['realizadas'], 1)
        self.assertEqual(r.context['proxima'].solicitud, proxima)
        self.assertContains(r, 'Ver calendario')

    def test_panel_sin_simulaciones_ofrece_ver_calendario(self):
        r = self.client.get(reverse('simulactores:dashboard_actor'))
        self.assertContains(r, 'No tienes simulaciones programadas')
        self.assertContains(r, reverse('simulactores:calendario_actor'))

    def test_detalle_distingue_estado_del_evento_y_de_la_asignacion(self):
        s, _ = self._asignar(3)
        r = self.client.get(reverse('simulactores:detalle_simulacion_actor', args=[s.uuid]))
        self.assertContains(r, 'Estado del evento')
        self.assertContains(r, 'Estado de tu asignación')
        self.assertContains(r, 'Confirmar participación')

    def test_perfil_agrupa_secciones_y_muestra_errores_de_contrasena(self):
        r = self.client.get(reverse('simulactores:perfil'))
        for texto in ('Cuenta', 'Perfil actoral', 'Habilidades', 'Características físicas', 'Seguridad'):
            self.assertContains(r, texto)
        r = self.client.post(reverse('simulactores:perfil'), {
            'nombre': 'Actor Rediseño', 'telefono': '', 'password': 'corta', 'password2': 'otra'})
        self.assertContains(r, '<details class="desplegable" open>', html=False)
