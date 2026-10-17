"""
Pruebas automáticas de HU-24 (archivar / reactivar escenarios)
y HU-25 (crear categoría desde el formulario de escenario).

Cómo correrlas:  python manage.py test simulactores
"""
from django.urls import reverse

from .models import Bitacora, Categoria, Escenario
from .tests import BaseSprint2


class HU24ArchivarEscenarioTests(BaseSprint2):

    def url_archivar(self, escenario=None):
        return reverse('simulactores:archivar_escenario', args=[(escenario or self.escenario).pk])

    def url_reactivar(self, escenario=None):
        return reverse('simulactores:reactivar_escenario', args=[(escenario or self.escenario).pk])

    def test_archivar_escenario_sin_solicitudes_activas(self):
        self.client.post(self.url_archivar())
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.estado, 'Archivado')
        self.assertTrue(Bitacora.objects.filter(campo_modificado='estado').exists())

    def test_no_archiva_si_tiene_solicitudes_activas(self):
        self.crear_solicitud(estado='Aprobada', escenario=self.escenario)
        r = self.client.post(self.url_archivar(), follow=True)
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.estado, 'Activo')
        self.assertContains(r, 'No se puede archivar')

    def test_archivar_con_solicitud_completada_si_se_permite(self):
        self.crear_solicitud(estado='Completada', escenario=self.escenario)
        self.client.post(self.url_archivar())
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.estado, 'Archivado')

    def test_reactivar_escenario_archivado(self):
        self.escenario.estado = 'Archivado'
        self.escenario.save()
        self.client.post(self.url_reactivar())
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.estado, 'Activo')
        self.assertTrue(Bitacora.objects.filter(campo_modificado='estado').exists())

    def test_archivar_y_reactivar_solo_aceptan_post(self):
        self.assertEqual(self.client.get(self.url_archivar()).status_code, 405)
        self.assertEqual(self.client.get(self.url_reactivar()).status_code, 405)

    def test_cliente_no_puede_archivar(self):
        self.client.force_login(self.cliente)
        self.client.post(self.url_archivar())
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.estado, 'Activo')

    def test_listado_muestra_solo_activos_por_defecto(self):
        archivado = Escenario.objects.create(
            nombre='Escenario archivado', descripcion='d', guion='g', tipo='Otro', estado='Archivado')
        r = self.client.get(reverse('simulactores:biblioteca_escenarios'))
        self.assertContains(r, 'Escenario base')
        self.assertNotContains(r, archivado.nombre)

    def test_listado_filtra_archivados(self):
        Escenario.objects.create(
            nombre='Escenario archivado', descripcion='d', guion='g', tipo='Otro', estado='Archivado')
        r = self.client.get(reverse('simulactores:biblioteca_escenarios'), {'estado': 'Archivado'})
        self.assertContains(r, 'Escenario archivado')
        self.assertNotContains(r, 'Escenario base')

    def test_escenario_archivado_no_se_puede_asignar_a_solicitud(self):
        self.escenario.estado = 'Archivado'
        self.escenario.save()
        solicitud = self.crear_solicitud()
        url = reverse('simulactores:solicitud_admin_detalle', args=[solicitud.uuid])
        self.client.post(url, {'escenario': self.escenario.pk})
        solicitud.refresh_from_db()
        self.assertIsNone(solicitud.escenario)


class HU25CrearCategoriaTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.url = reverse('simulactores:crear_escenario')

    def test_crea_categoria_nueva_y_la_asocia(self):
        datos = self.datos_escenario(categorias=[], nueva_categoria='Pediatría')
        self.client.post(self.url, datos)
        escenario = Escenario.objects.get(nombre='Escenario nuevo')
        self.assertTrue(Categoria.objects.filter(nombre='Pediatría').exists())
        self.assertEqual([c.nombre for c in escenario.categorias.all()], ['Pediatría'])

    def test_reutiliza_categoria_existente_sin_duplicar(self):
        datos = self.datos_escenario(categorias=[], nueva_categoria='medicina')
        self.client.post(self.url, datos)
        self.assertEqual(Categoria.objects.filter(nombre__iexact='medicina').count(), 1)
        escenario = Escenario.objects.get(nombre='Escenario nuevo')
        self.assertIn(self.categoria, escenario.categorias.all())

    def test_combina_categoria_existente_y_nueva(self):
        datos = self.datos_escenario(nueva_categoria='Pediatría')
        self.client.post(self.url, datos)
        escenario = Escenario.objects.get(nombre='Escenario nuevo')
        self.assertEqual(escenario.categorias.count(), 2)

    def test_exige_al_menos_una_categoria(self):
        datos = self.datos_escenario(categorias=[], nueva_categoria='')
        r = self.client.post(self.url, datos)
        self.assertFalse(Escenario.objects.filter(nombre='Escenario nuevo').exists())
        self.assertContains(r, 'Selecciona al menos una categoría o crea una nueva.')