"""
Pruebas automáticas de la HU-30 (notificaciones internas y por correo).

Cómo correrlas:  python manage.py test simulactores
"""
from unittest import mock

from django.core import mail
from django.urls import reverse

from .models import Actor, Asignacion, Bitacora, Notificacion, Rol, Usuario
from .tests import BaseSprint2


class BaseNotificaciones(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='actor.prueba@simgest.com', password='Actor123!',
            nombre='Actor Prueba', rol=rol_actor, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.solicitud = self.crear_solicitud(estado='Aprobada', escenario=self.escenario)

    def asignar(self, estado='Pendiente'):
        return Asignacion.objects.create(solicitud=self.solicitud, actor=self.actor, estado=estado)


class HU30AvisosAutomaticosTests(BaseNotificaciones):

    def test_nueva_asignacion_notifica_al_actor_en_el_sistema_y_por_correo(self):
        self.asignar()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertIn(self.solicitud.numero_solicitud, notificacion.mensaje)
        self.assertFalse(notificacion.leido)
        self.assertTrue(notificacion.correo_enviado)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['actor.prueba@simgest.com'])
        self.assertEqual(mail.outbox[0].subject, 'Nueva simulación asignada')

    def test_cambio_de_fecha_notifica_al_actor(self):
        self.asignar()
        Notificacion.objects.all().delete()
        mail.outbox.clear()
        self.solicitud.fecha_evento = self.solicitud.fecha_evento.replace(day=20)
        self.solicitud.save()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertIn('la fecha', notificacion.mensaje)
        self.assertEqual(mail.outbox[0].subject, 'Cambios en tu simulación')

    def test_cambio_de_escenario_y_horario_se_avisa_en_un_solo_mensaje(self):
        import datetime
        self.asignar()
        Notificacion.objects.all().delete()
        self.solicitud.hora_inicio = datetime.time(14)
        self.solicitud.hora_fin = datetime.time(16)
        self.solicitud.escenario = None
        self.solicitud.save()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertIn('el horario', notificacion.mensaje)
        self.assertIn('el escenario', notificacion.mensaje)

    def test_cancelar_la_solicitud_notifica_al_actor(self):
        self.asignar()
        Notificacion.objects.all().delete()
        mail.outbox.clear()
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertIn('fue cancelada', notificacion.mensaje)
        self.assertEqual(mail.outbox[0].subject, 'Simulación cancelada')

    def test_cancelar_la_asignacion_avisa_al_actor_anterior(self):
        asignacion = self.asignar()
        Notificacion.objects.all().delete()
        asignacion.estado = 'Cancelada'
        asignacion.save()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertIn('Tu asignación', notificacion.mensaje)

    def test_cambios_sin_actor_asignado_no_generan_avisos(self):
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        self.assertFalse(Notificacion.objects.filter(usuario=self.usuario_actor).exists())

    def test_asignacion_rechazada_ya_no_recibe_avisos_de_cambios(self):
        self.asignar(estado='Rechazada')
        Notificacion.objects.all().delete()
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        self.assertFalse(self.usuario_actor.notificaciones.exists())

    def test_guardar_sin_cambios_relevantes_no_notifica(self):
        self.asignar()
        Notificacion.objects.all().delete()
        self.solicitud.observaciones = 'Solo cambió una observación'
        self.solicitud.save()
        self.assertFalse(self.usuario_actor.notificaciones.exists())


class HU30FalloDeCorreoTests(BaseNotificaciones):

    def test_si_el_correo_falla_la_notificacion_interna_se_conserva_y_se_registra(self):
        with mock.patch('simulactores.utils.send_mail', side_effect=OSError('SMTP caído')):
            self.asignar()
        notificacion = self.usuario_actor.notificaciones.get()
        self.assertFalse(notificacion.correo_enviado)
        self.assertIn('SMTP caído', notificacion.error_correo)
        self.assertTrue(
            Bitacora.objects.filter(accion='Fallo de envío de correo', resultado='Fallido').exists())

    def test_la_bandeja_avisa_que_el_correo_no_se_envio(self):
        with mock.patch('simulactores.utils.send_mail', side_effect=OSError('SMTP caído')):
            self.asignar()
        self.client.force_login(self.usuario_actor)
        r = self.client.get(reverse('simulactores:notificaciones'))
        self.assertContains(r, 'no pudo enviarse')


class HU30BandejaTests(BaseNotificaciones):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario_actor)
        self.asignar()
        self.notificacion = self.usuario_actor.notificaciones.get()

    def test_la_bandeja_lista_las_notificaciones_del_usuario(self):
        r = self.client.get(reverse('simulactores:notificaciones'))
        self.assertContains(r, self.solicitud.numero_solicitud)
        self.assertContains(r, 'No leída')

    def test_abrir_una_notificacion_la_marca_como_leida_y_redirige_al_destino(self):
        r = self.client.get(reverse('simulactores:abrir_notificacion', args=[self.notificacion.pk]))
        self.notificacion.refresh_from_db()
        self.assertTrue(self.notificacion.leido)
        self.assertRedirects(r, reverse('simulactores:dashboard_actor'), fetch_redirect_response=False)

    def test_no_se_puede_abrir_la_notificacion_de_otra_persona(self):
        self.client.force_login(self.cliente)
        r = self.client.get(reverse('simulactores:abrir_notificacion', args=[self.notificacion.pk]))
        self.assertEqual(r.status_code, 404)
        self.notificacion.refresh_from_db()
        self.assertFalse(self.notificacion.leido)

    def test_marcar_una_como_leida_solo_acepta_post(self):
        url = reverse('simulactores:marcar_notificacion_leida', args=[self.notificacion.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.notificacion.refresh_from_db()
        self.assertTrue(self.notificacion.leido)

    def test_marcar_todas_como_leidas(self):
        self.solicitud.estado = 'Cancelada'
        self.solicitud.save()
        self.assertEqual(self.usuario_actor.notificaciones.filter(leido=False).count(), 2)
        self.client.post(reverse('simulactores:marcar_notificaciones_leidas'))
        self.assertEqual(self.usuario_actor.notificaciones.filter(leido=False).count(), 0)

    def test_filtro_de_no_leidas(self):
        self.notificacion.leido = True
        self.notificacion.save()
        r = self.client.get(reverse('simulactores:notificaciones'), {'estado': 'no_leidas'})
        self.assertContains(r, 'No tienes notificaciones sin leer')

    def test_el_menu_muestra_el_contador_de_no_leidas(self):
        r = self.client.get(reverse('simulactores:dashboard_actor'))
        self.assertContains(r, 'Notificaciones')
        self.assertContains(r, 'border-radius:999px')

    def test_la_bandeja_requiere_iniciar_sesion(self):
        self.client.logout()
        r = self.client.get(reverse('simulactores:notificaciones'))
        self.assertEqual(r.status_code, 302)

    def test_todos_los_roles_ven_su_bandeja(self):
        for usuario in (self.admin, self.cliente, self.usuario_actor):
            self.client.force_login(usuario)
            r = self.client.get(reverse('simulactores:notificaciones'))
            self.assertEqual(r.status_code, 200)
