"""
Pruebas de T02: modalidad y tarifas por modalidad.

Cómo correrlas:  python manage.py test simulactores.tests_tarifas
"""
from decimal import Decimal

from django.urls import reverse

from .models import Bitacora, Modalidad, Solicitud, TarifaModalidad
from .tests import BaseSprint2


class TarifasModalidadTests(BaseSprint2):

    def url(self):
        return reverse('simulactores:tarifas_modalidad')

    def test_tarifas_iniciales(self):
        self.assertEqual(TarifaModalidad.monto_de(Modalidad.VIRTUAL), Decimal('5500.00'))
        self.assertEqual(TarifaModalidad.monto_de(Modalidad.PRESENCIAL), Decimal('6500.00'))

    def test_admin_ve_la_pantalla(self):
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Tarifas por modalidad')

    def test_cliente_no_puede_entrar(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.post(self.url(), {'virtual': '1', 'presencial': '1'}).status_code, 403)

    def test_admin_cambia_tarifas_y_queda_en_bitacora(self):
        r = self.client.post(self.url(), {'virtual': '6000', 'presencial': '7000'})
        self.assertRedirects(r, self.url())
        self.assertEqual(TarifaModalidad.monto_de(Modalidad.VIRTUAL), Decimal('6000.00'))
        self.assertEqual(TarifaModalidad.monto_de(Modalidad.PRESENCIAL), Decimal('7000.00'))
        self.assertEqual(Bitacora.objects.filter(accion='Cambio de tarifa por modalidad').count(), 2)

    def test_tarifa_invalida_se_rechaza(self):
        r = self.client.post(self.url(), {'virtual': '0', 'presencial': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(TarifaModalidad.monto_de(Modalidad.VIRTUAL), Decimal('5500.00'))

    def test_solicitud_guarda_tarifa_vigente_y_no_cambia_despues(self):
        solicitud = self.crear_solicitud()
        solicitud.modalidad = Modalidad.VIRTUAL
        solicitud.tarifa_hora = None
        solicitud.save()
        self.assertEqual(solicitud.tarifa_hora, Decimal('5500.00'))
        self.client.post(self.url(), {'virtual': '9000', 'presencial': '9500'})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.tarifa_hora, Decimal('5500.00'))
        nueva = Solicitud.objects.get(pk=self.crear_solicitud(hora=14).pk)
        self.assertEqual(nueva.tarifa_hora, Decimal('9500.00'))