"""
Pruebas del rediseño del portal del cliente.

Cómo correrlas:  python manage.py test simulactores.tests_rediseno_cliente
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Asignacion, Notificacion, Rol, Solicitud, Usuario
from .templatetags.simulactores_extras import seguimiento, siguiente_paso
from .tests import BaseSprint2


class FiltrosSeguimientoTests(BaseSprint2):

    def test_siguiente_paso_sigue_el_flujo_real(self):
        self.assertEqual(siguiente_paso('Pendiente'), 'Revisión del equipo')
        self.assertEqual(siguiente_paso('Aprobada'), 'Asignación de actor')
        self.assertEqual(siguiente_paso('Confirmada'), 'Ejecución del evento')

    def test_sin_acciones_cuando_ya_termino(self):
        self.assertEqual(siguiente_paso('Completada'), 'Sin acciones')
        self.assertEqual(siguiente_paso('Cancelada'), 'Sin acciones')

    def test_seguimiento_marca_hecho_actual_y_pendiente(self):
        pasos = seguimiento('Aprobada')
        self.assertEqual([p['situacion'] for p in pasos],
                         ['hecho', 'hecho', 'actual', 'pendiente', 'pendiente', 'pendiente'])

    def test_seguimiento_completada_deja_todo_hecho(self):
        self.assertTrue(all(p['situacion'] == 'hecho' for p in seguimiento('Completada')))


class PortalClienteRediseñoTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente)

    def test_panel_destaca_nueva_solicitud(self):
        r = self.client.get(reverse('simulactores:dashboard_cliente'))
        self.assertContains(r, '¿Necesitas una simulación?')
        self.assertContains(r, reverse('simulactores:crear_solicitud'))

    def test_panel_muestra_actualizaciones_recientes(self):
        Notificacion.objects.create(usuario=self.cliente, mensaje='Tu solicitud cambió a En Revisión.')
        self.crear_solicitud()
        r = self.client.get(reverse('simulactores:dashboard_cliente'))
        self.assertContains(r, 'Tu solicitud cambió a En Revisión.')

    def test_listado_muestra_estado_y_siguiente_paso(self):
        self.crear_solicitud(estado='Pendiente')
        r = self.client.get(reverse('simulactores:mis_solicitudes'))
        self.assertContains(r, 'Siguiente paso')
        self.assertContains(r, 'Revisión del equipo')

    def test_formulario_tiene_los_cuatro_pasos_y_conserva_errores(self):
        r = self.client.get(reverse('simulactores:crear_solicitud'))
        for paso in ('Evento', 'Escenario', 'Contacto', 'Revisión'):
            self.assertContains(r, paso)
        r = self.client.post(reverse('simulactores:crear_solicitud'), {
            'tipo_simulacion': 'Otro', 'fecha_evento': '', 'hora_inicio': '09:00',
            'hora_fin': '10:00', 'cantidad_interpretes': 2, 'ubicacion': 'Hospital X'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="Hospital X"')
        self.assertContains(r, 'campo-error')

    def test_detalle_muestra_el_seguimiento(self):
        solicitud = self.crear_solicitud(estado='En Revisión')
        r = self.client.get(reverse('simulactores:detalle_solicitud', args=[solicitud.uuid]))
        self.assertContains(r, 'Resumen del evento')
        self.assertContains(r, 'Estado de la solicitud')
        self.assertContains(r, 'Solicitud recibida')
