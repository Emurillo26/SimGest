"""
Pruebas automáticas de HU-26 (dashboard del actor) y HU-28 (detalle de la simulación).

Cómo correrlas:  python manage.py test simulactores.tests_actor_dashboard
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Asignacion, Rol, Solicitud, Usuario
from .tests import BaseSprint2


class BaseActor(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = self._crear_actor('dash.actor@simgest.com', 'Actor Dashboard')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.usuario_otro = self._crear_actor('otro.actor@simgest.com', 'Otro Actor')
        self.otro = Actor.objects.create(usuario=self.usuario_otro)
        self.client.force_login(self.usuario_actor)
        self.url_dashboard = reverse('simulactores:dashboard_actor')

    def _crear_actor(self, email, nombre):
        return Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre,
            rol=self.rol_actor, estado='Activo')

    def en_dias(self, dias):
        return timezone.localdate() + datetime.timedelta(days=dias)

    def asignar(self, actor, dias=3, estado_asignacion='Pendiente',
                estado_solicitud='Actor Asignado', hora=9, **extra):
        solicitud = self.crear_solicitud(
            estado=estado_solicitud, fecha=self.en_dias(dias), hora=hora,
            escenario=self.escenario)
        for campo, valor in extra.items():
            setattr(solicitud, campo, valor)
        if extra:
            solicitud.save()
        asignacion = Asignacion.objects.create(
            solicitud=solicitud, actor=actor, estado=estado_asignacion)
        return solicitud, asignacion

    def url_detalle(self, solicitud):
        return reverse('simulactores:detalle_simulacion_actor', args=[solicitud.uuid])


class HU26DashboardTests(BaseActor):

    def test_muestra_las_simulaciones_futuras_del_actor(self):
        solicitud, _ = self.asignar(self.actor, dias=3)
        r = self.client.get(self.url_dashboard)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, solicitud.numero_solicitud)
        self.assertContains(r, self.url_detalle(solicitud))

    def test_no_muestra_simulaciones_de_otros_actores(self):
        propia, _ = self.asignar(self.actor, dias=3, hora=9)
        ajena, _ = self.asignar(self.otro, dias=4, hora=11)
        r = self.client.get(self.url_dashboard)
        self.assertContains(r, propia.numero_solicitud)
        self.assertNotContains(r, ajena.numero_solicitud)

    def test_no_muestra_simulaciones_pasadas(self):
        pasada, _ = self.asignar(self.actor, dias=-2)
        r = self.client.get(self.url_dashboard)
        self.assertNotContains(r, pasada.numero_solicitud)

    def test_no_muestra_asignaciones_rechazadas_ni_canceladas(self):
        rechazada, _ = self.asignar(self.actor, dias=3, estado_asignacion='Rechazada', hora=8)
        cancelada, _ = self.asignar(self.actor, dias=4, estado_asignacion='Cancelada', hora=10)
        sol_cancelada, _ = self.asignar(
            self.actor, dias=5, estado_solicitud='Cancelada', hora=12)
        r = self.client.get(self.url_dashboard)
        for s in (rechazada, cancelada, sol_cancelada):
            self.assertNotContains(r, s.numero_solicitud)

    def test_resumen_cuenta_pendientes_y_confirmadas(self):
        self.asignar(self.actor, dias=2, estado_asignacion='Pendiente', hora=8)
        self.asignar(self.actor, dias=3, estado_asignacion='Pendiente', hora=10)
        self.asignar(self.actor, dias=4, estado_asignacion='Confirmada', hora=12)
        r = self.client.get(self.url_dashboard)
        self.assertEqual(r.context['resumen'], {'total': 3, 'pendientes': 2, 'confirmadas': 1})

    def test_las_simulaciones_salen_ordenadas_por_fecha(self):
        lejana, _ = self.asignar(self.actor, dias=10, hora=9)
        cercana, _ = self.asignar(self.actor, dias=2, hora=9)
        r = self.client.get(self.url_dashboard)
        numeros = [a.solicitud.numero_solicitud for a in r.context['asignaciones']]
        self.assertEqual(numeros, [cercana.numero_solicitud, lejana.numero_solicitud])

    def test_sin_simulaciones_muestra_mensaje_informativo(self):
        r = self.client.get(self.url_dashboard)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No tienes simulaciones programadas')
        self.assertEqual(r.context['resumen']['total'], 0)

    def test_muestra_fecha_horario_y_estado(self):
        solicitud, _ = self.asignar(self.actor, dias=3, hora=9)
        r = self.client.get(self.url_dashboard)
        self.assertContains(r, solicitud.fecha_evento.strftime('%d/%m/%Y'))
        self.assertContains(r, '09:00')
        self.assertContains(r, 'Pendiente')

    def test_actor_sin_perfil_de_actor_no_falla(self):
        sin_perfil = self._crear_actor('sin.perfil@simgest.com', 'Sin Perfil')
        self.client.force_login(sin_perfil)
        r = self.client.get(self.url_dashboard)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['resumen']['total'], 0)

    def test_un_cliente_no_entra_al_dashboard_del_actor(self):
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get(self.url_dashboard).status_code, 200)

    def test_sin_iniciar_sesion_redirige_al_login(self):
        self.client.logout()
        r = self.client.get(self.url_dashboard)
        self.assertEqual(r.status_code, 302)


class HU28DetalleTests(BaseActor):

    def test_muestra_los_datos_de_la_simulacion(self):
        solicitud, _ = self.asignar(
            self.actor, dias=3, hora=9, ubicacion='Hospital Central',
            observaciones='Llevar bata blanca')
        r = self.client.get(self.url_detalle(solicitud))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, solicitud.numero_solicitud)
        self.assertContains(r, 'Hospital Central')
        self.assertContains(r, 'Llevar bata blanca')
        self.assertContains(r, '09:00')
        self.assertContains(r, self.escenario.nombre)
        self.assertContains(r, self.escenario.guion)

    def test_sin_ubicacion_ni_observaciones_muestra_texto_por_defecto(self):
        solicitud, _ = self.asignar(self.actor, dias=3)
        r = self.client.get(self.url_detalle(solicitud))
        self.assertContains(r, 'Por definir')
        self.assertContains(r, 'Sin observaciones')

    def test_el_actor_ve_su_estado_de_asignacion(self):
        solicitud, _ = self.asignar(self.actor, dias=3, estado_asignacion='Confirmada')
        r = self.client.get(self.url_detalle(solicitud))
        self.assertContains(r, 'Confirmada')

    def test_simulacion_de_otro_actor_da_403_y_no_filtra_datos(self):
        ajena, _ = self.asignar(self.otro, dias=3, ubicacion='Lugar secreto')
        r = self.client.get(self.url_detalle(ajena))
        self.assertEqual(r.status_code, 403)
        self.assertNotContains(r, 'Lugar secreto', status_code=403)

    def test_simulacion_inexistente_da_403(self):
        r = self.client.get(reverse(
            'simulactores:detalle_simulacion_actor',
            args=['00000000-0000-0000-0000-000000000000']))
        self.assertEqual(r.status_code, 403)

    def test_asignacion_rechazada_no_se_puede_abrir(self):
        solicitud, _ = self.asignar(self.actor, dias=3, estado_asignacion='Rechazada')
        self.assertEqual(self.client.get(self.url_detalle(solicitud)).status_code, 403)

    def test_asignacion_cancelada_no_se_puede_abrir(self):
        solicitud, _ = self.asignar(self.actor, dias=3, estado_asignacion='Cancelada')
        self.assertEqual(self.client.get(self.url_detalle(solicitud)).status_code, 403)

    def test_asignacion_ejecutada_si_se_puede_consultar(self):
        solicitud, _ = self.asignar(
            self.actor, dias=-3, estado_asignacion='Ejecutada', estado_solicitud='Completada')
        self.assertEqual(self.client.get(self.url_detalle(solicitud)).status_code, 200)

    def test_una_ejecutada_ya_no_ofrece_responder(self):
        solicitud, _ = self.asignar(
            self.actor, dias=-3, estado_asignacion='Ejecutada', estado_solicitud='Completada')
        r = self.client.get(self.url_detalle(solicitud))
        self.assertFalse(r.context['puede_responder'])

    def test_una_pendiente_vigente_permite_responder(self):
        solicitud, _ = self.asignar(self.actor, dias=3)
        r = self.client.get(self.url_detalle(solicitud))
        self.assertTrue(r.context['puede_responder'])

    def test_un_cliente_no_entra_al_detalle_del_actor(self):
        solicitud, _ = self.asignar(self.actor, dias=3)
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get(self.url_detalle(solicitud)).status_code, 200)

    def test_desde_el_dashboard_se_llega_al_detalle(self):
        solicitud, _ = self.asignar(self.actor, dias=3)
        r = self.client.get(self.url_dashboard)
        self.assertContains(r, self.url_detalle(solicitud))
        self.assertEqual(self.client.get(self.url_detalle(solicitud)).status_code, 200)