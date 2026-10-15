"""
Carga escenarios reales de la biblioteca a partir de los Excels de programación
de Simulactores (columna PERFIL de cada hoja).

Uso (desde la carpeta del proyecto, con el venv activo):

    python manage.py cargar_escenarios_excel "C:\\ruta\\a\\Información de Simulactores"
    python manage.py cargar_escenarios_excel "C:\\ruta\\..." --minimo 5 --simular

Qué hace:
  * Recorre todos los .xlsx de la carpeta (y subcarpetas).
  * En cada hoja que tenga una columna PERFIL cuenta cuántas veces aparece cada perfil.
  * Crea un escenario por cada perfil que aparezca al menos --minimo veces (por defecto 10).
  * La categoría sale del nombre de la hoja (Medicina, Enfermería, Psicología, ...).
  * Se puede correr varias veces: no duplica lo que ya existe.

Solo usa el nombre del perfil y la cantidad de veces; NO lee datos personales
(intérpretes, teléfonos ni correos), así que es seguro para el repositorio.
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from simulactores.models import Categoria, Escenario, TipoSimulacion

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

GUION_PENDIENTE = (
    'Guion pendiente de redactar. Este escenario se creó a partir del historial de '
    'programación de Simulactores; completa el contexto, el rol del actor y los '
    'objetivos del estudiante.'
)


def _limpiar(texto):
    return re.sub(r'\s+', ' ', str(texto)).strip()


def _categoria_de_hoja(titulo):
    """Devuelve el nombre de categoría según el nombre de la hoja, o None si no aplica."""
    t = _limpiar(titulo)
    if t.lower().startswith('base de datos'):
        return None
    if t.lower().startswith('educaci'):
        return 'Educación'
    return t


class Command(BaseCommand):
    help = 'Crea escenarios en la biblioteca a partir de la columna PERFIL de los Excels de Simulactores.'

    def add_arguments(self, parser):
        parser.add_argument('carpeta', help='Carpeta con los archivos .xlsx')
        parser.add_argument('--minimo', type=int, default=10,
                            help='Veces mínimas que debe aparecer un perfil para crearlo (por defecto 10)')
        parser.add_argument('--simular', action='store_true',
                            help='Solo muestra lo que se crearía, sin guardar nada')

    def handle(self, *args, **opciones):
        if openpyxl is None:
            raise CommandError('Falta openpyxl. Instálalo con: pip install openpyxl')

        carpeta = Path(opciones['carpeta'])
        if not carpeta.is_dir():
            raise CommandError(f'No existe la carpeta: {carpeta}')

        archivos = sorted(p for p in carpeta.rglob('*.xlsx') if not p.name.startswith('~$'))
        if not archivos:
            raise CommandError('No se encontraron archivos .xlsx en esa carpeta.')

        # (categoria, perfil en minúsculas) -> veces; y el nombre "bonito" de cada perfil
        conteo = Counter()
        nombres = {}
        for archivo in archivos:
            try:
                libro = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
            except Exception as error:
                self.stderr.write(f'  Se omitió {archivo.name}: {error}')
                continue
            for hoja in libro.worksheets:
                categoria = _categoria_de_hoja(hoja.title)
                if not categoria:
                    continue
                col_perfil = None
                for fila in hoja.iter_rows(values_only=True):
                    if not fila:
                        continue
                    celdas = [_limpiar(c).upper() if c is not None else '' for c in fila]
                    if 'PERFIL' in celdas and 'FECHA' in celdas:
                        col_perfil = celdas.index('PERFIL')      # fila de encabezado
                        continue
                    if col_perfil is None or col_perfil >= len(fila):
                        continue
                    perfil = fila[col_perfil]
                    if perfil is None or not _limpiar(perfil):
                        continue
                    perfil = _limpiar(perfil)
                    if len(perfil) < 4 or len(perfil) > 150:
                        continue
                    clave = (categoria, perfil.lower())
                    conteo[clave] += 1
                    nombres.setdefault(clave, perfil)
            libro.close()

        minimo = opciones['minimo']
        elegidos = defaultdict(set)   # perfil(minúscula) -> categorías
        veces = Counter()
        for (categoria, perfil_min), n in conteo.items():
            if n >= minimo:
                elegidos[perfil_min].add(categoria)
                veces[perfil_min] += n

        self.stdout.write(f'Archivos leídos: {len(archivos)} | perfiles distintos: {len(conteo)} '
                          f'| con {minimo}+ apariciones: {len(elegidos)}')

        if opciones['simular']:
            for perfil_min, cats in sorted(elegidos.items(), key=lambda x: -veces[x[0]])[:40]:
                self.stdout.write(f'  {nombres[(sorted(cats)[0], perfil_min)]}  [{", ".join(sorted(cats))}]  x{veces[perfil_min]}')
            self.stdout.write(self.style.WARNING('Simulación: no se guardó nada.'))
            return

        creados = actualizados = 0
        with transaction.atomic():
            for perfil_min, cats in elegidos.items():
                nombre = nombres[(sorted(cats)[0], perfil_min)]
                existente = Escenario.objects.filter(nombre__iexact=nombre).first()
                if existente:
                    escenario = existente
                    actualizados += 1
                else:
                    escenario = Escenario.objects.create(
                        nombre=nombre,
                        descripcion=(f'Perfil de simulación «{nombre}», utilizado {veces[perfil_min]} veces '
                                     f'en la programación de Simulactores ({", ".join(sorted(cats))}).'),
                        guion=GUION_PENDIENTE,
                        tipo=TipoSimulacion.OTRO,
                    )
                    creados += 1
                for cat in cats:
                    categoria, _ = Categoria.objects.get_or_create(nombre=cat)
                    escenario.categorias.add(categoria)

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {creados} escenarios nuevos, {actualizados} ya existían (solo se les sumó categoría).'))
