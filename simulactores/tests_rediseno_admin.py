"""
Pruebas del rediseño de la administración (panel, detalle, actores y escenarios).

Cómo correrlas:  python manage.py test simulactores.tests_rediseno_admin
"""
from django.urls import reverse

from .models import Actor, Rol, Usuario
from .tests import BaseSprint2


class PanelAdministradorTests(BaseSprint2):

    def test_panel_prioriza_las_tareas_pendientes(self):
        self.crear_solicitud(estado='Pendiente')
        self.crear_solicitud(estado='Aprobada')
        r = self.client.get(reverse('simulactores:dashboard_administrador'))
        self.assertContains(r, 'Próximas acciones')
        self.assertContains(r, 'Revisar 1 solicitud pendiente')
        self.assertContains(r, 'Asignar actores a 1 simulación')
        self.assertEqual(r.context['pendientes']['solicitudes'], 1)
        self.assertEqual(r.context['pendientes']['por_asignar'], 1)

    def test_panel_cuenta_actores_y_escenarios(self):
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        u = Usuario.objects.create_user(email='a@simgest.com', password='Actor123!',
                                        nombre='A', rol=rol, estado='Activo')
        Actor.objects.get_or_create(usuario=u)
        r = self.client.get(reverse('simulactores:dashboard_administrador'))
        self.assertEqual(r.context['totales']['actores'], Actor.objects.count())
        self.assertGreaterEqual(r.context['totales']['actores'], 1)
        self.assertEqual(r.context['totales']['escenarios'], 1)

    def test_panel_con_solicitudes_muestra_barra_por_estado(self):
        self.crear_solicitud(estado='Pendiente')
        r = self.client.get(reverse('simulactores:dashboard_administrador'))
        self.assertContains(r, 'Solicitudes por estado')
        self.assertTrue(r.context['por_estado'])


class PantallasAdministracionTests(BaseSprint2):

    def test_detalle_de_solicitud_muestra_resumen_y_actor(self):
        s = self.crear_solicitud(estado='Aprobada', escenario=self.escenario)
        r = self.client.get(reverse('simulactores:solicitud_admin_detalle', args=[s.uuid]))
        self.assertContains(r, 'Detalle de solicitud')
        self.assertContains(r, 'Información de la solicitud')
        self.assertContains(r, 'Actor asignado')

    def test_detalle_del_escenario_tiene_informacion_general_y_guion(self):
        r = self.client.get(reverse('simulactores:detalle_escenario', args=[self.escenario.pk]))
        self.assertContains(r, 'Información general')
        self.assertContains(r, 'Guion del escenario')

    def test_formulario_de_escenario_tiene_las_tres_secciones(self):
        r = self.client.get(reverse('simulactores:editar_escenario', args=[self.escenario.pk]))
        for texto in ('Información general', 'Descripción', 'Guion del actor'):
            self.assertContains(r, texto)

    def test_ficha_operativa_muestra_habilidades_como_opciones(self):
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        u = Usuario.objects.create_user(email='f@simgest.com', password='Actor123!',
                                        nombre='Ficha Actor', rol=rol, estado='Activo')
        actor, _ = Actor.objects.get_or_create(usuario=u)
        r = self.client.get(reverse('simulactores:editar_perfil_actor', args=[actor.pk]))
        self.assertContains(r, 'Datos operativos')
        self.assertContains(r, 'Habilidades del actor')
        self.assertContains(r, 'Características físicas')
