"""Cierre de sesión por inactividad para todos los roles."""
import time

from django.test import override_settings
from django.urls import reverse

from .middleware import CLAVE_ULTIMA_ACTIVIDAD, MENSAJE_INACTIVIDAD
from .models import Actor, Rol, Usuario
from .tests import BaseSprint2


@override_settings(INACTIVITY_TIMEOUT_MINUTES=30)
class InactividadTests(BaseSprint2):

    def usuarios(self):
        rol, _ = Rol.objects.get_or_create(nombre='Actor')
        actor = Usuario.objects.create_user(
            email='a@simgest.com', password='Actor123!', nombre='Actor A', rol=rol, estado='Activo')
        Actor.objects.create(usuario=actor)
        rol_c, _ = Rol.objects.get_or_create(nombre='Contador')
        contador = Usuario.objects.create_user(
            email='c@simgest.com', password='Conta123!', nombre='Conta', rol=rol_c, estado='Activo')
        return [self.admin, self.cliente, actor, contador]

    def envejecer(self, minutos):
        s = self.client.session
        s[CLAVE_ULTIMA_ACTIVIDAD] = time.time() - minutos * 60
        s.save()

    def test_con_actividad_reciente_la_sesion_sigue(self):
        for u in self.usuarios():
            self.client.force_login(u)
            self.client.get(reverse('simulactores:home'))
            self.envejecer(29)
            r = self.client.get(reverse('simulactores:perfil'))
            self.assertEqual(r.status_code, 200, u.email)

    def test_pasado_el_limite_cierra_sesion_avisa_y_manda_al_login(self):
        for u in self.usuarios():
            self.client.force_login(u)
            self.client.get(reverse('simulactores:home'))
            self.envejecer(31)
            r = self.client.get(reverse('simulactores:perfil'), follow=True)
            self.assertRedirects(r, reverse('simulactores:login'))
            self.assertContains(r, MENSAJE_INACTIVIDAD)
            self.assertNotIn('_auth_user_id', self.client.session, u.email)

    def test_cada_solicitud_renueva_el_tiempo(self):
        self.client.force_login(self.cliente)
        self.client.get(reverse('simulactores:home'))
        self.envejecer(20)
        self.client.get(reverse('simulactores:perfil'))
        self.envejecer(20)
        self.assertEqual(self.client.get(reverse('simulactores:perfil')).status_code, 200)

    def test_el_login_no_muestra_aviso_si_no_hubo_sesion(self):
        r = self.client.get(reverse('simulactores:login'))
        self.assertNotContains(r, MENSAJE_INACTIVIDAD)

    def test_se_puede_volver_a_entrar_despues(self):
        self.client.force_login(self.cliente)
        self.client.get(reverse('simulactores:home'))
        self.envejecer(45)
        self.client.get(reverse('simulactores:perfil'))
        r = self.client.post(reverse('simulactores:login'),
                             {'email': self.cliente.email, 'password': 'Cliente123!'})
        self.assertEqual(r.status_code, 302)
