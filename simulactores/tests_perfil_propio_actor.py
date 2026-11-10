"""
Pruebas de «Mi perfil» para el actor: datos personales, habilidades y
características físicas que el actor llena por sí mismo.

Cómo correrlas:  python manage.py test simulactores.tests_perfil_propio_actor
"""
import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Bitacora, Habilidad, Rol, Usuario
from .tests import BaseSprint2


class BasePerfilPropio(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='propio.actor@simgest.com', password='Actor123!',
            nombre='Actor Propio', rol=rol_actor, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.hab1 = Habilidad.objects.create(nombre='Habilidad propia A')
        self.hab2 = Habilidad.objects.create(nombre='Habilidad propia B')
        self.client.force_login(self.usuario_actor)
        self.url = reverse('simulactores:perfil')

    def datos(self, **extra):
        datos = {
            'nombre': 'Actor Propio', 'telefono': '8888-0000',
            'fecha_nacimiento': '1996-05-20', 'genero': 'Femenino',
            'tarifa': '12000.50', 'tipo_tarifa': 'Por Hora',
            'habilidades': [self.hab1.pk, self.hab2.pk],
            'estatura_cm': '168', 'peso_kg': '60.5',
            'color_cabello': 'Negro', 'color_ojos': 'Café oscuro',
            'contextura': 'Media', 'tono_piel': 'Trigueña',
            'talla_ropa': 'M', 'talla_calzado': '38.5',
            'otras_caracteristicas': 'Usa lentes.',
        }
        datos.update(extra)
        return datos


class PerfilPropioGuardadoTests(BasePerfilPropio):

    def test_el_actor_ve_las_secciones_de_actor(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'Características físicas')
        self.assertContains(r, 'Habilidades')
        self.assertContains(r, 'Datos del actor')
        self.assertContains(r, 'Habilidad propia A')

    def test_guarda_todos_los_datos(self):
        r = self.client.post(self.url, self.datos(), follow=True)
        self.assertContains(r, 'Perfil actualizado correctamente')
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.fecha_nacimiento, datetime.date(1996, 5, 20))
        self.assertEqual(self.actor.genero, 'Femenino')
        self.assertEqual(self.actor.estatura_cm, 168)
        self.assertEqual(self.actor.peso_kg, Decimal('60.5'))
        self.assertEqual(self.actor.color_cabello, 'Negro')
        self.assertEqual(self.actor.color_ojos, 'Café oscuro')
        self.assertEqual(self.actor.contextura, 'Media')
        self.assertEqual(self.actor.tono_piel, 'Trigueña')
        self.assertEqual(self.actor.talla_ropa, 'M')
        self.assertEqual(self.actor.talla_calzado, Decimal('38.5'))
        self.assertEqual(self.actor.otras_caracteristicas, 'Usa lentes.')
        self.assertEqual(set(self.actor.habilidades.all()), {self.hab1, self.hab2})

    def test_los_datos_guardados_aparecen_al_volver(self):
        self.client.post(self.url, self.datos())
        r = self.client.get(self.url)
        self.assertContains(r, 'value="168"')
        self.assertContains(r, 'Usa lentes.')

    def test_los_campos_fisicos_son_opcionales(self):
        r = self.client.post(self.url, self.datos(
            estatura_cm='', peso_kg='', color_cabello='', color_ojos='', contextura='',
            tono_piel='', talla_ropa='', talla_calzado='', otras_caracteristicas=''), follow=True)
        self.assertContains(r, 'Perfil actualizado correctamente')
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.estatura_cm)
        self.assertIsNone(self.actor.color_cabello)

    def test_queda_en_la_bitacora(self):
        self.client.post(self.url, self.datos())
        self.assertTrue(Bitacora.objects.filter(
            accion='Perfil de actor actualizado por el actor',
            campo_modificado='estatura_cm', valor_nuevo='168').exists())

    def test_sin_cambios_no_escribe_bitacora_de_actor(self):
        self.client.post(self.url, self.datos())
        total = Bitacora.objects.filter(accion='Perfil de actor actualizado por el actor').count()
        self.client.post(self.url, self.datos())
        self.assertEqual(
            Bitacora.objects.filter(accion='Perfil de actor actualizado por el actor').count(), total)

    def test_el_actor_guarda_su_tarifa_y_queda_en_el_historial(self):
        self.client.post(self.url, self.datos())
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.tarifa, Decimal('12000.50'))
        self.assertEqual(self.actor.tipo_tarifa, 'Por Hora')
        self.assertEqual(self.actor.historial_tarifas.count(), 1)
        self.assertTrue(Bitacora.objects.filter(
            accion='Perfil de actor actualizado por el actor', campo_modificado='tarifa').exists())

    def test_no_puede_cambiar_su_estado(self):
        self.client.post(self.url, self.datos(estado='Inactivo'))
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.estado, 'Activo')


