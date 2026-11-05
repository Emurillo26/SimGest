"""
Pruebas automáticas de HU-27 (calendario de simulaciones del actor).

Cómo correrlas:  python manage.py test simulactores.tests_calendario
"""
import datetime

from django.urls import reverse

from .models import Actor, Asignacion, Rol, Usuario
from .tests import BaseSprint2

NOVIEMBRE = datetime.date(2026, 11, 5)


class BaseCalendario(BaseSprint2):

    def setUp(self):
        super().setUp()
        self.rol_actor, _ = Rol.objects.get_or_create(nombre='Actor')
        self.actor = self.crear_actor('actor.cal@simgest.com', 'Actor Calendario')
        self.client.force_login(self.actor.usuario)

    def crear_actor(self, email, nombre):
        usuario = Usuario.objects.create_user(
            email=email, password='Actor123!', nombre=nombre,
            rol=self.rol_actor, estado='Activo')
        return Actor.objects.create(usuario=usuario)

    def asignar(self, actor=None, estado='Confirmada', fecha=NOVIEMBRE, hora=9,
                estado_solicitud='Confirmada'):
        solicitud = self.crear_solicitud(
            estado=estado_solicitud, fecha=fecha, hora=hora, escenario=self.escenario)
        asignacion = Asignacion.objects.create(
            solicitud=solicitud, actor=actor or self.actor, estado=estado)
        return asignacion

    def url(self, mes=None):
        base = reverse('simulactores:calendario_actor')
        return f'{base}?mes={mes}' if mes else base

    def celda(self, respuesta, fecha):
        for semana in respuesta.context['semanas']:
            for dia in semana:
                if dia['fecha'] == fecha:
                    return dia
        return None


class HU27VisualizacionTests(BaseCalendario):

    def test_muestra_el_evento_en_su_fecha_con_hora_y_estado(self):
        self.asignar(estado='Confirmada', hora=9)
        r = self.client.get(self.url('2026-11'))
        self.assertEqual(r.status_code, 200)
        celda = self.celda(r, NOVIEMBRE)
        self.assertEqual(len(celda['eventos']), 1)
        self.assertContains(r, '09:00 - 10:00')
        self.assertContains(r, 'Confirmada')

    def test_estado_pendiente_se_muestra_como_pendiente_de_confirmacion(self):
        self.asignar(estado='Pendiente', estado_solicitud='Actor Asignado')
        r = self.client.get(self.url('2026-11'))
        self.assertContains(r, 'Pendiente de confirmación')

    def test_varios_eventos_el_mismo_dia_van_ordenados_por_hora(self):
        self.asignar(hora=14)
        self.asignar(hora=8)
        r = self.client.get(self.url('2026-11'))
        horas = [e.solicitud.hora_inicio.hour for e in self.celda(r, NOVIEMBRE)['eventos']]
        self.assertEqual(horas, [8, 14])

    def test_solo_muestra_las_simulaciones_del_actor_autenticado(self):
        otro = self.crear_actor('otro.cal@simgest.com', 'Otro Actor')
        self.asignar(actor=otro)
        r = self.client.get(self.url('2026-11'))
        self.assertEqual(self.celda(r, NOVIEMBRE)['eventos'], [])
        self.assertContains(r, 'No tienes simulaciones asignadas en Noviembre 2026')

    def test_no_muestra_asignaciones_rechazadas_ni_solicitudes_canceladas(self):
        self.asignar(estado='Rechazada', hora=8, estado_solicitud='Aprobada')
        self.asignar(estado='Confirmada', hora=10, estado_solicitud='Cancelada')
        r = self.client.get(self.url('2026-11'))
        self.assertEqual(self.celda(r, NOVIEMBRE)['eventos'], [])

    def test_total_del_mes_no_cuenta_dias_vecinos_de_la_cuadricula(self):
        # 28/oct aparece en la primera semana de la cuadrícula de noviembre
        self.asignar(fecha=datetime.date(2026, 10, 28))
        self.asignar(fecha=NOVIEMBRE)
        r = self.client.get(self.url('2026-11'))
        self.assertEqual(r.context['total_mes'], 1)

    def test_mes_sin_simulaciones_muestra_mensaje(self):
        r = self.client.get(self.url('2026-11'))
        self.assertContains(r, 'No tienes simulaciones asignadas en Noviembre 2026')


