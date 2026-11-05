"""
Pruebas automáticas de HU-43 (registrar pagos a actores con trazabilidad).

Cómo correrlas:  python manage.py test simulactores.tests_pagos
"""
import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from . import pagos_service as servicio
from .models import Actor, Asignacion, Bitacora, Pago, Rol, Usuario
from .tests import BaseSprint2

FECHA = datetime.date(2026, 11, 5)   # fecha de las simulaciones ejecutadas (noviembre 2026)


class BasePagos(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.actor = self.crear_actor('actor.pago@simgest.com', 'Actor Pago',
                                      tarifa='5000', tipo='Por Hora')

    def crear_actor(self, email, nombre, tarifa='5000', tipo='Por Hora'):
        usuario = Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre,
            rol=self.rol_actor, estado='Activo')
        return Actor.objects.create(usuario=usuario, tarifa=Decimal(tarifa), tipo_tarifa=tipo)

    def ejecutada(self, actor=None, fecha=FECHA, hora=9, estado='Ejecutada'):
        """Simulación de 1 hora; con tarifa de ₡5000/hora vale ₡5000."""
        solicitud = self.crear_solicitud(estado='Completada', fecha=fecha, hora=hora)
        return Asignacion.objects.create(
            solicitud=solicitud, actor=actor or self.actor, estado=estado,
            tarifa_aplicada=(actor or self.actor).tarifa)

    def datos(self, **extra):
        datos = {
            'actor': self.actor.pk, 'periodo_mes': 11, 'periodo_anio': 2026,
            'monto': '5000.00', 'fecha_pago': timezone.localdate().isoformat(),
            'metodo_pago': 'Transferencia', 'referencia': 'TRF-0001',
        }
        datos.update(extra)
        return datos

    url = reverse('simulactores:registrar_pago')

    def pagar(self, **extra):
        return self.client.post(self.url, self.datos(**extra))

    def pago_registrado(self):
        self.ejecutada()
        self.pagar()
        return Pago.objects.get(actor=self.actor)


class HU43CalculoPendienteTests(BasePagos):

    def test_por_hora_usa_las_horas_agendadas_si_no_hay_horas_reales(self):
        self.ejecutada(hora=9)
        total, filas = servicio.monto_pendiente(self.actor, 11, 2026)
        self.assertEqual(total, Decimal('5000.00'))
        self.assertEqual(len(filas), 1)

    def test_por_hora_usa_las_horas_reales_cuando_existen(self):
        asignacion = self.ejecutada(hora=9)
        asignacion.hora_inicio_real = datetime.time(9, 0)
        asignacion.hora_fin_real = datetime.time(11, 30)
        asignacion.save()
        total, _ = servicio.monto_pendiente(self.actor, 11, 2026)
        self.assertEqual(total, Decimal('12500.00'))

    def test_por_evento_cobra_la_tarifa_completa(self):
        actor = self.crear_actor('evento@simgest.com', 'Actor Evento', tarifa='30000', tipo='Por Evento')
        self.ejecutada(actor=actor)
        total, _ = servicio.monto_pendiente(actor, 11, 2026)
        self.assertEqual(total, Decimal('30000.00'))

    def test_solo_cuentan_las_ejecutadas_del_periodo(self):
        self.ejecutada(hora=9)
        self.ejecutada(hora=11, estado='Confirmada')
        self.ejecutada(hora=13, fecha=datetime.date(2026, 10, 20))
        total, filas = servicio.monto_pendiente(self.actor, 11, 2026)
        self.assertEqual((total, len(filas)), (Decimal('5000.00'), 1))

    def test_consultar_pendiente_rellena_el_monto_sin_guardar(self):
        self.ejecutada()
        datos = self.datos(accion='calcular')
        r = self.client.post(self.url, datos)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'tiene ₡5000.00 pendientes')
        self.assertContains(r, 'value="5000.00"')
        self.assertFalse(Pago.objects.exists())

    def test_consultar_pendiente_sin_simulaciones_avisa(self):
        r = self.client.post(self.url, self.datos(accion='calcular'))
        self.assertContains(r, 'no tiene monto pendiente')


