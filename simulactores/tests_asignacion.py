"""
Pruebas automáticas de HU-42 (validar disponibilidad), HU-44 (asignar actor)
y HU-45 (reasignar actor).

Cómo correrlas:  python manage.py test simulactores
"""
import datetime

from django.urls import reverse

from . import asignacion_service as servicio
from .models import Actor, Asignacion, Bitacora, Disponibilidad, Rol, Usuario
from .tests import BaseSprint2

FECHA = datetime.date(2026, 11, 5)


class BaseAsignacion(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.solicitud = self.crear_solicitud(estado='Aprobada', escenario=self.escenario)
        self.actor = self.crear_actor('uno@simgest.com', 'Actor Uno')

    def crear_actor(self, email, nombre, disponible=True, estado='Activo'):
        usuario = Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre, rol=self.rol_actor, estado='Activo')
        actor = Actor.objects.create(usuario=usuario, estado=estado)
        if disponible:
            self.dar_disponibilidad(actor)
        return actor

    def dar_disponibilidad(self, actor, fecha=FECHA, inicio=8, fin=18, tipo='Disponible'):
        return Disponibilidad.objects.create(
            actor=actor, fecha=fecha, hora_inicio=datetime.time(inicio),
            hora_fin=datetime.time(fin), tipo_bloque=tipo)

    def url_asignar(self, solicitud=None):
        return reverse('simulactores:asignar_actor', args=[(solicitud or self.solicitud).uuid])

    def url_reasignar(self, solicitud=None):
        return reverse('simulactores:reasignar_actor', args=[(solicitud or self.solicitud).uuid])


class HU42ValidarDisponibilidadTests(BaseAsignacion):

    def test_actor_con_disponibilidad_registrada_es_valido(self):
        self.assertTrue(servicio.validar_disponibilidad(self.actor, self.solicitud).disponible)

    def test_actor_sin_disponibilidad_registrada_no_es_valido(self):
        otro = self.crear_actor('dos@simgest.com', 'Actor Dos', disponible=False)
        veredicto = servicio.validar_disponibilidad(otro, self.solicitud)
        self.assertFalse(veredicto.disponible)
        self.assertIn('no tiene disponibilidad', veredicto.motivo)

    def test_disponibilidad_de_otra_fecha_no_sirve(self):
        otro = self.crear_actor('dos@simgest.com', 'Actor Dos', disponible=False)
        self.dar_disponibilidad(otro, fecha=datetime.date(2026, 11, 6))
        self.assertFalse(servicio.validar_disponibilidad(otro, self.solicitud).disponible)

    def test_bloque_que_no_cubre_todo_el_horario_no_sirve(self):
        otro = self.crear_actor('dos@simgest.com', 'Actor Dos', disponible=False)
        self.dar_disponibilidad(otro, inicio=9, fin=9)  # no cubre 9:00-10:00
        self.assertFalse(servicio.validar_disponibilidad(otro, self.solicitud).disponible)

    def test_fecha_bloqueada_no_es_valida(self):
        self.dar_disponibilidad(self.actor, inicio=9, fin=11, tipo='Bloqueado')
        veredicto = servicio.validar_disponibilidad(self.actor, self.solicitud)
        self.assertFalse(veredicto.disponible)
        self.assertIn('bloqueó', veredicto.motivo)

    def test_actor_inactivo_no_es_valido(self):
        inactivo = self.crear_actor('dos@simgest.com', 'Actor Dos', estado='Inactivo')
        self.assertFalse(servicio.validar_disponibilidad(inactivo, self.solicitud).disponible)

    def test_conflicto_de_agenda_con_otra_simulacion(self):
        otra = self.crear_solicitud(estado='Actor Asignado', hora=9, escenario=self.escenario)
        Asignacion.objects.create(solicitud=otra, actor=self.actor, estado='Confirmada')
        veredicto = servicio.validar_disponibilidad(self.actor, self.solicitud)
        self.assertFalse(veredicto.disponible)
        self.assertIn('Conflicto de agenda', veredicto.motivo)
        self.assertIn(otra.numero_solicitud, veredicto.motivo)

    def test_simulaciones_seguidas_no_chocan(self):
        otra = self.crear_solicitud(estado='Actor Asignado', hora=10, escenario=self.escenario)  # 10-11
        Asignacion.objects.create(solicitud=otra, actor=self.actor, estado='Confirmada')
        self.assertTrue(servicio.validar_disponibilidad(self.actor, self.solicitud).disponible)

    def test_asignacion_cancelada_o_solicitud_cancelada_no_choca(self):
        otra = self.crear_solicitud(estado='Cancelada', hora=9, escenario=self.escenario)
        Asignacion.objects.create(solicitud=otra, actor=self.actor, estado='Pendiente')
        otra2 = self.crear_solicitud(estado='Actor Asignado', hora=9, escenario=self.escenario)
        Asignacion.objects.create(solicitud=otra2, actor=self.actor, estado='Cancelada')
        self.assertTrue(servicio.validar_disponibilidad(self.actor, self.solicitud).disponible)