class HU27CambioDePeriodoTests(BaseCalendario):

    def test_mes_siguiente_actualiza_el_calendario(self):
        self.asignar(fecha=NOVIEMBRE)
        self.asignar(fecha=datetime.date(2026, 12, 10), hora=11)
        r = self.client.get(self.url('2026-12'))
        self.assertContains(r, 'Diciembre 2026')
        self.assertEqual(r.context['total_mes'], 1)
        self.assertContains(r, '11:00 - 12:00')
        self.assertNotContains(r, '09:00 - 10:00')

    def test_mes_anterior_actualiza_el_calendario(self):
        self.asignar(fecha=datetime.date(2026, 10, 15), hora=13)
        r = self.client.get(self.url('2026-10'))
        self.assertContains(r, 'Octubre 2026')
        self.assertContains(r, '13:00 - 14:00')

    def test_enlaces_de_navegacion_cruzan_el_cambio_de_anio(self):
        r = self.client.get(self.url('2026-01'))
        self.assertEqual(r.context['mes_anterior'], '2025-12')
        self.assertEqual(r.context['mes_siguiente'], '2026-02')
        r = self.client.get(self.url('2026-12'))
        self.assertEqual(r.context['mes_siguiente'], '2027-01')

    def test_la_pagina_trae_los_botones_de_mes_anterior_y_siguiente(self):
        r = self.client.get(self.url('2026-11'))
        self.assertContains(r, '?mes=2026-10')
        self.assertContains(r, '?mes=2026-12')

    def test_mes_invalido_vuelve_al_mes_actual_sin_error(self):
        for valor in ['abc', '2026-13', '2026-00', '1800-05', '2026', '']:
            r = self.client.get(self.url(valor))
            self.assertEqual(r.status_code, 200, valor)
            self.assertTrue(r.context['es_mes_actual'], valor)


class HU27SeleccionDeSimulacionTests(BaseCalendario):

    def test_el_evento_enlaza_al_detalle_de_la_simulacion(self):
        asignacion = self.asignar()
        r = self.client.get(self.url('2026-11'))
        detalle = reverse('simulactores:detalle_simulacion_actor', args=[asignacion.solicitud.uuid])
        self.assertContains(r, f'href="{detalle}"')

    def test_el_enlace_del_evento_abre_el_detalle_sin_error(self):
        asignacion = self.asignar()
        detalle = reverse('simulactores:detalle_simulacion_actor', args=[asignacion.solicitud.uuid])
        r = self.client.get(detalle)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, asignacion.solicitud.numero_solicitud)


