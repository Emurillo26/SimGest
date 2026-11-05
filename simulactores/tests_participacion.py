"""
Pruebas automáticas de HU-29 (confirmar o rechazar participación en una simulación).

Cómo correrlas:  python manage.py test simulactores.tests_participacion
"""
from django.core import mail
from django.urls import reverse

from .models import Actor, Asignacion, Bitacora, Notificacion, Rol, Usuario
from .tests import BaseSprint2


class BaseParticipacion(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.actor = self.crear_actor('actor.part@simgest.com', 'Actor Part')
        self.solicitud = self.crear_solicitud(
            estado='Actor Asignado', escenario=self.escenario)
        self.asignacion = Asignacion.objects.create(
            solicitud=self.solicitud, actor=self.actor, estado='Pendiente')
        self.client.force_login(self.actor.usuario)
        # Las notificaciones del setup (asignación) no cuentan en estas pruebas.
        Notificacion.objects.all().delete()
        mail.outbox.clear()

    def crear_actor(self, email, nombre):
        usuario = Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre,
            rol=self.rol_actor, estado='Activo')
        return Actor.objects.create(usuario=usuario)

    def url(self, nombre, solicitud=None):
        return reverse(f'simulactores:{nombre}', args=[(solicitud or self.solicitud).uuid])

    def recargar(self):
        self.asignacion.refresh_from_db()
        self.solicitud.refresh_from_db()


class HU29ConfirmacionTests(BaseParticipacion):

    def test_confirmacion_exitosa_registra_el_estado(self):
        r = self.client.post(self.url('confirmar_participacion'))
        self.assertRedirects(r, self.url('detalle_simulacion_actor'))
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Confirmada')

    def test_confirmacion_notifica_al_administrador(self):
        self.client.post(self.url('confirmar_participacion'))
        avisos = Notificacion.objects.filter(usuario=self.admin)
        self.assertEqual(avisos.count(), 1)
        aviso = avisos.first()
        self.assertIn('confirmó', aviso.mensaje)
        self.assertIn(self.solicitud.numero_solicitud, aviso.mensaje)
        self.assertEqual(aviso.enlace, self.url('solicitud_admin_detalle'))
        # Cada administrador activo recibe su aviso y su correo.
        self.assertEqual(len(mail.outbox), Notificacion.objects.count())

    def test_confirmacion_queda_en_bitacora(self):
        self.client.post(self.url('confirmar_participacion'))
        fila = Bitacora.objects.get(accion='Respuesta a asignación')
        self.assertEqual(fila.usuario, self.actor.usuario)
        self.assertEqual(fila.valor_nuevo, 'Confirmada')

    def test_el_actor_ve_el_mensaje_de_exito(self):
        r = self.client.post(self.url('confirmar_participacion'), follow=True)
        self.assertContains(r, 'Confirmaste tu participación')

    def test_confirmar_dos_veces_no_duplica_el_aviso(self):
        self.client.post(self.url('confirmar_participacion'))
        r = self.client.post(self.url('confirmar_participacion'), follow=True)
        self.assertContains(r, 'Ya habías confirmado')
        self.assertEqual(Notificacion.objects.filter(usuario=self.admin).count(), 1)

    def test_no_se_confirma_con_get(self):
        r = self.client.get(self.url('confirmar_participacion'))
        self.assertEqual(r.status_code, 405)
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')

    def test_el_detalle_muestra_los_botones_cuando_esta_pendiente(self):
        r = self.client.get(self.url('detalle_simulacion_actor'))
        self.assertContains(r, 'Confirmar participación')
        self.assertContains(r, 'Rechazar')


