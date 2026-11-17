
import datetime

from django.urls import reverse

from .models import Actor, Asignacion, Rol, Usuario
from .tests import BaseSprint2


class PaginacionPanelesTests(BaseSprint2):

    def test_panel_cliente_pagina_las_solicitudes_activas(self):
        for i in range(12):
            self.crear_solicitud(fecha=datetime.date(2026, 11, 5) + datetime.timedelta(days=i), hora=9)
        self.client.force_login(self.cliente)
        url = reverse('simulactores:dashboard_cliente')
        r1 = self.client.get(url)
        self.assertEqual(len(r1.context['solicitudes']), 10)
        self.assertContains(r1, 'aria-label="Paginación"')
        r2 = self.client.get(url, {'pagina': 2})
        self.assertEqual(len(r2.context['solicitudes']), 2)

    def test_panel_cliente_sin_exceso_no_muestra_navegacion(self):
        self.crear_solicitud()
        self.client.force_login(self.cliente)
        r = self.client.get(reverse('simulactores:dashboard_cliente'))
        self.assertNotContains(r, 'aria-label="Paginación"')

    def test_panel_actor_pagina_las_simulaciones(self):
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        usuario = Usuario.objects.create_user(
            email='a@simgest.com', password='Actor123!', nombre='Actor A', rol=rol, estado='Activo')
        actor = Actor.objects.create(usuario=usuario)
        for i in range(12):
            s = self.crear_solicitud(estado='Actor Asignado', fecha=datetime.date.today() + datetime.timedelta(days=30 + i))
            Asignacion.objects.create(solicitud=s, actor=actor, estado='Pendiente')
        self.client.force_login(usuario)
        url = reverse('simulactores:dashboard_actor')
        r1 = self.client.get(url)
        self.assertEqual(len(r1.context['asignaciones']), 10)
        r2 = self.client.get(url, {'pagina': 2})
        self.assertEqual(len(r2.context['asignaciones']), 2)
        self.assertContains(r2, 'Anterior')