class HU27AccesoTests(BaseCalendario):

    def test_usuario_sin_sesion_va_al_login(self):
        self.client.logout()
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('simulactores:login'), r.url)

    def test_cliente_no_puede_ver_el_calendario_del_actor(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_administrador_no_puede_ver_el_calendario_del_actor(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_usuario_actor_sin_perfil_ve_aviso(self):
        sin_perfil = Usuario.objects.create_user(
            email='sinperfil@simgest.com', password='Actor123!', nombre='Sin Perfil',
            rol=self.rol_actor, estado='Activo')
        self.client.force_login(sin_perfil)
        r = self.client.get(self.url('2026-11'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Todavía no tienes un perfil de Actor completo')

    def test_el_menu_del_actor_incluye_mi_calendario(self):
        r = self.client.get(self.url('2026-11'))
        self.assertContains(r, 'Mi calendario')


# ----------------------------------------------------------------------
# HU-36 - Registro de disponibilidad del actor
# ----------------------------------------------------------------------

from django.utils import timezone  # noqa: E402

from .models import Disponibilidad  # noqa: E402


class HU36RegistroDisponibilidadTests(BaseCalendario):

    def setUp(self):
        super().setUp()
        self.fecha = timezone.localdate() + datetime.timedelta(days=10)
        self.url_disp = reverse('simulactores:mi_disponibilidad')

    def datos(self, tipo='Disponible', inicio='08:00', fin='12:00'):
        return {'fecha': self.fecha.isoformat(), 'hora_inicio': inicio,
                'hora_fin': fin, 'tipo_bloque': tipo}

    def test_registro_exitoso_guarda_el_bloque_y_lo_muestra_en_el_calendario(self):
        r = self.client.post(self.url_disp, self.datos())
        self.assertRedirects(r, self.url_disp)
        bloque = Disponibilidad.objects.get(actor=self.actor)
        self.assertEqual(bloque.tipo_bloque, 'Disponible')
        self.assertEqual(bloque.fecha, self.fecha)

        mes = f'{self.fecha.year:04d}-{self.fecha.month:02d}'
        r = self.client.get(self.url(mes))
        celda = self.celda(r, self.fecha)
        self.assertEqual(len(celda['bloques']), 1)
        self.assertContains(r, '08:00 - 12:00')
        self.assertContains(r, 'Disponible')

    def test_mensaje_de_exito_al_guardar_disponibilidad(self):
        r = self.client.post(self.url_disp, self.datos(), follow=True)
        self.assertContains(r, 'Disponibilidad guardada.')

    def test_un_bloqueo_tambien_aparece_en_el_calendario(self):
        self.client.post(self.url_disp, self.datos(tipo='Bloqueado'))
        mes = f'{self.fecha.year:04d}-{self.fecha.month:02d}'
        r = self.client.get(self.url(mes))
        self.assertContains(r, 'Bloqueado')
        self.assertEqual(self.celda(r, self.fecha)['bloques'][0].tipo_bloque, 'Bloqueado')

    def test_el_calendario_solo_muestra_los_bloques_del_actor_autenticado(self):
        otro = self.crear_actor('otro.disp@simgest.com', 'Otro Actor')
        Disponibilidad.objects.create(
            actor=otro, fecha=self.fecha, hora_inicio=datetime.time(8),
            hora_fin=datetime.time(12), tipo_bloque='Disponible')
        mes = f'{self.fecha.year:04d}-{self.fecha.month:02d}'
        r = self.client.get(self.url(mes))
        self.assertEqual(self.celda(r, self.fecha)['bloques'], [])

    def test_horario_invalido_no_se_guarda(self):
        r = self.client.post(self.url_disp, self.datos(inicio='12:00', fin='08:00'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'La hora final debe ser posterior')
        self.assertFalse(Disponibilidad.objects.exists())

    def test_el_mas_del_calendario_precarga_la_fecha_en_el_formulario(self):
        r = self.client.get(f'{self.url_disp}?fecha={self.fecha.isoformat()}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'value="{self.fecha.isoformat()}"')

    def test_fecha_invalida_en_la_url_no_rompe_el_formulario(self):
        r = self.client.get(f'{self.url_disp}?fecha=hola')
        self.assertEqual(r.status_code, 200)

    def test_el_calendario_ofrece_registrar_disponibilidad_en_dias_futuros(self):
        mes = f'{self.fecha.year:04d}-{self.fecha.month:02d}'
        r = self.client.get(self.url(mes))
        self.assertContains(r, f'?fecha={self.fecha.isoformat()}')


class HU36CorreoDuplicadoTests(BaseSprint2):
    """Validación heredada del registro: correo ya existente."""

    url = reverse('simulactores:registro')

    def datos(self, email):
        return {'nombre': 'Persona Nueva', 'email': email, 'telefono': '',
                'password': 'ClaveSegura123!', 'password2': 'ClaveSegura123!'}

    def test_correo_ya_existente_muestra_mensaje_de_error(self):
        r = self.client.post(self.url, self.datos(self.cliente.email))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Este correo ya está en uso.')

    def test_correo_existente_con_mayusculas_tambien_se_rechaza(self):
        r = self.client.post(self.url, self.datos(self.cliente.email.upper()))
        self.assertContains(r, 'Este correo ya está en uso.')

    def test_correo_duplicado_no_crea_otro_usuario(self):
        total = Usuario.objects.count()
        self.client.post(self.url, self.datos(self.cliente.email))
        self.assertEqual(Usuario.objects.count(), total)
