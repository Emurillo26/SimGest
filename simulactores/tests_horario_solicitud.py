"""
Pruebas de la regla de horario al crear una solicitud.

Regla: un cliente no puede tener dos solicitudes activas que se traslapen,
pero SÍ puede pedir un horario que otro cliente ya pidió (la capacidad la
define la disponibilidad de los actores al asignar).

Cómo correrlas:  python manage.py test simulactores.tests_horario_solicitud
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Rol, Solicitud, Usuario
from .tests import BaseSprint2


class HorarioSolicitudTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_cliente, _ = Rol.objects.get_or_create(nombre='Cliente')
        self.otro_cliente = Usuario.objects.create_user(
            email='cliente2.prueba@simgest.com', password='Cliente123!',
            nombre='Cliente Dos', rol=rol_cliente, estado='Activo')
        self.fecha = timezone.localdate() + datetime.timedelta(days=10)
        self.url = reverse('simulactores:crear_solicitud')
        self.client.force_login(self.cliente)

    def datos(self, inicio='09:00', fin='10:00', **extra):
        datos = {
            'tipo_simulacion': 'Otro', 'fecha_evento': self.fecha.isoformat(),
            'hora_inicio': inicio, 'hora_fin': fin, 'cantidad_interpretes': 1,
            'ubicacion': 'Sede central', 'observaciones': '',
        }
        datos.update(extra)
        return datos

    def existente(self, cliente, estado='Pendiente', hora=9):
        return Solicitud.objects.create(
            cliente=cliente, tipo_simulacion='Otro', fecha_evento=self.fecha,
            hora_inicio=datetime.time(hora), hora_fin=datetime.time(hora + 1),
            cantidad_interpretes=1, estado=estado)

    def test_otro_cliente_ya_pidio_ese_horario_si_se_puede_crear(self):
        self.existente(self.otro_cliente)
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertEqual(Solicitud.objects.filter(cliente=self.cliente).count(), 1)
        self.assertContains(r, 'creada correctamente')

    def test_mismo_cliente_mismo_horario_se_rechaza(self):
        self.existente(self.cliente)
        r = self.client.post(self.url, self.datos())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ya tienes otra solicitud en ese horario')
        self.assertEqual(Solicitud.objects.filter(cliente=self.cliente).count(), 1)

    def test_mismo_cliente_traslape_parcial_se_rechaza(self):
        self.existente(self.cliente)  # 09:00 - 10:00
        r = self.client.post(self.url, self.datos(inicio='09:30', fin='10:30'))
        self.assertContains(r, 'Ya tienes otra solicitud en ese horario')

    def test_mismo_cliente_horarios_seguidos_si_se_permite(self):
        self.existente(self.cliente)  # 09:00 - 10:00
        r = self.client.post(self.url, self.datos(inicio='10:00', fin='11:00'), follow=True)
        self.assertEqual(Solicitud.objects.filter(cliente=self.cliente).count(), 2)
        self.assertContains(r, 'creada correctamente')

    def test_una_solicitud_cancelada_no_bloquea(self):
        self.existente(self.cliente, estado='Cancelada')
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertContains(r, 'creada correctamente')

    def test_mismo_horario_otro_dia_si_se_permite(self):
        self.existente(self.cliente)
        otro_dia = (self.fecha + datetime.timedelta(days=1)).isoformat()
        r = self.client.post(self.url, self.datos(fecha_evento=otro_dia), follow=True)
        self.assertContains(r, 'creada correctamente')

    def test_hora_fin_anterior_al_inicio_sigue_rechazandose(self):
        r = self.client.post(self.url, self.datos(inicio='11:00', fin='10:00'))
        self.assertContains(r, 'posterior a la hora de inicio')