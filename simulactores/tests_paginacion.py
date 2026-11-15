"""
Pruebas de la paginación de escenarios, actores, pagos y Mi disponibilidad.

Cómo correrlas:  python manage.py test simulactores.tests_paginacion
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Disponibilidad, Escenario, Pago, Rol, Usuario
from .tests import BaseSprint2


class PaginacionTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')

    def crear_actores(self, cantidad):
        actores = []
        for i in range(cantidad):
            usuario = Usuario.objects.create_user(
                email=f'actor{i:02d}@simgest.com', password='Actor123!',
                nombre=f'Actor {i:02d}', rol=self.rol_actor, estado='Activo')
            actores.append(Actor.objects.create(usuario=usuario))
        return actores

    def test_escenarios_se_paginan_y_cuentan_el_total(self):
        for i in range(10):  # + el escenario base = 11
            Escenario.objects.create(nombre=f'Escenario {i:02d}', tipo='Otro')
        url = reverse('simulactores:biblioteca_escenarios')

        r = self.client.get(url)
        self.assertEqual(len(r.context['escenarios']), 9)
        self.assertContains(r, '11')
        self.assertContains(r, 'pagina=2')

        r = self.client.get(url, {'pagina': 2})
        self.assertEqual(len(r.context['escenarios']), 2)

    def test_actores_se_paginan_y_conservan_los_filtros(self):
        self.crear_actores(12)
        total = Actor.objects.count()  # incluye el actor de las cuentas de desarrollo
        url = reverse('simulactores:actores_admin')

        r = self.client.get(url)
        self.assertEqual(len(r.context['filas']), 10)
        self.assertContains(r, f'{total} actores')

        r = self.client.get(url, {'estado': 'Activo', 'pagina': 2})
        self.assertEqual(len(r.context['filas']), Actor.objects.filter(estado='Activo').count() - 10)
        self.assertContains(r, 'estado=Activo')

    def test_pagos_se_paginan(self):
        actor = self.crear_actores(1)[0]
        for mes in range(1, 13):
            Pago.objects.create(actor=actor, periodo_mes=mes, periodo_anio=2026, monto_total=1000)
        url = reverse('simulactores:pagos_admin')

        self.assertEqual(len(self.client.get(url).context['pagos']), 10)
        self.assertEqual(len(self.client.get(url, {'pagina': 2}).context['pagos']), 2)

    def test_mi_disponibilidad_se_pagina(self):
        actor = self.crear_actores(1)[0]
        hoy = timezone.localdate()
        for dia in range(1, 13):
            Disponibilidad.objects.create(
                actor=actor, fecha=hoy + datetime.timedelta(days=dia),
                hora_inicio=datetime.time(8), hora_fin=datetime.time(12))
        self.client.force_login(actor.usuario)
        url = reverse('simulactores:mi_disponibilidad')

        self.assertEqual(len(self.client.get(url).context['bloques']), 10)
        self.assertEqual(len(self.client.get(url, {'pagina': 2}).context['bloques']), 2)

    def test_pagina_invalida_muestra_la_ultima(self):
        self.crear_actores(12)
        r = self.client.get(reverse('simulactores:actores_admin'), {'pagina': 99})
        self.assertEqual(len(r.context['filas']), Actor.objects.count() - 10)

    def test_sin_paginacion_si_cabe_en_una_pagina(self):
        self.crear_actores(3)
        r = self.client.get(reverse('simulactores:actores_admin'))
        self.assertNotContains(r, 'aria-label="Paginación"')
