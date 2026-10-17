"""
Pruebas automáticas de las HU-18 a HU-23 (Sprint 2).

Cómo correrlas (desde la carpeta del proyecto, con el venv activo):

    python manage.py test simulactores

Django crea una base de datos temporal, ejecuta todo y la borra al terminar;
no toca los datos reales.
"""
import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Bitacora, Categoria, Escenario, Rol, Solicitud, Usuario


class BaseSprint2(TestCase):
    """Datos comunes: un administrador, un cliente, un escenario y una solicitud."""

    def setUp(self):
        rol_admin, _ = Rol.objects.get_or_create(nombre='Administrador')
        rol_cliente, _ = Rol.objects.get_or_create(nombre='Cliente')
        self.admin = Usuario.objects.create_user(
            email='admin.prueba@simgest.com', password='Admin123!',
            nombre='Admin Prueba', rol=rol_admin, estado='Activo')
        self.cliente = Usuario.objects.create_user(
            email='cliente.prueba@simgest.com', password='Cliente123!',
            nombre='Cliente Prueba', rol=rol_cliente, estado='Activo')
        self.client.force_login(self.admin)

        self.categoria, _ = Categoria.objects.get_or_create(nombre='Medicina')
        self.escenario = Escenario.objects.create(
            nombre='Escenario base', descripcion='Descripción', guion='Guion', tipo='Otro')
        self.escenario.categorias.add(self.categoria)

    def crear_solicitud(self, estado='Pendiente', fecha=datetime.date(2026, 11, 5),
                        hora=9, escenario=None):
        return Solicitud.objects.create(
            cliente=self.cliente, tipo_simulacion='Otro', fecha_evento=fecha,
            hora_inicio=datetime.time(hora), hora_fin=datetime.time(hora + 1),
            cantidad_interpretes=1, estado=estado, escenario=escenario)

    def datos_escenario(self, **extra):
        datos = {'nombre': 'Escenario nuevo', 'descripcion': 'Descripción', 'tipo': 'Otro',
                 'guion': 'Guion', 'categorias': [self.categoria.pk]}
        datos.update(extra)
        return datos


class HU18AsignarEscenarioTests(BaseSprint2):

    def url(self, solicitud):
        return reverse('simulactores:solicitud_admin_detalle', args=[solicitud.uuid])

    def otro_escenario(self, **extra):
        datos = {'nombre': 'Otro escenario', 'descripcion': 'Descripción', 'guion': 'Guion', 'tipo': 'Otro'}
        datos.update(extra)
        escenario = Escenario.objects.create(**datos)
        escenario.categorias.add(self.categoria)
        return escenario

    def test_asignacion_exitosa_vincula_cambia_estado_y_notifica(self):
        solicitud = self.crear_solicitud()
        r = self.client.post(self.url(solicitud), {'escenario': self.escenario.pk}, follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.escenario, self.escenario)
        self.assertEqual(solicitud.estado, 'En Revisión')
        self.assertTrue(self.cliente.notificaciones.exists())
        self.assertTrue(Bitacora.objects.filter(campo_modificado='escenario').exists())
        self.assertContains(r, 'Escenario asignado correctamente')

    def test_reemplazar_sin_confirmar_no_cambia_nada(self):
        otro = self.otro_escenario()
        solicitud = self.crear_solicitud(estado='En Revisión', escenario=self.escenario)
        r = self.client.post(self.url(solicitud), {'escenario': otro.pk}, follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.escenario, self.escenario)
        self.assertContains(r, 'Confirma el reemplazo')
        self.assertFalse(self.cliente.notificaciones.exists())

    def test_reemplazar_confirmado_cambia_el_escenario_y_notifica(self):
        otro = self.otro_escenario()
        solicitud = self.crear_solicitud(estado='En Revisión', escenario=self.escenario)
        r = self.client.post(self.url(solicitud), {'escenario': otro.pk, 'confirmar_reemplazo': '1'}, follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.escenario, otro)
        self.assertEqual(solicitud.estado, 'En Revisión')
        self.assertTrue(self.cliente.notificaciones.exists())
        self.assertContains(r, 'Escenario reemplazado correctamente')

    def test_elegir_el_mismo_escenario_no_vuelve_a_notificar(self):
        solicitud = self.crear_solicitud(estado='En Revisión', escenario=self.escenario)
        r = self.client.post(self.url(solicitud), {'escenario': self.escenario.pk}, follow=True)
        self.assertContains(r, 'ya tiene ese escenario')
        self.assertFalse(self.cliente.notificaciones.exists())

    def test_la_pantalla_incluye_el_modal_de_reemplazo(self):
        solicitud = self.crear_solicitud(estado='En Revisión', escenario=self.escenario)
        self.otro_escenario()
        r = self.client.get(self.url(solicitud))
        self.assertContains(r, 'modalReemplazo')
        self.assertContains(r, 'Sí, reemplazar')

    def test_el_selector_solo_ofrece_escenarios_compatibles(self):
        self.otro_escenario(nombre='Escenario solo ECOE', tipo='Examen ECOE')
        solicitud = self.crear_solicitud()
        solicitud.tipo_simulacion = 'Manejo de Crisis'
        solicitud.save()
        r = self.client.get(self.url(solicitud))
        self.assertContains(r, 'Escenario base')                 # tipo Otro: sirve para cualquiera
        self.assertNotContains(r, 'Escenario solo ECOE')         # de otro tipo: no se ofrece

    def test_sin_escenarios_muestra_mensaje_y_opcion_de_crear(self):
        solicitud = self.crear_solicitud()
        Escenario.objects.all().delete()
        r = self.client.get(self.url(solicitud))
        self.assertContains(r, 'No hay escenarios disponibles')
        self.assertContains(r, reverse('simulactores:crear_escenario'))


