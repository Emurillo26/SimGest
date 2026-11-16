"""
Pruebas de T13: las habilidades las escribe el actor (sin lista fija).

Cómo correrlas:  python manage.py test simulactores.tests_habilidades
"""

from django.urls import reverse

from .models import Actor, Habilidad, Rol, Usuario
from .tests import BaseSprint2


class HabilidadesEscritasTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='actor.hab@simgest.com', password='Actor123!', nombre='Actor Hab',
            rol=rol_actor, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.client.force_login(self.usuario_actor)
        self.url = reverse('simulactores:perfil')

    def datos(self, habilidades):
        return {
            'nombre': 'Actor Hab', 'telefono': '8888-0000',
            'fecha_nacimiento': '1996-05-20', 'genero': 'Femenino',
            'habilidades': habilidades,
        }

    def nombres(self):
        return sorted(h.nombre for h in self.actor.habilidades.all())

    def test_el_actor_escribe_una_habilidad_nueva(self):
        self.client.post(self.url, self.datos(['  clown   de hospital ']))
        self.assertEqual(self.nombres(), ['Clown de hospital'])
        self.assertTrue(Habilidad.objects.filter(nombre='Clown de hospital').exists())

    def test_reutiliza_una_existente_sin_importar_mayusculas(self):
        existente = Habilidad.objects.create(nombre='Danza')
        self.client.post(self.url, self.datos(['danza']))
        self.assertEqual(list(self.actor.habilidades.all()), [existente])
        self.assertEqual(Habilidad.objects.filter(nombre__iexact='danza').count(), 1)

    def test_no_guarda_repetidas(self):
        self.client.post(self.url, self.datos(['Teatro', 'teatro', 'TEATRO']))
        self.assertEqual(len(self.nombres()), 1)

    def test_el_actor_puede_quitar_habilidades(self):
        self.client.post(self.url, self.datos(['Teatro', 'Canto']))
        self.assertEqual(self.nombres(), ['Canto', 'Teatro'])
        self.client.post(self.url, self.datos(['Canto']))
        self.assertEqual(self.nombres(), ['Canto'])
        self.client.post(self.url, self.datos([]))
        self.assertEqual(self.nombres(), [])

    def test_habilidad_demasiado_larga_se_rechaza(self):
        r = self.client.post(self.url, self.datos(['x' * 101]))
        self.assertContains(r, 'como máximo 100 caracteres')
        self.assertEqual(self.nombres(), [])

    def test_maximo_de_habilidades(self):
        r = self.client.post(self.url, self.datos([f'Habilidad {i}' for i in range(21)]))
        self.assertContains(r, 'hasta 20 habilidades')
        self.assertEqual(self.nombres(), [])

    def test_la_pantalla_muestra_el_editor_con_las_habilidades_actuales(self):
        self.client.post(self.url, self.datos(['Teatro']))
        r = self.client.get(self.url)
        self.assertContains(r, 'id="hab-nueva"')
        self.assertContains(r, 'name="habilidades" value="Teatro"')

    def test_el_administrador_tambien_puede_corregirlas(self):
        self.client.force_login(self.admin)
        url = reverse('simulactores:editar_perfil_actor', args=[self.actor.pk])
        r = self.client.post(url, {
            'fecha_nacimiento': '1990-01-01', 'genero': 'Otro', 'estado': 'Activo',
            'habilidades': ['Improvisación', 'Mimo'],
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.nombres(), ['Improvisación', 'Mimo'])