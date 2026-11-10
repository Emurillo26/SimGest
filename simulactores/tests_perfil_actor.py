"""
Pruebas automáticas de HU-37 (perfil operativo del actor).

Cómo correrlas:  python manage.py test simulactores.tests_perfil_actor
"""
import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Asignacion, Bitacora, Habilidad, Rol, TarifaActor, Usuario
from .tests import BaseSprint2


class BasePerfilActor(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='perfil.actor@simgest.com', password='Actor123!',
            nombre='Actor Perfil', rol=rol_actor, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.hab1 = Habilidad.objects.create(nombre='Habilidad prueba A')
        self.hab2 = Habilidad.objects.create(nombre='Habilidad prueba B')
        self.url = reverse('simulactores:editar_perfil_actor', args=[self.actor.pk])
        self.url_lista = reverse('simulactores:actores_admin')

    def datos(self, **extra):
        datos = {
            'fecha_nacimiento': '1995-04-12',
            'genero': 'Femenino',
            'habilidades': [self.hab1.pk, self.hab2.pk],
            'tarifa': '15000.50',
            'tipo_tarifa': 'Por Hora',
            'estado': 'Activo',
        }
        datos.update(extra)
        return datos


class HU37ActualizacionExitosaTests(BasePerfilActor):

    def test_la_lista_muestra_a_los_actores_y_el_enlace_para_editar(self):
        r = self.client.get(self.url_lista)
        self.assertContains(r, 'Actor Perfil')
        self.assertContains(r, self.url)
        self.assertContains(r, 'Perfil incompleto')

    def test_actualizacion_exitosa_guarda_y_muestra_confirmacion(self):
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertRedirects(r, self.url_lista)
        self.assertContains(r, 'actualizado correctamente')
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.fecha_nacimiento, datetime.date(1995, 4, 12))
        self.assertEqual(self.actor.genero, 'Femenino')
        self.assertEqual(self.actor.tarifa, Decimal('15000.50'))
        self.assertEqual(self.actor.tipo_tarifa, 'Por Hora')
        self.assertEqual(set(self.actor.habilidades.all()), {self.hab1, self.hab2})

    def test_se_puede_pasar_a_inactivo_y_se_refleja_en_la_lista(self):
        r = self.client.post(self.url, self.datos(estado='Inactivo'), follow=True)
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.estado, 'Inactivo')
        self.assertContains(r, 'Inactivo')

    def test_pasar_a_inactivo_con_simulaciones_por_venir_avisa(self):
        solicitud = self.crear_solicitud(estado='Actor Asignado', fecha=timezone.localdate() + datetime.timedelta(days=5))
        Asignacion.objects.create(solicitud=solicitud, actor=self.actor, estado='Pendiente')
        r = self.client.post(self.url, self.datos(estado='Inactivo'), follow=True)
        self.assertContains(r, 'simulación(es) asignada(s) por venir')

    def test_queda_en_la_bitacora(self):
        self.client.post(self.url, self.datos())
        self.assertTrue(Bitacora.objects.filter(
            accion='Perfil operativo del actor actualizado', campo_modificado='tarifa',
            valor_nuevo='15000.50').exists())

    def test_sin_cambios_no_escribe_bitacora(self):
        self.client.post(self.url, self.datos())
        total = Bitacora.objects.filter(accion='Perfil operativo del actor actualizado').count()
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertContains(r, 'No hiciste ningún cambio')
        self.assertEqual(
            Bitacora.objects.filter(accion='Perfil operativo del actor actualizado').count(), total)

    def test_cambiar_la_tarifa_actualiza_el_historial(self):
        self.client.post(self.url, self.datos(tarifa='10000'))
        self.assertEqual(self.actor.historial_tarifas.count(), 1)
        TarifaActor.objects.filter(actor=self.actor).update(
            vigente_desde=timezone.localdate() - datetime.timedelta(days=30))
        self.client.post(self.url, self.datos(tarifa='12000'))
        historial = self.actor.historial_tarifas.order_by('vigente_desde')
        self.assertEqual(historial.count(), 2)
        self.assertEqual(historial[0].monto, Decimal('10000'))
        self.assertIsNotNone(historial[0].vigente_hasta)
        self.assertEqual(historial[1].monto, Decimal('12000'))
        self.assertIsNone(historial[1].vigente_hasta)

    def test_la_pagina_de_edicion_muestra_el_resumen_de_disponibilidad(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'Disponibilidad registrada')
        self.assertContains(r, 'todavía no tiene bloques')


class HU37DatosInvalidosTests(BasePerfilActor):

    def assert_no_guarda(self, r):
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Revisa los campos marcados en rojo')
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.tarifa)
        self.assertFalse(Bitacora.objects.filter(accion='Perfil operativo del actor actualizado').exists())

    def test_tarifa_negativa_se_rechaza(self):
        r = self.client.post(self.url, self.datos(tarifa='-500'))
        self.assertContains(r, 'no puede ser negativa')
        self.assertContains(r, 'is-invalid')
        self.assert_no_guarda(r)

    def test_tarifa_no_numerica_se_rechaza(self):
        r = self.client.post(self.url, self.datos(tarifa='mucho'))
        self.assertContains(r, 'debe ser un número')
        self.assert_no_guarda(r)

    def test_tarifa_cero_se_rechaza(self):
        r = self.client.post(self.url, self.datos(tarifa='0'))
        self.assertContains(r, 'mayor que cero')
        self.assert_no_guarda(r)

    def test_campos_obligatorios_vacios(self):
        r = self.client.post(self.url, self.datos(
            fecha_nacimiento='', genero='', tarifa='', tipo_tarifa=''))
        self.assertContains(r, 'Indica la fecha de nacimiento')
        self.assertContains(r, 'Selecciona el género')
        self.assertContains(r, 'Indica la tarifa')
        self.assertContains(r, 'por hora o por evento')
        self.assert_no_guarda(r)

    def test_fecha_de_nacimiento_futura(self):
        futura = (timezone.localdate() + datetime.timedelta(days=30)).isoformat()
        r = self.client.post(self.url, self.datos(fecha_nacimiento=futura))
        self.assertContains(r, 'no puede ser futura')
        self.assert_no_guarda(r)

    def test_menor_de_edad(self):
        reciente = (timezone.localdate() - datetime.timedelta(days=365 * 10)).isoformat()
        r = self.client.post(self.url, self.datos(fecha_nacimiento=reciente))
        self.assertContains(r, 'al menos 18 años')
        self.assert_no_guarda(r)

    def test_un_error_no_guarda_ninguno_de_los_otros_cambios(self):
        r = self.client.post(self.url, self.datos(tarifa='-1', genero='Otro', estado='Inactivo'))
        self.assertContains(r, 'no puede ser negativa')
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.genero)
        self.assertEqual(self.actor.estado, 'Activo')


class HU37PermisosTests(BasePerfilActor):

    def test_el_actor_no_puede_editar_perfiles(self):
        self.client.force_login(self.usuario_actor)
        r = self.client.post(self.url, self.datos())
        self.assertNotEqual(r.status_code, 200)
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.tarifa)

    def test_el_cliente_no_entra_a_la_lista(self):
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get(self.url_lista).status_code, 200)

    def test_actor_inexistente_da_404(self):
        r = self.client.get(reverse('simulactores:editar_perfil_actor', args=[999999]))
        self.assertEqual(r.status_code, 404)

    def test_el_menu_del_administrador_incluye_actores(self):
        r = self.client.get(reverse('simulactores:dashboard_administrador'))
        self.assertContains(r, self.url_lista)