
from django.urls import reverse

from .models import MATRIZ_PERMISOS, Rol, Usuario
from .tests import BaseSprint2


class ContadorTests(BaseSprint2):

    def setUp(self):
        super().setUp()
        rol, _ = Rol.objects.get_or_create(nombre='Contador')
        self.contador = Usuario.objects.create_user(
            email='contador@simgest.com', password='Conta123!',
            nombre='Contador Prueba', rol=rol, estado='Activo')
        self.client.force_login(self.contador)
        self.solicitud = self.crear_solicitud(estado='Aprobada', escenario=self.escenario)

    def url(self, nombre, *args):
        return reverse(f'simulactores:{nombre}', args=args)

    def test_el_rol_existe_tras_migrar(self):
        self.assertTrue(Rol.objects.filter(nombre='Contador').exists())

    def test_al_entrar_va_a_pagos(self):
        r = self.client.get(self.url('home'))
        self.assertRedirects(r, self.url('pagos_admin'))

    def test_ve_pagos_y_reporte_mensual(self):
        self.assertEqual(self.client.get(self.url('pagos_admin')).status_code, 200)
        self.assertEqual(self.client.get(self.url('reporte_mensual_actores')).status_code, 200)

    def test_el_menu_solo_trae_lo_permitido(self):
        r = self.client.get(self.url('pagos_admin'))
        etiquetas = {i['etiqueta'] for i in r.context['menu_lateral']}
        self.assertEqual(etiquetas, {'Pagos a actores', 'Reporte mensual', 'Notificaciones', 'Mi perfil'})

    def test_urls_no_permitidas_muestran_acceso_restringido(self):
        urls = [
            self.url('dashboard_administrador'), self.url('listado_usuarios'),
            self.url('solicitudes_admin'), self.url('solicitud_admin_detalle', self.solicitud.uuid),
            self.url('asignar_actor', self.solicitud.uuid), self.url('reasignar_actor', self.solicitud.uuid),
            self.url('actores_admin'), self.url('consulta_disponibilidad'),
            self.url('bitacora_actividad'), self.url('biblioteca_escenarios'),
            self.url('tarifas_modalidad'),
        ]
        for u in urls:
            r = self.client.get(u)
            self.assertEqual(r.status_code, 403, u)
            self.assertContains(r, 'Acceso restringido', status_code=403)

    def test_no_puede_asignar_ni_cambiar_roles_ni_tarifas_por_post(self):
        self.assertEqual(self.client.post(self.url('asignar_actor', self.solicitud.uuid), {'actor': 1}).status_code, 403)
        self.assertEqual(self.client.post(self.url('actualizar_rol', self.admin.pk),
                                          {'id_rol': self.contador.rol_id, 'estado': 'Activo'}).status_code, 403)
        self.assertEqual(self.client.post(self.url('tarifas_modalidad'),
                                          {'virtual': '1', 'presencial': '1'}).status_code, 403)

    def test_el_administrador_sigue_con_todo(self):
        self.client.force_login(self.admin)
        for nombre in ('tarifas_modalidad', 'pagos_admin', 'listado_usuarios', 'actores_admin'):
            self.assertEqual(self.client.get(self.url(nombre)).status_code, 200, nombre)
        self.assertIn('tarifas_modalidad', MATRIZ_PERMISOS['Administrador'])

    def test_el_administrador_puede_asignar_el_rol_contador(self):
        self.client.force_login(self.admin)
        r = self.client.get(self.url('listado_usuarios'))
        self.assertContains(r, 'Contador')