class HU44AsignarActorTests(BaseAsignacion):

    def test_pantalla_lista_a_los_actores_disponibles(self):
        r = self.client.get(self.url_asignar())
        self.assertContains(r, 'Actor Uno')
        self.assertContains(r, 'Disponible')

    def test_asignacion_exitosa(self):
        r = self.client.post(self.url_asignar(), {'actor': self.actor.pk}, follow=True)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Actor Asignado')
        asignacion = Asignacion.objects.get(solicitud=self.solicitud)
        self.assertEqual(asignacion.actor, self.actor)
        self.assertEqual(asignacion.estado, 'Pendiente')
        self.assertContains(r, 'Actor asignado correctamente')

    def test_notifica_al_actor_y_al_cliente(self):
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        self.assertTrue(self.actor.usuario.notificaciones.filter(mensaje__contains='nueva simulación').exists())
        self.assertTrue(self.cliente.notificaciones.filter(mensaje__contains='asignamos un actor').exists())

    def test_queda_en_bitacora(self):
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        self.assertTrue(Bitacora.objects.filter(
            accion='Actor asignado por administrador', valor_nuevo='Actor Uno').exists())
        self.assertTrue(Bitacora.objects.filter(
            accion='Actor asignado por administrador', campo_modificado='estado',
            valor_nuevo='Actor Asignado').exists())

    def test_conflicto_de_agenda_bloquea_la_asignacion(self):
        otra = self.crear_solicitud(estado='Actor Asignado', hora=9, escenario=self.escenario)
        Asignacion.objects.create(solicitud=otra, actor=self.actor, estado='Confirmada')
        r = self.client.post(self.url_asignar(), {'actor': self.actor.pk}, follow=True)
        self.assertContains(r, 'Conflicto de agenda')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Aprobada')
        self.assertFalse(self.solicitud.asignaciones.exists())

    def test_actor_sin_disponibilidad_no_se_puede_asignar(self):
        otro = self.crear_actor('dos@simgest.com', 'Actor Dos', disponible=False)
        r = self.client.post(self.url_asignar(), {'actor': otro.pk}, follow=True)
        self.assertContains(r, 'no tiene disponibilidad')
        self.assertFalse(self.solicitud.asignaciones.exists())

    def test_primero_que_guarda_gana(self):
        otra = self.crear_solicitud(estado='Aprobada', hora=9, escenario=self.escenario)
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        r = self.client.post(self.url_asignar(otra), {'actor': self.actor.pk}, follow=True)
        self.assertContains(r, 'Conflicto de agenda')
        self.assertFalse(otra.asignaciones.exists())

    def test_sin_elegir_actor_muestra_error(self):
        r = self.client.post(self.url_asignar(), {}, follow=True)
        self.assertContains(r, 'Selecciona un actor')
        self.assertFalse(self.solicitud.asignaciones.exists())

    def test_solo_se_asigna_en_estado_aprobada(self):
        pendiente = self.crear_solicitud(estado='Pendiente')
        r = self.client.post(self.url_asignar(pendiente), {'actor': self.actor.pk}, follow=True)
        self.assertContains(r, 'no admite asignar')
        self.assertFalse(pendiente.asignaciones.exists())

    def test_con_dos_interpretes_el_estado_cambia_al_completar_cupos(self):
        self.solicitud.cantidad_interpretes = 2
        self.solicitud.save()
        segundo = self.crear_actor('dos@simgest.com', 'Actor Dos')
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Aprobada')
        self.client.post(self.url_asignar(), {'actor': segundo.pk})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Actor Asignado')

    def test_no_se_puede_asignar_dos_veces_al_mismo_actor(self):
        self.solicitud.cantidad_interpretes = 2
        self.solicitud.save()
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        r = self.client.post(self.url_asignar(), {'actor': self.actor.pk}, follow=True)
        self.assertContains(r, 'ya está asignado')
        self.assertEqual(self.solicitud.asignaciones.count(), 1)

    def test_sin_actores_disponibles_muestra_mensaje(self):
        self.actor.disponibilidades.all().delete()
        r = self.client.get(self.url_asignar())
        self.assertContains(r, 'No hay actores disponibles')
        self.assertContains(r, 'fechas alternativas')

    def test_el_detalle_muestra_el_boton_asignar(self):
        detalle = reverse('simulactores:solicitud_admin_detalle', args=[self.solicitud.uuid])
        self.assertContains(self.client.get(detalle), self.url_asignar())

    def test_un_actor_no_puede_entrar(self):
        self.client.force_login(self.actor.usuario)
        r = self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        self.assertNotEqual(r.status_code, 200)
        self.assertFalse(self.solicitud.asignaciones.exists())