class HU43RegistroExitosoTests(BasePagos):

    def test_registro_exitoso_crea_el_pago_con_todos_los_datos(self):
        asignacion = self.ejecutada()
        r = self.pagar()
        self.assertRedirects(r, reverse('simulactores:pagos_admin'))
        pago = Pago.objects.get(actor=self.actor)
        self.assertEqual(pago.estado, 'Pagado')
        self.assertEqual((pago.periodo_mes, pago.periodo_anio), (11, 2026))
        self.assertEqual(pago.monto_total, Decimal('5000.00'))
        self.assertEqual(pago.metodo_pago, 'Transferencia')
        self.assertEqual(pago.referencia, 'TRF-0001')
        self.assertEqual(list(pago.asignaciones.all()), [asignacion])

    def test_registro_deja_trazabilidad_en_la_bitacora(self):
        self.ejecutada()
        self.pagar()
        filas = Bitacora.objects.filter(accion='Pago registrado')
        self.assertEqual(filas.count(), 7)
        self.assertTrue(all(f.realizado_por == self.admin for f in filas))
        self.assertTrue(all(f.usuario == self.actor.usuario for f in filas))
        referencia = filas.get(campo_modificado='referencia')
        self.assertEqual(referencia.valor_nuevo, 'TRF-0001')

    def test_el_pago_aparece_en_el_listado(self):
        self.ejecutada()
        self.pagar()
        r = self.client.get(reverse('simulactores:pagos_admin'))
        self.assertContains(r, 'Actor Pago')
        self.assertContains(r, 'TRF-0001')
        self.assertContains(r, '11/2026')

    def test_mensaje_de_exito(self):
        self.ejecutada()
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertContains(r, 'Pago registrado')

    def test_un_pago_anulado_se_puede_registrar_de_nuevo_en_la_misma_fila(self):
        pago = self.pago_registrado()
        servicio.anular_pago(pago, motivo='Error de transferencia', confirmado=True)
        self.pagar(referencia='TRF-0002')
        self.assertEqual(Pago.objects.filter(actor=self.actor).count(), 1)
        pago.refresh_from_db()
        self.assertEqual((pago.estado, pago.referencia), ('Pagado', 'TRF-0002'))

    def test_un_pago_pendiente_existente_se_completa(self):
        self.ejecutada()
        Pago.objects.create(actor=self.actor, periodo_mes=11, periodo_anio=2026,
                            monto_total=Decimal('5000'), estado='Pendiente')
        self.pagar()
        pago = Pago.objects.get(actor=self.actor)
        self.assertEqual((pago.estado, pago.referencia), ('Pagado', 'TRF-0001'))


class HU43BloqueosTests(BasePagos):

    def test_periodo_ya_pagado_se_bloquea(self):
        self.pago_registrado()
        r = self.pagar(referencia='TRF-9999')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ya está pagado')
        self.assertEqual(Pago.objects.filter(actor=self.actor).count(), 1)
        self.assertEqual(Pago.objects.get(actor=self.actor).referencia, 'TRF-0001')

    def test_falta_la_referencia(self):
        self.ejecutada()
        for valor in ['', '   ']:
            r = self.pagar(referencia=valor)
            self.assertContains(r, 'Indica la referencia del pago')
        self.assertFalse(Pago.objects.exists())

    def test_falta_la_fecha(self):
        self.ejecutada()
        r = self.pagar(fecha_pago='')
        self.assertContains(r, 'Indica la fecha del pago')
        self.assertFalse(Pago.objects.exists())

    def test_faltan_metodo_y_monto(self):
        self.ejecutada()
        r = self.pagar(metodo_pago='', monto='')
        self.assertContains(r, 'Selecciona el método de pago')
        self.assertContains(r, 'Indica el monto')
        self.assertFalse(Pago.objects.exists())

    def test_monto_cero_o_negativo_se_rechaza(self):
        self.ejecutada()
        for monto in ['0', '-100']:
            self.pagar(monto=monto)
        self.assertFalse(Pago.objects.exists())

    def test_fecha_futura_se_rechaza(self):
        self.ejecutada()
        futura = (timezone.localdate() + datetime.timedelta(days=3)).isoformat()
        r = self.pagar(fecha_pago=futura)
        self.assertContains(r, 'no puede ser futura')
        self.assertFalse(Pago.objects.exists())

    def test_actor_sin_monto_pendiente_no_se_puede_pagar(self):
        r = self.pagar()
        self.assertContains(r, 'no tiene monto pendiente')
        self.assertFalse(Pago.objects.exists())

    def test_mes_invalido_se_rechaza(self):
        self.ejecutada()
        self.pagar(periodo_mes=13)
        self.assertFalse(Pago.objects.exists())