class HU19CambiarEstadoTests(BaseSprint2):

    def url_estado(self, solicitud):
        return reverse('simulactores:cambiar_estado_solicitud', args=[solicitud.uuid])

    def test_cambio_valido_actualiza_estado_y_notifica_al_cliente(self):
        solicitud = self.crear_solicitud(escenario=self.escenario)
        self.client.post(self.url_estado(solicitud), {'estado': 'En Revisión'})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'En Revisión')
        self.assertTrue(self.cliente.notificaciones.exists())
        self.assertTrue(Bitacora.objects.filter(campo_modificado='estado').exists())

    def test_transicion_no_permitida_mantiene_el_estado(self):
        solicitud = self.crear_solicitud(estado='Completada')
        respuesta = self.client.post(self.url_estado(solicitud), {'estado': 'Pendiente'}, follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'Completada')
        self.assertContains(respuesta, 'No se permite')

    def test_cancelar_sin_motivo_se_rechaza(self):
        solicitud = self.crear_solicitud(estado='En Revisión', escenario=self.escenario)
        self.client.post(self.url_estado(solicitud), {'estado': 'Cancelada', 'motivo': ''})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'En Revisión')

    def test_cancelar_con_motivo_guarda_el_motivo(self):
        solicitud = self.crear_solicitud()
        self.client.post(self.url_estado(solicitud), {'estado': 'Cancelada', 'motivo': 'Sin actores'})
        solicitud.refresh_from_db()
        self.assertEqual((solicitud.estado, solicitud.motivo_cancelacion), ('Cancelada', 'Sin actores'))

    def test_un_cliente_no_puede_cambiar_estados(self):
        solicitud = self.crear_solicitud()
        self.client.force_login(self.cliente)
        self.client.post(self.url_estado(solicitud), {'estado': 'Cancelada', 'motivo': 'x'})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'Pendiente')


class HU20BuscarSolicitudesTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.noviembre = self.crear_solicitud(fecha=datetime.date(2026, 11, 5))
        self.diciembre = self.crear_solicitud(estado='Confirmada', fecha=datetime.date(2026, 12, 5), hora=12)
        self.url = reverse('simulactores:solicitudes_admin')

    def test_filtra_por_rango_de_fechas(self):
        r = self.client.get(self.url, {'desde': '2026-11-01', 'hasta': '2026-11-30'})
        self.assertContains(r, self.noviembre.numero_solicitud)
        self.assertNotContains(r, self.diciembre.numero_solicitud)

    def test_combina_fechas_y_estado(self):
        r = self.client.get(self.url, {'desde': '2026-11-01', 'hasta': '2026-12-31', 'estado': 'Confirmada'})
        self.assertContains(r, self.diciembre.numero_solicitud)
        self.assertNotContains(r, self.noviembre.numero_solicitud)

    def test_busca_por_numero_de_solicitud(self):
        r = self.client.get(self.url, {'q': self.noviembre.numero_solicitud})
        self.assertContains(r, self.noviembre.numero_solicitud)
        self.assertNotContains(r, self.diciembre.numero_solicitud)

    def test_sin_resultados_muestra_mensaje(self):
        r = self.client.get(self.url, {'q': 'zzzz'})
        self.assertContains(r, 'No se encontraron solicitudes con los criterios ingresados')

    def test_rango_invertido_no_rompe_la_pagina(self):
        r = self.client.get(self.url, {'desde': '2026-12-31', 'hasta': '2026-01-01'})
        self.assertEqual(r.status_code, 200)


