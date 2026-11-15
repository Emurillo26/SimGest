"""
Pruebas del modo oscuro.

Cómo correrlas:  python manage.py test simulactores.tests_tema
"""
import glob
import os

from django.conf import settings
from django.urls import reverse

from .tests import BaseSprint2

PLANTILLAS = os.path.join(settings.BASE_DIR, 'simulactores', 'templates', 'simulactores')


class ModoOscuroTests(BaseSprint2):

    def test_paginas_cargan_el_tema_y_el_boton(self):
        r = self.client.get(reverse('simulactores:dashboard_administrador'))
        self.assertContains(r, 'css/tema-oscuro.css')
        self.assertContains(r, 'js/tema.js')
        self.assertContains(r, 'class="boton-tema"')

    def test_inicio_de_sesion_carga_el_tema(self):
        self.client.logout()
        r = self.client.get(reverse('simulactores:login'))
        self.assertContains(r, 'css/tema-oscuro.css')
        self.assertContains(r, "localStorage.getItem('simgest-tema')")

    def test_todas_las_paginas_completas_incluyen_el_tema(self):
        faltan = []
        for ruta in glob.glob(os.path.join(PLANTILLAS, '*.html')):
            with open(ruta, encoding='utf8') as f:
                html = f.read()
            if '</head>' in html and "_tema.html" not in html:
                faltan.append(os.path.basename(ruta))
        self.assertEqual(faltan, [], 'Agrega {% include "simulactores/_tema.html" %} antes de </head>')
