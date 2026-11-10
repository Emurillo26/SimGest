"""
Pruebas automáticas de HU-36 (filtrar actores por perfil) y HU-38 (historial de asignaciones).

Cómo correrlas:  python manage.py test simulactores.tests_filtro_historial_actor
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from .models import Actor, Asignacion, Habilidad, Rol, Usuario
from .tests import BaseSprint2


def nacido_hace(anios):
    """Fecha de nacimiento que hoy da exactamente esa edad (cumplió años hace unas semanas)."""
    return timezone.localdate() - datetime.timedelta(days=int(anios * 365.25) + 30)


class BaseActores(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.hab_a = Habilidad.objects.create(nombre='Hab Filtro A')
        self.hab_b = Habilidad.objects.create(nombre='Hab Filtro B')
        self.ana = self.crear('ana@simgest.com', 'Ana Filtro', 25, 'Femenino', [self.hab_a])
        self.bruno = self.crear('bruno@simgest.com', 'Bruno Filtro', 40, 'Masculino', [self.hab_a, self.hab_b])
        self.carla = self.crear('carla@simgest.com', 'Carla Filtro', 60, 'Femenino', [self.hab_b], estado='Inactivo')
        self.url = reverse('simulactores:actores_admin')

    def crear(self, email, nombre, edad, genero, habilidades, estado='Activo'):
        usuario = Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre, rol=self.rol_actor, estado='Activo')
        actor = Actor.objects.create(
            usuario=usuario, fecha_nacimiento=nacido_hace(edad), genero=genero, estado=estado)
        actor.habilidades.set(habilidades)
        return actor


class HU36FiltrarActoresTests(BaseActores):

    def nombres(self, respuesta):
        return [f['actor'].usuario.nombre for f in respuesta.context['filas']
                if 'Filtro' in f['actor'].usuario.nombre]

    def test_sin_filtros_muestra_a_todos(self):
        r = self.client.get(self.url)
        self.assertEqual(set(self.nombres(r)), {'Ana Filtro', 'Bruno Filtro', 'Carla Filtro'})

    def test_filtra_por_rango_de_edad(self):
        r = self.client.get(self.url, {'edad_min': 30, 'edad_max': 50})
        self.assertEqual(self.nombres(r), ['Bruno Filtro'])

    def test_filtra_solo_por_edad_minima(self):
        r = self.client.get(self.url, {'edad_min': 50})
        self.assertEqual(self.nombres(r), ['Carla Filtro'])

    def test_filtra_solo_por_edad_maxima(self):
        r = self.client.get(self.url, {'edad_max': 30})
        self.assertEqual(self.nombres(r), ['Ana Filtro'])

    def test_filtra_por_genero(self):
        r = self.client.get(self.url, {'genero': 'Masculino'})
        self.assertEqual(self.nombres(r), ['Bruno Filtro'])

    def test_filtra_por_una_habilidad(self):
        r = self.client.get(self.url, {'habilidades': [self.hab_b.pk]})
        self.assertEqual(set(self.nombres(r)), {'Bruno Filtro', 'Carla Filtro'})

    def test_con_varias_habilidades_debe_tener_todas(self):
        r = self.client.get(self.url, {'habilidades': [self.hab_a.pk, self.hab_b.pk]})
        self.assertEqual(self.nombres(r), ['Bruno Filtro'])

    def test_filtra_por_estado(self):
        r = self.client.get(self.url, {'estado': 'Inactivo'})
        self.assertEqual(self.nombres(r), ['Carla Filtro'])

    def test_combina_varios_criterios(self):
        r = self.client.get(self.url, {'genero': 'Femenino', 'habilidades': [self.hab_b.pk]})
        self.assertEqual(self.nombres(r), ['Carla Filtro'])

    def test_sin_resultados_muestra_mensaje(self):
        r = self.client.get(self.url, {'edad_min': 30, 'genero': 'Femenino', 'habilidades': [self.hab_a.pk]})
        self.assertEqual(self.nombres(r), [])
        self.assertContains(r, 'No se encontraron actores con ese perfil')

    def test_rango_invertido_muestra_error_y_no_filtra(self):
        r = self.client.get(self.url, {'edad_min': 50, 'edad_max': 20})
        self.assertContains(r, 'no puede ser menor que la mínima')
        self.assertEqual(len(self.nombres(r)), 3)

    def test_edad_no_numerica_muestra_error(self):
        r = self.client.get(self.url, {'edad_min': 'abc'})
        self.assertContains(r, 'número entero')

    def test_edad_negativa_muestra_error(self):
        r = self.client.get(self.url, {'edad_min': -5})
        self.assertContains(r, 'no puede ser negativa')

    def test_el_actor_sin_fecha_de_nacimiento_no_aparece_al_filtrar_por_edad(self):
        sin_fecha = self.crear('sin@simgest.com', 'Sin Filtro', 30, 'Otro', [])
        Actor.objects.filter(pk=sin_fecha.pk).update(fecha_nacimiento=None)
        r = self.client.get(self.url, {'edad_min': 0, 'edad_max': 120})
        self.assertNotIn('Sin Filtro', self.nombres(r))

    def test_solo_el_administrador_filtra(self):
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get(self.url, {'genero': 'Femenino'}).status_code, 200)


class HU38HistorialTests(BaseActores):

    def url_historial(self, actor):
        return reverse('simulactores:historial_actor', args=[actor.pk])

    def asignar(self, actor, estado='Confirmada', dias=-5, hora=9):
        fecha = timezone.localdate() + datetime.timedelta(days=dias)
        solicitud = self.crear_solicitud(estado='Completada', fecha=fecha, hora=hora)
        return Asignacion.objects.create(solicitud=solicitud, actor=actor, estado=estado)

    def test_historial_con_registros_muestra_simulaciones_fechas_y_estados(self):
        a1 = self.asignar(self.ana, 'Ejecutada', dias=-10)
        a2 = self.asignar(self.ana, 'Rechazada', dias=-3, hora=11)
        a2.motivo_rechazo = 'No puedo ese día'
        a2.save()
        r = self.client.get(self.url_historial(self.ana))
        self.assertContains(r, a1.solicitud.numero_solicitud)
        self.assertContains(r, a2.solicitud.numero_solicitud)
        self.assertContains(r, a1.solicitud.fecha_evento.strftime('%d/%m/%Y'))
        self.assertContains(r, 'Ejecutada')
        self.assertContains(r, 'Rechazada')
        self.assertContains(r, 'No puedo ese día')

    def test_actor_sin_historial_muestra_mensaje(self):
        r = self.client.get(self.url_historial(self.bruno))
        self.assertContains(r, 'no registra asignaciones anteriores')

    def test_el_resumen_cuenta_por_estado(self):
        self.asignar(self.ana, 'Ejecutada', dias=-9)
        self.asignar(self.ana, 'Ejecutada', dias=-8)
        self.asignar(self.ana, 'Cancelada', dias=-7)
        r = self.client.get(self.url_historial(self.ana))
        self.assertEqual(r.context['resumen']['total'], 3)
        self.assertEqual(r.context['resumen']['ejecutadas'], 2)
        self.assertEqual(r.context['resumen']['canceladas'], 1)

    def test_solo_se_ven_las_asignaciones_de_ese_actor(self):
        propia = self.asignar(self.ana, 'Confirmada', dias=-4)
        ajena = self.asignar(self.bruno, 'Confirmada', dias=-3, hora=13)
        r = self.client.get(self.url_historial(self.ana))
        self.assertContains(r, propia.solicitud.numero_solicitud)
        self.assertNotContains(r, ajena.solicitud.numero_solicitud)

    def test_filtra_por_estado(self):
        ok = self.asignar(self.ana, 'Ejecutada', dias=-9)
        otra = self.asignar(self.ana, 'Cancelada', dias=-8, hora=12)
        r = self.client.get(self.url_historial(self.ana), {'estado': 'Cancelada'})
        self.assertContains(r, otra.solicitud.numero_solicitud)
        self.assertNotContains(r, ok.solicitud.numero_solicitud)

    def test_un_estado_invalido_se_ignora(self):
        self.asignar(self.ana, 'Ejecutada', dias=-9)
        r = self.client.get(self.url_historial(self.ana), {'estado': 'Inventado'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['pagina'].paginator.count, 1)

    def test_el_orden_es_del_mas_reciente_al_mas_antiguo(self):
        vieja = self.asignar(self.ana, 'Ejecutada', dias=-20)
        nueva = self.asignar(self.ana, 'Ejecutada', dias=-2, hora=14)
        r = self.client.get(self.url_historial(self.ana))
        ids = [a.pk for a in r.context['pagina']]
        self.assertEqual(ids, [nueva.pk, vieja.pk])

    def test_pagina_de_10_en_10(self):
        for i in range(12):
            self.asignar(self.ana, 'Ejecutada', dias=-30 + i, hora=(i % 12) + 6)
        r = self.client.get(self.url_historial(self.ana))
        self.assertEqual(len(r.context['pagina']), 10)
        self.assertTrue(r.context['pagina'].has_next())

    def test_la_lista_de_actores_enlaza_al_historial(self):
        r = self.client.get(reverse('simulactores:actores_admin'))
        self.assertContains(r, self.url_historial(self.ana))

    def test_actor_inexistente_da_404(self):
        r = self.client.get(reverse('simulactores:historial_actor', args=[999999]))
        self.assertEqual(r.status_code, 404)

    def test_el_actor_no_ve_el_historial_de_otros(self):
        self.client.force_login(self.ana.usuario)
        self.assertNotEqual(self.client.get(self.url_historial(self.bruno)).status_code, 200)