class HU21CrearEscenarioTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.url = reverse('simulactores:crear_escenario')

    def test_creacion_exitosa_queda_activo(self):
        self.client.post(self.url, self.datos_escenario())
        self.assertEqual(Escenario.objects.get(nombre='Escenario nuevo').estado, 'Activo')

    def test_nombre_duplicado_se_rechaza(self):
        self.client.post(self.url, self.datos_escenario())
        r = self.client.post(self.url, self.datos_escenario(nombre='ESCENARIO NUEVO'))
        self.assertContains(r, 'Ya existe un escenario con ese nombre')
        self.assertEqual(Escenario.objects.filter(nombre__iexact='escenario nuevo').count(), 1)

    def test_campo_obligatorio_vacio_resalta_y_no_guarda(self):
        r = self.client.post(self.url, self.datos_escenario(guion=''))
        self.assertContains(r, 'is-invalid')
        self.assertFalse(Escenario.objects.filter(nombre='Escenario nuevo').exists())

    def test_sin_categoria_se_rechaza(self):
        r = self.client.post(self.url, self.datos_escenario(categorias=[]))
        self.assertContains(r, 'Selecciona al menos una categoría')


class HU22EditarEscenarioTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.url = reverse('simulactores:editar_escenario', args=[self.escenario.pk])

    def datos(self, **extra):
        return self.datos_escenario(nombre=self.escenario.nombre, **extra)

    def test_edicion_exitosa(self):
        r = self.client.post(self.url, self.datos(guion='Guion nuevo'), follow=True)
        self.assertContains(r, 'Escenario actualizado correctamente')
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.guion, 'Guion nuevo')

    def test_campo_obligatorio_vacio_no_guarda(self):
        r = self.client.post(self.url, self.datos(guion=''))
        self.assertContains(r, 'is-invalid')
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.guion, 'Guion')

    def test_escenario_en_uso_pide_confirmacion(self):
        self.crear_solicitud(escenario=self.escenario)
        r = self.client.post(self.url, self.datos(guion='Cambio'))
        self.assertContains(r, 'afectará')
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.guion, 'Guion')          # todavía no se guardó

        self.client.post(self.url, self.datos(guion='Cambio', confirmar_cambio='1'))
        self.escenario.refresh_from_db()
        self.assertEqual(self.escenario.guion, 'Cambio')         # ya confirmado


class HU23ListadoEscenariosTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.url = reverse('simulactores:biblioteca_escenarios')

    def test_lista_escenarios_con_su_informacion(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'Escenario base')
        self.assertContains(r, 'Medicina')

    def test_filtra_por_tipo(self):
        r = self.client.get(self.url, {'tipo': 'Examen ECOE'})
        self.assertNotContains(r, 'Escenario base')
        self.assertContains(r, 'Ningún escenario activo coincide')

    def test_filtra_por_categoria(self):
        otra = Categoria.objects.create(nombre='Categoría vacía de prueba')
        r = self.client.get(self.url, {'categoria': otra.pk})
        self.assertNotContains(r, 'Escenario base')

    def test_detalle_del_escenario(self):
        r = self.client.get(reverse('simulactores:detalle_escenario', args=[self.escenario.pk]))
        self.assertContains(r, 'Escenario base')

    def test_biblioteca_vacia(self):
        Escenario.objects.all().delete()
        self.assertContains(self.client.get(self.url), 'No hay escenarios registrados')

    def test_exige_iniciar_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)