
from django.urls import reverse

from .tests_asignacion import BaseAsignacion


class FiltrosFisicosTests(BaseAsignacion):

    def setUp(self):
        super().setUp()
        self.actor.estatura_cm = 170
        self.actor.color_cabello = 'Negro'
        self.actor.color_ojos = 'Café oscuro'
        self.actor.contextura = 'Media'
        self.actor.tono_piel = 'Trigueña'
        self.actor.talla_ropa = 'M'
        self.actor.talla_calzado = 40
        self.actor.save()
        self.rubio = self.crear_actor('dos@simgest.com', 'Actor Rubio')
        self.rubio.estatura_cm = 185
        self.rubio.color_cabello = 'Rubio'
        self.rubio.save()
        self.sin_datos = self.crear_actor('tres@simgest.com', 'Actor Sin Datos')
        self.lista = reverse('simulactores:actores_admin')

    def nombres(self, r):
        return {f['actor'].usuario.nombre for f in r.context['filas']}

    def test_lista_sin_filtros_muestra_a_todos(self):
        r = self.client.get(self.lista)
        self.assertEqual(self.nombres(r), {'Actor Uno', 'Actor Rubio', 'Actor Sin Datos', 'Actor de Prueba'})

    def test_lista_filtra_por_cabello(self):
        r = self.client.get(self.lista, {'color_cabello': 'Negro'})
        self.assertEqual(self.nombres(r), {'Actor Uno'})

    def test_lista_filtra_por_rango_de_estatura(self):
        r = self.client.get(self.lista, {'estatura_min': 180, 'estatura_max': 200})
        self.assertEqual(self.nombres(r), {'Actor Rubio'})

    def test_lista_combina_varios_criterios(self):
        r = self.client.get(self.lista, {'color_cabello': 'Negro', 'tono_piel': 'Trigueña',
                                         'talla_ropa': 'M', 'talla_calzado': '40',
                                         'contextura': 'Media', 'color_ojos': 'Café oscuro'})
        self.assertEqual(self.nombres(r), {'Actor Uno'})
        r = self.client.get(self.lista, {'color_cabello': 'Negro', 'talla_ropa': 'XL'})
        self.assertEqual(self.nombres(r), set())

    def test_estatura_invalida_se_rechaza(self):
        r = self.client.get(self.lista, {'estatura_min': 200, 'estatura_max': 150})
        self.assertContains(r, 'no puede ser menor')

    def test_asignacion_sin_filtros_ofrece_a_todos_los_disponibles(self):
        r = self.client.get(self.url_asignar())
        self.assertEqual(self.nombres(r), {'Actor Uno', 'Actor Rubio', 'Actor Sin Datos', 'Actor de Prueba'})

    def test_asignacion_filtra_por_cabello(self):
        r = self.client.get(self.url_asignar(), {'color_cabello': 'Negro'})
        self.assertEqual(self.nombres(r), {'Actor Uno'})

    def test_asignacion_combina_caracteristica_con_disponibilidad(self):
        # El rubio no tiene disponibilidad ese día: aparece marcado, no elegible.
        self.rubio.disponibilidades.all().delete()
        r = self.client.get(self.url_asignar(), {'color_cabello': 'Rubio'})
        fila = r.context['filas'][0]
        self.assertEqual(fila['actor'], self.rubio)
        self.assertFalse(fila['disponible'])
        self.assertFalse(r.context['hay_disponibles'])

    def test_asignacion_sin_coincidencias_avisa(self):
        r = self.client.get(self.url_asignar(), {'color_cabello': 'Pelirrojo'})
        self.assertContains(r, 'Ningún actor cumple esas características')

    def test_asignar_conserva_los_filtros_al_publicar(self):
        r = self.client.post(self.url_asignar() + '?color_cabello=Negro', {'actor': self.actor.pk}, follow=True)
        self.assertContains(r, 'Actor asignado correctamente')