class PerfilPropioValidacionTests(BasePerfilPropio):

    def assert_rechaza(self, r, texto):
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, texto)
        self.assertContains(r, 'Revisa los campos marcados en rojo')
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.estatura_cm)
        self.assertIsNone(self.actor.fecha_nacimiento)

    def test_estatura_fuera_de_rango(self):
        r = self.client.post(self.url, self.datos(estatura_cm='50'))
        self.assert_rechaza(r, 'entre 100 y 230 cm')

    def test_peso_fuera_de_rango(self):
        r = self.client.post(self.url, self.datos(peso_kg='500'))
        self.assert_rechaza(r, 'entre 30 y 250 kg')

    def test_talla_de_calzado_fuera_de_rango(self):
        r = self.client.post(self.url, self.datos(talla_calzado='5'))
        self.assert_rechaza(r, 'entre 20 y 50')

    def test_estatura_no_numerica(self):
        r = self.client.post(self.url, self.datos(estatura_cm='alto'))
        self.assert_rechaza(r, 'número entero')

    def test_fecha_de_nacimiento_obligatoria(self):
        r = self.client.post(self.url, self.datos(fecha_nacimiento=''))
        self.assertContains(r, 'Indica tu fecha de nacimiento')
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.estatura_cm)

    def test_genero_obligatorio(self):
        r = self.client.post(self.url, self.datos(genero=''))
        self.assertContains(r, 'Selecciona tu género')

    def test_fecha_futura_y_menor_de_edad(self):
        futura = (timezone.localdate() + datetime.timedelta(days=30)).isoformat()
        r = self.client.post(self.url, self.datos(fecha_nacimiento=futura))
        self.assertContains(r, 'no puede ser futura')
        reciente = (timezone.localdate() - datetime.timedelta(days=365 * 10)).isoformat()
        r = self.client.post(self.url, self.datos(fecha_nacimiento=reciente))
        self.assertContains(r, 'al menos 18 años')

    def test_valor_de_lista_no_valido(self):
        r = self.client.post(self.url, self.datos(color_ojos='Violeta'))
        self.assertEqual(r.status_code, 200)
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.color_ojos)

    def test_un_error_no_guarda_ni_el_nombre(self):
        self.client.post(self.url, self.datos(nombre='Nombre nuevo', estatura_cm='50'))
        self.usuario_actor.refresh_from_db()
        self.assertEqual(self.usuario_actor.nombre, 'Actor Propio')


    def test_tarifa_obligatoria_negativa_y_cero(self):
        for valor, texto in (('', 'Indica tu tarifa'), ('-5', 'no puede ser negativa'), ('0', 'mayor que cero')):
            r = self.client.post(self.url, self.datos(tarifa=valor))
            self.assertContains(r, texto)
        self.actor.refresh_from_db()
        self.assertIsNone(self.actor.tarifa)

    def test_tipo_de_tarifa_obligatorio(self):
        r = self.client.post(self.url, self.datos(tipo_tarifa=''))
        self.assertContains(r, 'por hora o por evento')


class PerfilPropioOtrosRolesTests(BasePerfilPropio):

    def test_el_cliente_no_ve_secciones_de_actor(self):
        self.client.force_login(self.cliente)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Características físicas')

    def test_el_cliente_sigue_pudiendo_editar_su_nombre(self):
        self.client.force_login(self.cliente)
        r = self.client.post(self.url, {'nombre': 'Cliente Nuevo', 'telefono': ''}, follow=True)
        self.assertContains(r, 'Perfil actualizado correctamente')
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nombre, 'Cliente Nuevo')

    def test_el_administrador_ve_las_caracteristicas_fisicas_del_actor(self):
        self.actor.estatura_cm = 172
        self.actor.color_ojos = 'Verdes'
        self.actor.save()
        self.client.force_login(self.admin)
        r = self.client.get(reverse('simulactores:editar_perfil_actor', args=[self.actor.pk]))
        self.assertContains(r, 'Características físicas')
        self.assertContains(r, '172 cm')
        self.assertContains(r, 'Verdes')
        self.assertContains(r, 'Sin completar')

    def test_las_habilidades_iniciales_existen(self):
        self.assertTrue(Habilidad.objects.filter(nombre='Improvisación').exists())