class HU43ModificarYAnularTests(BasePagos):

    def url_editar(self, pago):
        return reverse('simulactores:editar_pago', args=[pago.pk])

    def url_anular(self, pago):
        return reverse('simulactores:anular_pago', args=[pago.pk])

    def datos_edicion(self, **extra):
        datos = {'monto': '6000.00', 'fecha_pago': timezone.localdate().isoformat(),
                 'metodo_pago': 'Transferencia', 'referencia': 'TRF-0001'}
        datos.update(extra)
        return datos

    def test_modificar_un_pago_pagado_sin_confirmar_se_bloquea(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_editar(pago), self.datos_edicion())
        self.assertContains(r, 'Debes confirmar')
        pago.refresh_from_db()
        self.assertEqual(pago.monto_total, Decimal('5000.00'))

    def test_el_formulario_de_un_pago_pagado_pide_confirmacion(self):
        pago = self.pago_registrado()
        r = self.client.get(self.url_editar(pago))
        self.assertContains(r, 'ya está confirmado como')
        self.assertContains(r, 'name="confirmo"')

    def test_modificar_confirmando_guarda_y_deja_bitacora(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_editar(pago), self.datos_edicion(confirmo='on', referencia='TRF-0002'))
        self.assertRedirects(r, reverse('simulactores:pagos_admin'))
        pago.refresh_from_db()
        self.assertEqual((pago.monto_total, pago.referencia), (Decimal('6000.00'), 'TRF-0002'))
        campos = set(Bitacora.objects.filter(accion='Pago modificado')
                     .values_list('campo_modificado', flat=True))
        self.assertEqual(campos, {'monto_total', 'referencia'})

    def test_modificar_sin_cambios_avisa(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_editar(pago), self.datos_edicion(confirmo='on', monto='5000.00'))
        self.assertContains(r, 'ningún cambio')

    def test_anular_sin_confirmar_se_bloquea(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_anular(pago), {'motivo': 'Duplicado'})
        self.assertContains(r, 'Debes confirmar')
        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'Pagado')

    def test_la_pantalla_de_anular_pide_confirmacion(self):
        pago = self.pago_registrado()
        r = self.client.get(self.url_anular(pago))
        self.assertContains(r, 'ya está confirmado como')
        self.assertContains(r, 'Sí, anular pago')

    def test_anular_confirmando_cambia_el_estado_y_deja_bitacora(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_anular(pago), {'motivo': 'Pago duplicado', 'confirmar': '1'})
        self.assertRedirects(r, reverse('simulactores:pagos_admin'))
        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'Anulado')
        motivo = Bitacora.objects.get(accion='Pago anulado', campo_modificado='motivo_anulacion')
        self.assertEqual(motivo.valor_nuevo, 'Pago duplicado')

    def test_anular_exige_motivo(self):
        pago = self.pago_registrado()
        r = self.client.post(self.url_anular(pago), {'motivo': '  ', 'confirmar': '1'})
        self.assertContains(r, 'Indica el motivo')
        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'Pagado')

    def test_un_pago_anulado_no_se_modifica_ni_se_vuelve_a_anular(self):
        pago = self.pago_registrado()
        servicio.anular_pago(pago, motivo='Error', confirmado=True)
        r = self.client.post(self.url_editar(pago), self.datos_edicion(confirmo='on'), follow=True)
        self.assertContains(r, 'anulado no se puede modificar')
        r = self.client.post(self.url_anular(pago), {'motivo': 'x', 'confirmar': '1'})
        self.assertContains(r, 'ya está anulado')

    def test_pago_pendiente_se_anula_sin_confirmacion_especial(self):
        pago = Pago.objects.create(actor=self.actor, periodo_mes=11, periodo_anio=2026,
                                   monto_total=Decimal('5000'), estado='Pendiente')
        self.client.post(self.url_anular(pago), {'motivo': 'Creado por error'})
        pago.refresh_from_db()
        self.assertEqual(pago.estado, 'Anulado')

    def test_el_listado_ofrece_modificar_y_anular_solo_si_no_esta_anulado(self):
        pago = self.pago_registrado()
        r = self.client.get(reverse('simulactores:pagos_admin'))
        self.assertContains(r, self.url_anular(pago))
        servicio.anular_pago(pago, motivo='Error', confirmado=True)
        r = self.client.get(reverse('simulactores:pagos_admin'))
        self.assertNotContains(r, self.url_anular(pago))


class HU43ListadoYAccesoTests(BasePagos):

    def test_filtros_del_listado(self):
        otro = self.crear_actor('otro.pago@simgest.com', 'Otro Actor')
        self.ejecutada()
        self.ejecutada(actor=otro, hora=11)
        self.pagar()
        self.pagar(actor=otro.pk, referencia='TRF-0002')
        url = reverse('simulactores:pagos_admin')
        r = self.client.get(url, {'actor': otro.pk})
        self.assertContains(r, 'TRF-0002')
        self.assertNotContains(r, 'TRF-0001')
        r = self.client.get(url, {'mes': 10})
        self.assertNotContains(r, 'TRF-0001')

    def test_solo_el_administrador_entra(self):
        urls = [reverse('simulactores:pagos_admin'), self.url]
        for usuario in (self.cliente, self.actor.usuario):
            self.client.force_login(usuario)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        r = self.client.get(urls[0])
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('simulactores:login'), r.url)

    def test_un_actor_no_puede_registrar_pagos_por_post(self):
        self.ejecutada()
        self.client.force_login(self.actor.usuario)
        self.assertEqual(self.pagar().status_code, 403)
        self.assertFalse(Pago.objects.exists())

    def test_el_menu_del_administrador_incluye_pagos(self):
        r = self.client.get(reverse('simulactores:pagos_admin'))
        self.assertContains(r, 'Pagos a actores')
