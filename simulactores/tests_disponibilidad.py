"""
Pruebas de #37 (bloquear fechas), #40 (editar o eliminar bloques) y #38 (consulta del admin).

Cómo correrlas:  python manage.py test simulactores.tests_disponibilidad
"""
import datetime

from django.urls import reverse
from django.utils import timezone

from . import asignacion_service as servicio
from .models import Actor, Asignacion, Disponibilidad, Rol, Usuario
from .tests import BaseSprint2


class BaseDisponibilidad(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.usuario_actor = Usuario.objects.create_user(
            email='actor.disp@simgest.com', password='Actor123!',
            nombre='Actor Disp', rol=rol_actor, estado='Activo')
        self.actor = Actor.objects.create(usuario=self.usuario_actor)
        self.fecha = timezone.localdate() + datetime.timedelta(days=10)
        self.client.force_login(self.usuario_actor)

    def bloque(self, inicio=8, fin=18, tipo='Disponible', actor=None):
        return Disponibilidad.objects.create(
            actor=actor or self.actor, fecha=self.fecha,
            hora_inicio=datetime.time(inicio), hora_fin=datetime.time(fin), tipo_bloque=tipo)

    def simulacion_asignada(self, hora=9, estado='Confirmada'):
        solicitud = self.crear_solicitud(estado='Confirmada', fecha=self.fecha, hora=hora)
        return Asignacion.objects.create(solicitud=solicitud, actor=self.actor, estado=estado)

    def datos(self, inicio='09:00', fin='12:00', tipo='Bloqueado'):
        return {'fecha': self.fecha.isoformat(), 'hora_inicio': inicio,
                'hora_fin': fin, 'tipo_bloque': tipo}


class Item37BloquearFechaTests(BaseDisponibilidad):

    url = reverse('simulactores:mi_disponibilidad')

    def test_bloqueo_exitoso_excluye_al_actor_de_asignaciones(self):
        self.bloque()
        respuesta = self.client.post(self.url, self.datos(tipo='Bloqueado'))
        self.assertRedirects(respuesta, self.url)
        self.assertTrue(Disponibilidad.objects.filter(actor=self.actor, tipo_bloque='Bloqueado').exists())

        solicitud = self.crear_solicitud(estado='Aprobada', fecha=self.fecha, hora=10)
        veredicto = servicio.validar_disponibilidad(self.actor, solicitud)
        self.assertFalse(veredicto.disponible)

    def test_no_se_puede_bloquear_con_simulacion_asignada(self):
        asignacion = self.simulacion_asignada(hora=10)
        respuesta = self.client.post(self.url, self.datos(tipo='Bloqueado'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, asignacion.solicitud.numero_solicitud)
        self.assertContains(respuesta, 'gestionar primero su cancelación')
        self.assertFalse(Disponibilidad.objects.filter(tipo_bloque='Bloqueado').exists())

    def test_no_se_aceptan_fechas_pasadas(self):
        datos = self.datos()
        datos['fecha'] = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        self.client.post(self.url, datos)
        self.assertFalse(Disponibilidad.objects.exists())

    def test_no_se_aceptan_bloques_que_se_cruzan(self):
        self.bloque(inicio=8, fin=10)
        respuesta = self.client.post(self.url, self.datos(inicio='09:00', fin='11:00', tipo='Disponible'))
        self.assertContains(respuesta, 'se cruza')
        self.assertEqual(Disponibilidad.objects.count(), 1)

    def test_otros_roles_no_entran(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class Item40EditarEliminarBloqueTests(BaseDisponibilidad):

    def url_editar(self, bloque):
        return reverse('simulactores:editar_disponibilidad', args=[bloque.pk])

    def url_eliminar(self, bloque):
        return reverse('simulactores:eliminar_disponibilidad', args=[bloque.pk])

    def test_edicion_exitosa_de_bloque_sin_simulaciones(self):
        bloque = self.bloque()
        self.client.post(self.url_editar(bloque), self.datos(inicio='13:00', fin='17:00', tipo='Disponible'))
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, datetime.time(13))
        self.assertEqual(bloque.hora_fin, datetime.time(17))

    def test_no_se_edita_bloque_con_simulacion(self):
        bloque = self.bloque()
        self.simulacion_asignada(hora=9)
        respuesta = self.client.post(self.url_editar(bloque), self.datos(inicio='13:00', fin='17:00'), follow=True)
        self.assertContains(respuesta, 'gestionar esa simulación primero')
        bloque.refresh_from_db()
        self.assertEqual(bloque.hora_inicio, datetime.time(8))

    def test_eliminacion_bloqueada_si_hay_simulacion(self):
        bloque = self.bloque()
        self.simulacion_asignada(hora=9, estado='Pendiente')
        respuesta = self.client.post(self.url_eliminar(bloque), follow=True)
        self.assertContains(respuesta, 'gestionar esa simulación primero')
        self.assertTrue(Disponibilidad.objects.filter(pk=bloque.pk).exists())

    def test_eliminacion_exitosa_sin_simulaciones(self):
        bloque = self.bloque()
        self.client.post(self.url_eliminar(bloque))
        self.assertFalse(Disponibilidad.objects.filter(pk=bloque.pk).exists())

    def test_simulacion_cancelada_no_impide_eliminar(self):
        bloque = self.bloque()
        self.simulacion_asignada(hora=9, estado='Cancelada')
        self.client.post(self.url_eliminar(bloque))
        self.assertFalse(Disponibilidad.objects.filter(pk=bloque.pk).exists())

    def test_no_se_tocan_bloques_de_otro_actor(self):
        rol_actor = Rol.objects.get(nombre='Actor')
        otro_usuario = Usuario.objects.create_user(
            email='otro.actor@simgest.com', password='Actor123!',
            nombre='Otro Actor', rol=rol_actor, estado='Activo')
        ajeno = self.bloque(actor=Actor.objects.create(usuario=otro_usuario))

        self.assertEqual(self.client.get(self.url_editar(ajeno)).status_code, 404)
        self.assertEqual(self.client.post(self.url_eliminar(ajeno)).status_code, 404)
        self.assertTrue(Disponibilidad.objects.filter(pk=ajeno.pk).exists())


class Item38ConsultaDisponibilidadTests(BaseDisponibilidad):

    url = reverse('simulactores:consulta_disponibilidad')

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def consultar(self, inicio='', fin=''):
        return self.client.get(self.url, {'fecha': self.fecha.isoformat(),
                                          'hora_inicio': inicio, 'hora_fin': fin})

    def test_consulta_exitosa_muestra_actores_disponibles(self):
        self.bloque(inicio=8, fin=12)
        respuesta = self.consultar('09:00', '11:00')
        self.assertContains(respuesta, 'Actor Disp')
        self.assertNotContains(respuesta, 'No hay actores disponibles para esta fecha')

    def test_sin_actores_disponibles_muestra_mensaje(self):
        respuesta = self.consultar()
        self.assertContains(respuesta, 'No hay actores disponibles para esta fecha')

    def test_horario_fuera_del_bloque_no_aparece(self):
        self.bloque(inicio=8, fin=12)
        respuesta = self.consultar('11:00', '13:00')
        self.assertContains(respuesta, 'No hay actores disponibles para esta fecha')

    def test_actor_con_bloqueo_o_simulacion_no_aparece_en_ese_horario(self):
        self.bloque(inicio=8, fin=18)
        self.bloque(inicio=14, fin=16, tipo='Bloqueado')
        self.simulacion_asignada(hora=9)
        self.assertContains(self.consultar('09:00', '10:00'), 'No hay actores disponibles')
        self.assertContains(self.consultar('14:00', '15:00'), 'No hay actores disponibles')
        self.assertContains(self.consultar('11:00', '12:00'), 'Actor Disp')

    def test_sin_horario_muestra_compromisos_del_dia(self):
        self.bloque(inicio=8, fin=18)
        asignacion = self.simulacion_asignada(hora=9)
        respuesta = self.consultar()
        self.assertContains(respuesta, 'Actor Disp')
        self.assertContains(respuesta, asignacion.solicitud.numero_solicitud)

    def test_actor_inactivo_no_aparece(self):
        self.bloque(inicio=8, fin=12)
        self.actor.estado = 'Inactivo'
        self.actor.save()
        self.assertContains(self.consultar(), 'No hay actores disponibles')

    def test_solo_el_administrador_entra(self):
        self.client.force_login(self.usuario_actor)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class SinBloquesEncimadosTests(BaseDisponibilidad):
    """Un mismo horario nunca puede ser Disponible y Bloqueado a la vez."""

    url = reverse('simulactores:mi_disponibilidad')

    def horarios(self, tipo):
        return sorted(
            (b.hora_inicio.hour, b.hora_fin.hour)
            for b in Disponibilidad.objects.filter(actor=self.actor, tipo_bloque=tipo)
        )

    def test_bloqueo_en_medio_parte_la_disponibilidad_en_dos(self):
        self.bloque(inicio=8, fin=18)
        self.client.post(self.url, self.datos(inicio='10:00', fin='12:00'))
        self.assertEqual(self.horarios('Disponible'), [(8, 10), (12, 18)])
        self.assertEqual(self.horarios('Bloqueado'), [(10, 12)])

    def test_bloqueo_al_inicio_acorta_la_disponibilidad(self):
        self.bloque(inicio=8, fin=18)
        self.client.post(self.url, self.datos(inicio='07:00', fin='10:00'))
        self.assertEqual(self.horarios('Disponible'), [(10, 18)])

    def test_bloqueo_al_final_acorta_la_disponibilidad(self):
        self.bloque(inicio=8, fin=18)
        self.client.post(self.url, self.datos(inicio='16:00', fin='20:00'))
        self.assertEqual(self.horarios('Disponible'), [(8, 16)])

    def test_bloqueo_total_elimina_la_disponibilidad(self):
        self.bloque(inicio=9, fin=12)
        self.client.post(self.url, self.datos(inicio='08:00', fin='13:00'))
        self.assertEqual(self.horarios('Disponible'), [])
        self.assertEqual(self.horarios('Bloqueado'), [(8, 13)])

    def test_el_mensaje_avisa_que_se_ajusto_la_disponibilidad(self):
        self.bloque(inicio=8, fin=18)
        respuesta = self.client.post(self.url, self.datos(inicio='10:00', fin='12:00'), follow=True)
        self.assertContains(respuesta, 'se ajustó')

    def test_no_se_registra_disponibilidad_sobre_un_bloqueo(self):
        self.bloque(inicio=10, fin=12, tipo='Bloqueado')
        respuesta = self.client.post(self.url, self.datos(inicio='09:00', fin='11:00', tipo='Disponible'))
        self.assertContains(respuesta, 'Ese horario está bloqueado')
        self.assertEqual(self.horarios('Disponible'), [])

    def test_al_editar_un_bloque_a_bloqueado_tambien_se_recorta(self):
        self.bloque(inicio=8, fin=18)
        otro = self.bloque(inicio=19, fin=21)
        otro.hora_inicio = datetime.time(10)
        otro.hora_fin = datetime.time(12)
        url = reverse('simulactores:editar_disponibilidad', args=[otro.pk])
        self.client.post(url, self.datos(inicio='10:00', fin='12:00', tipo='Bloqueado'))
        self.assertEqual(self.horarios('Disponible'), [(8, 10), (12, 18)])
        self.assertEqual(self.horarios('Bloqueado'), [(10, 12)])

    def test_nunca_quedan_bloques_de_distinto_tipo_encimados(self):
        self.bloque(inicio=8, fin=18)
        self.client.post(self.url, self.datos(inicio='10:00', fin='12:00'))
        for d in Disponibilidad.objects.filter(tipo_bloque='Disponible'):
            for b in Disponibilidad.objects.filter(tipo_bloque='Bloqueado', fecha=d.fecha):
                self.assertFalse(d.hora_inicio < b.hora_fin and b.hora_inicio < d.hora_fin)

class ConsultaPorRangoTests(BaseDisponibilidad):
    """Consulta del administrador por día, semana o rango de fechas."""

    url = reverse('simulactores:consulta_disponibilidad')

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def bloque_en(self, dias, inicio=8, fin=18, actor=None):
        return Disponibilidad.objects.create(
            actor=actor or self.actor, fecha=self.fecha + datetime.timedelta(days=dias),
            hora_inicio=datetime.time(inicio), hora_fin=datetime.time(fin), tipo_bloque='Disponible')

    def consultar(self, dias_hasta=None, **extra):
        datos = {'fecha': self.fecha.isoformat()}
        if dias_hasta is not None:
            datos['fecha_hasta'] = (self.fecha + datetime.timedelta(days=dias_hasta)).isoformat()
        datos.update(extra)
        return self.client.get(self.url, datos)

    def test_un_rango_agrupa_los_resultados_por_dia(self):
        self.bloque_en(0)
        self.bloque_en(2)
        r = self.consultar(dias_hasta=3)
        self.assertTrue(r.context['es_rango'])
        self.assertEqual(len(r.context['resultados']), 4)
        self.assertEqual(r.context['dias_con_actores'], 2)
        self.assertContains(r, 'Actor Disp')
        self.assertContains(r, '2 de 4 días con actores disponibles')

    def test_los_dias_sin_actores_se_indican(self):
        self.bloque_en(0)
        r = self.consultar(dias_hasta=2)
        self.assertContains(r, 'Sin actores')
        self.assertContains(r, 'No hay actores disponibles para esta fecha')

    def test_si_nadie_esta_disponible_en_todo_el_rango_muestra_el_mensaje(self):
        r = self.consultar(dias_hasta=6)
        self.assertContains(r, 'No hay actores disponibles en ese rango de fechas')

    def test_el_rango_respeta_el_horario(self):
        self.bloque_en(0, 8, 12)
        self.bloque_en(1, 14, 18)
        r = self.consultar(dias_hasta=1, hora_inicio='09:00', hora_fin='11:00')
        self.assertEqual(r.context['dias_con_actores'], 1)

    def test_una_semana_completa_tiene_siete_dias(self):
        r = self.consultar(dias_hasta=6)
        self.assertEqual(len(r.context['resultados']), 7)

    def test_fecha_final_anterior_a_la_inicial_da_error(self):
        r = self.consultar(dias_hasta=-2)
        self.assertContains(r, 'no puede ser anterior')
        self.assertIsNone(r.context['filas'])

    def test_el_rango_maximo_es_de_31_dias(self):
        r = self.consultar(dias_hasta=31)
        self.assertContains(r, 'rango máximo es de 31 días')
        self.assertIsNone(r.context['filas'])
        self.assertEqual(len(self.consultar(dias_hasta=30).context['resultados']), 31)

    def test_sin_fecha_final_funciona_como_antes(self):
        self.bloque_en(0)
        r = self.consultar()
        self.assertFalse(r.context['es_rango'])
        self.assertContains(r, 'Actor Disp')

    def test_misma_fecha_inicial_y_final_es_una_consulta_de_un_dia(self):
        self.bloque_en(0)
        r = self.consultar(dias_hasta=0)
        self.assertFalse(r.context['es_rango'])

    def test_los_atajos_aparecen_y_conservan_el_horario(self):
        r = self.client.get(self.url, {'fecha': self.fecha.isoformat(), 'hora_inicio': '09:00', 'hora_fin': '11:00'})
        atajos = {a['etiqueta']: a['query'] for a in r.context['atajos']}
        self.assertEqual(set(atajos), {'Hoy', 'Mañana', 'Esta semana', 'Próximos 7 días', 'Este mes'})
        self.assertIn('hora_inicio=09%3A00', atajos['Esta semana'])
        self.assertIn('fecha_hasta=', atajos['Próximos 7 días'])
        self.assertContains(r, 'Próximos 7 días')

    def test_el_atajo_de_esta_semana_cubre_de_lunes_a_domingo(self):
        r = self.client.get(self.url)
        semana = next(a['query'] for a in r.context['atajos'] if a['etiqueta'] == 'Esta semana')
        from urllib.parse import parse_qs
        q = parse_qs(semana)
        desde = datetime.date.fromisoformat(q['fecha'][0])
        hasta = datetime.date.fromisoformat(q['fecha_hasta'][0])
        self.assertEqual(desde.weekday(), 0)
        self.assertEqual((hasta - desde).days, 6)

    def test_solo_el_administrador_consulta_rangos(self):
        self.client.force_login(self.usuario_actor)
        self.assertEqual(self.consultar(dias_hasta=3).status_code, 403)