class HU29RechazoTests(BaseParticipacion):

    def test_rechazo_con_motivo_registra_estado_y_motivo(self):
        r = self.client.post(self.url('rechazar_participacion'), {'motivo': 'Tengo examen ese día'})
        self.assertRedirects(r, reverse('simulactores:dashboard_actor'))
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Rechazada')
        self.assertEqual(self.asignacion.motivo_rechazo, 'Tengo examen ese día')

    def test_rechazo_notifica_al_administrador_con_el_motivo(self):
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'Tengo examen ese día'})
        aviso = Notificacion.objects.get(usuario=self.admin)
        self.assertIn('rechazó', aviso.mensaje)
        self.assertIn('reemplazo', aviso.mensaje)
        self.assertIn('Tengo examen ese día', aviso.mensaje)

    def test_rechazo_sin_motivo_no_se_registra(self):
        for motivo in ['', '   ']:
            r = self.client.post(self.url('rechazar_participacion'), {'motivo': motivo})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Indica el motivo')
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')
        self.assertFalse(Notificacion.objects.filter(usuario=self.admin).exists())

    def test_motivo_demasiado_largo_se_rechaza(self):
        r = self.client.post(self.url('rechazar_participacion'), {'motivo': 'x' * 501})
        self.assertContains(r, 'no puede superar')
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')

    def test_motivo_largo_no_rompe_la_notificacion(self):
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'y' * 500})
        aviso = Notificacion.objects.get(usuario=self.admin)
        self.assertLessEqual(len(aviso.mensaje), 255)

    def test_el_motivo_aparece_para_el_administrador_en_la_solicitud(self):
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'Viaje familiar'})
        self.client.force_login(self.admin)
        r = self.client.get(self.url('solicitud_admin_detalle'))
        self.assertContains(r, 'Viaje familiar')

    def test_tras_el_rechazo_el_administrador_puede_asignar_reemplazo(self):
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'No puedo'})
        self.client.force_login(self.admin)
        r = self.client.get(self.url('asignar_actor'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'ya tiene todos los actores')

    def test_si_la_solicitud_estaba_confirmada_vuelve_a_actor_asignado(self):
        self.solicitud.estado = 'Confirmada'
        self.solicitud.save()
        self.asignacion.estado = 'Confirmada'
        self.asignacion.save()
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'Imprevisto'})
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Rechazada')
        self.assertEqual(self.solicitud.estado, 'Actor Asignado')

    def test_rechazo_queda_en_bitacora(self):
        self.client.post(self.url('rechazar_participacion'), {'motivo': 'Imprevisto'})
        campos = set(Bitacora.objects.filter(accion='Respuesta a asignación')
                     .values_list('campo_modificado', flat=True))
        self.assertEqual(campos, {'estado_asignacion', 'motivo_rechazo'})


class HU29CambioNoPermitidoTests(BaseParticipacion):

    def assert_bloqueado(self, nombre, datos=None):
        r = self.client.post(self.url(nombre), datos or {'motivo': 'x'}, follow=True)
        self.assertContains(r, 'ya no es posible modificar tu participación')
        self.assertFalse(Notificacion.objects.filter(usuario=self.admin).exists())

    def test_simulacion_cancelada_no_permite_confirmar_ni_rechazar(self):
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        Notificacion.objects.all().delete()
        self.assert_bloqueado('confirmar_participacion')
        self.assert_bloqueado('rechazar_participacion')
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')

    def test_simulacion_ejecutada_no_permite_cambios(self):
        self.asignacion.estado = 'Ejecutada'
        self.asignacion.save()
        self.assert_bloqueado('confirmar_participacion')
        self.assert_bloqueado('rechazar_participacion')
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Ejecutada')

    def test_simulacion_completada_no_permite_cambios(self):
        self.solicitud.estado = 'Completada'
        self.solicitud.save()
        self.assert_bloqueado('confirmar_participacion')

    def test_el_detalle_de_una_simulacion_cancelada_no_ofrece_botones(self):
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        r = self.client.get(self.url('detalle_simulacion_actor'))
        self.assertNotContains(r, 'Confirmar participación')
        self.assertContains(r, 'ya no es posible modificar tu participación')

    def test_asignacion_ya_cancelada_por_reasignacion_no_se_puede_responder(self):
        self.asignacion.estado = 'Cancelada'
        self.asignacion.save()
        r = self.client.post(self.url('confirmar_participacion'), follow=True)
        self.assertContains(r, 'ya no es posible modificar tu participación')
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Cancelada')


class HU29AccesoTests(BaseParticipacion):

    def test_un_actor_no_responde_por_la_simulacion_de_otro(self):
        otro = self.crear_actor('otro.part@simgest.com', 'Otro Actor')
        self.client.force_login(otro.usuario)
        for nombre in ['confirmar_participacion', 'rechazar_participacion']:
            r = self.client.post(self.url(nombre), {'motivo': 'x'})
            self.assertEqual(r.status_code, 403)
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')

    def test_cliente_y_administrador_no_pueden_responder(self):
        for usuario in (self.cliente, self.admin):
            self.client.force_login(usuario)
            r = self.client.post(self.url('confirmar_participacion'))
            self.assertEqual(r.status_code, 403)
        self.recargar()
        self.assertEqual(self.asignacion.estado, 'Pendiente')

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        r = self.client.post(self.url('confirmar_participacion'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('simulactores:login'), r.url)
