"""
Pruebas de la foto de perfil.

Cómo correrlas:  python manage.py test simulactores.tests_foto_perfil
"""
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from .models import Bitacora
from .tests import BaseSprint2

MEDIA_TEMPORAL = tempfile.mkdtemp()


def imagen(formato='JPEG', tamano=(800, 600), nombre='foto.jpg', modo='RGB'):
    datos = BytesIO()
    Image.new(modo, tamano, (120, 40, 50, 255)[:len(modo)]).save(datos, format=formato)
    tipo = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif'}[formato]
    return SimpleUploadedFile(nombre, datos.getvalue(), content_type=tipo)


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class FotoPerfilTests(BaseSprint2):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def subir(self, archivo):
        return self.client.post(reverse('simulactores:subir_foto_perfil'), {'foto': archivo}, follow=True)

    def test_subir_foto_la_guarda_cuadrada_y_la_muestra(self):
        r = self.subir(imagen())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.foto)
        with Image.open(self.admin.foto.path) as guardada:
            self.assertEqual(guardada.size, (400, 400))
            self.assertEqual(guardada.format, 'JPEG')
        self.assertContains(r, 'Tu foto de perfil se actualizó.')
        self.assertContains(r, self.admin.foto.url)  # en el perfil y en la barra lateral
        self.assertTrue(Bitacora.objects.filter(usuario=self.admin, accion='Foto de perfil actualizada').exists())

    def test_png_con_transparencia_se_acepta(self):
        self.subir(imagen('PNG', nombre='foto.png', modo='RGBA'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.foto)

    def test_cambiar_foto_borra_la_anterior(self):
        self.subir(imagen())
        self.admin.refresh_from_db()
        anterior = self.admin.foto.path
        self.subir(imagen(nombre='otra.jpg'))
        self.admin.refresh_from_db()
        self.assertNotEqual(self.admin.foto.path, anterior)
        self.assertFalse(self.admin.foto.storage.exists(anterior))

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        falso = SimpleUploadedFile('virus.jpg', b'esto no es una imagen', content_type='image/jpeg')
        r = self.subir(falso)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.foto)
        self.assertContains(r, 'alert-danger')

    def test_formato_no_permitido_se_rechaza(self):
        r = self.subir(imagen('GIF', nombre='foto.gif'))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.foto)
        self.assertContains(r, 'Usa una imagen JPG, PNG o WEBP.')

    def test_quitar_foto(self):
        self.subir(imagen())
        self.admin.refresh_from_db()
        ruta = self.admin.foto.path
        r = self.client.post(reverse('simulactores:quitar_foto_perfil'), follow=True)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.foto)
        self.assertFalse(self.admin.foto.storage.exists(ruta))
        self.assertContains(r, 'Quitaste tu foto de perfil.')

    def test_sin_foto_se_ve_la_inicial(self):
        r = self.client.get(reverse('simulactores:perfil'))
        self.assertContains(r, 'Subir foto')
        self.assertNotContains(r, 'fotos_perfil/')

    def test_solo_por_post_y_con_sesion(self):
        self.assertEqual(self.client.get(reverse('simulactores:subir_foto_perfil')).status_code, 405)
        self.client.logout()
        r = self.client.post(reverse('simulactores:subir_foto_perfil'), {'foto': imagen()})
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('simulactores:login'), r.url)
