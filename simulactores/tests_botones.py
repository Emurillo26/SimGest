
import datetime
import re

from django.urls import reverse

from .models import Actor, Asignacion, Rol, Usuario
from .tests import BaseSprint2

HREF = re.compile(r'<a\s[^>]*href="(/[^"#]*)"')
POST_SOLO = ('/logout', '/notificaciones/leidas', '/cancelar', '/aprobar', '/rechazar',
             '/eliminar', '/marcar')


class EnlacesTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='a@simgest.com', password='Actor123!', nombre='Actor A', rol=rol, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.solicitud = self.crear_solicitud(estado='Actor Asignado', escenario=self.escenario)
        Asignacion.objects.create(solicitud=self.solicitud, actor=self.actor, estado='Pendiente')

    def revisar(self, usuario, nombres):
        self.client.force_login(usuario)
        vistos = set()
        for nombre in nombres:
            r = self.client.get(reverse(f'simulactores:{nombre}'))
            self.assertEqual(r.status_code, 200, nombre)
            for destino in HREF.findall(r.content.decode()):
                if destino in vistos or destino.startswith(('/static', '/media', '/admin')):
                    continue
                vistos.add(destino)
                if any(destino.rstrip('/').endswith(p) or p + '/' in destino for p in POST_SOLO):
                    continue
                respuesta = self.client.get(destino)
                self.assertIn(respuesta.status_code, (200, 302, 405),
                              f'{destino} (desde {nombre}) respondió {respuesta.status_code}')
        return vistos

    def test_enlaces_del_cliente(self):
        vistos = self.revisar(self.cliente, ['dashboard_cliente', 'mis_solicitudes',
                                             'historial_solicitudes', 'crear_solicitud',
                                             'notificaciones', 'perfil'])
        self.assertTrue(vistos)

    def test_enlaces_del_actor(self):
        vistos = self.revisar(self.usuario_actor, ['dashboard_actor', 'calendario_actor',
                                                   'mi_disponibilidad', 'notificaciones', 'perfil'])
        self.assertTrue(vistos)