class HU45ReasignarActorTests(BaseAsignacion):

    def setUp(self):
        super().setUp()
        self.reemplazo = self.crear_actor('dos@simgest.com', 'Actor Dos')
        self.client.post(self.url_asignar(), {'actor': self.actor.pk})
        self.anterior = Asignacion.objects.get(solicitud=self.solicitud, actor=self.actor)

    def reasignar(self, actor=None, asignacion=None, **extra):
        datos = {'asignacion': (asignacion or self.anterior).pk, 'actor': (actor or self.reemplazo).pk}
        datos.update(extra)
        return self.client.post(self.url_reasignar(), datos, follow=True)

    def test_reasignacion_exitosa(self):
        r = self.reasignar()
        self.assertContains(r, 'Actor reasignado correctamente')
        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.estado, 'Cancelada')
        nueva = Asignacion.objects.get(solicitud=self.solicitud, actor=self.reemplazo)
        self.assertEqual(nueva.estado, 'Pendiente')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Actor Asignado')

    def test_el_actor_anterior_queda_libre(self):
        self.reasignar()
        self.assertTrue(servicio.validar_disponibilidad(self.actor, self.solicitud).disponible)

    def test_avisa_al_cliente_y_a_ambos_actores(self):
        self.reasignar()
        self.assertTrue(self.cliente.notificaciones.filter(mensaje__contains='Cambiamos el actor').exists())
        self.assertTrue(self.actor.usuario.notificaciones.filter(mensaje__contains='fue cancelada').exists())
        self.assertTrue(self.reemplazo.usuario.notificaciones.filter(mensaje__contains='nueva simulación').exists())

    def test_queda_en_bitacora(self):
        self.reasignar()
        self.assertTrue(Bitacora.objects.filter(
            accion='Actor reasignado por administrador',
            valor_anterior='Actor Uno', valor_nuevo='Actor Dos').exists())

    def test_reasignar_una_solicitud_confirmada_vuelve_a_actor_asignado(self):
        self.anterior.estado = 'Confirmada'
        self.anterior.save()
        self.solicitud.estado = 'Confirmada'
        self.solicitud.save()
        self.reasignar()
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'Actor Asignado')

    def test_reemplazo_con_conflicto_de_agenda_se_bloquea(self):
        otra = self.crear_solicitud(estado='Actor Asignado', hora=9, escenario=self.escenario)
        Asignacion.objects.create(solicitud=otra, actor=self.reemplazo, estado='Confirmada')
        r = self.reasignar()
        self.assertContains(r, 'Conflicto de agenda')
        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.estado, 'Pendiente')

    def test_no_se_puede_elegir_al_mismo_actor(self):
        r = self.reasignar(actor=self.actor)
        self.assertContains(r, 'actor distinto')
        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.estado, 'Pendiente')

    def test_sin_elegir_a_quien_reemplazar(self):
        r = self.client.post(self.url_reasignar(), {'actor': self.reemplazo.pk}, follow=True)
        self.assertContains(r, 'Selecciona el actor que quieres reemplazar')

    def test_sin_actores_disponibles_para_reemplazo(self):
        self.reemplazo.disponibilidades.all().delete()
        r = self.client.get(self.url_reasignar())
        self.assertContains(r, 'No hay actores disponibles')
        self.assertContains(r, 'fechas alternativas')

    def test_el_actor_que_sale_no_se_ofrece_como_reemplazo(self):
        r = self.client.get(self.url_reasignar())
        self.assertContains(r, 'Actor Dos')
        self.assertNotContains(r, 'aria-label="Elegir a Actor Uno"')

    def test_el_actor_que_rechazo_no_se_ofrece_de_nuevo(self):
        self.anterior.estado = 'Rechazada'
        self.anterior.save()
        filas = servicio.candidatos(self.solicitud)
        actores = [f['actor'] for f in filas]
        self.assertIn(self.reemplazo, actores)
        self.assertNotIn(self.actor, actores)

    def test_tras_un_rechazo_se_puede_asignar_otro_actor(self):
        self.anterior.estado = 'Rechazada'
        self.anterior.save()
        r = self.client.post(self.url_asignar(), {'actor': self.reemplazo.pk}, follow=True)
        self.assertContains(r, 'Actor asignado correctamente')

    def test_no_se_reasigna_si_no_hay_actor_vigente(self):
        self.anterior.estado = 'Rechazada'
        self.anterior.save()
        r = self.client.get(self.url_reasignar(), follow=True)
        self.assertContains(r, 'no tiene un actor asignado')
