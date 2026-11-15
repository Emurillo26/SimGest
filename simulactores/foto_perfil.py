"""Foto de perfil: cualquier usuario puede subir, cambiar o quitar su foto desde Mi perfil."""
import uuid
from io import BytesIO

from django import forms
from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps

from .permisos import modulo_requerido
from .utils import registrar_cambios

TAMANO_MAXIMO_MB = 5
FORMATOS_PERMITIDOS = {'JPEG', 'PNG', 'WEBP'}
LADO_FINAL = 400  # px: la foto se guarda cuadrada de 400 x 400


class FotoPerfilForm(forms.Form):
    foto = forms.ImageField(
        error_messages={
            'required': 'Elige una imagen.',
            'invalid_image': 'El archivo no es una imagen válida.',
        }
    )

    def clean_foto(self):
        foto = self.cleaned_data['foto']
        if foto.size > TAMANO_MAXIMO_MB * 1024 * 1024:
            raise forms.ValidationError(f'La imagen pesa más de {TAMANO_MAXIMO_MB} MB.')
        formato = getattr(foto, 'image', None) and foto.image.format
        if formato not in FORMATOS_PERMITIDOS:
            raise forms.ValidationError('Usa una imagen JPG, PNG o WEBP.')
        return foto


def preparar_foto(archivo):
    """Endereza la foto según el celular, la recorta al centro en cuadrado y la reduce."""
    archivo.seek(0)
    imagen = ImageOps.exif_transpose(Image.open(archivo))
    imagen = ImageOps.fit(imagen.convert('RGB'), (LADO_FINAL, LADO_FINAL), Image.LANCZOS)
    salida = BytesIO()
    imagen.save(salida, format='JPEG', quality=85, optimize=True)
    return ContentFile(salida.getvalue())


def _ip(request):
    return request.META.get('REMOTE_ADDR')


def _borrar_archivo(campo):
    if campo:
        campo.storage.delete(campo.name)


@modulo_requerido('perfil')
@require_POST
def subir_foto_view(request):
    form = FotoPerfilForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form.errors['foto'][0])
        return redirect('simulactores:perfil')

    usuario = request.user
    anterior = usuario.foto.name if usuario.foto else None
    _borrar_archivo(usuario.foto)
    usuario.foto.save(f'{usuario.uuid}-{uuid.uuid4().hex[:8]}.jpg', preparar_foto(form.cleaned_data['foto']), save=True)

    registrar_cambios(usuario, 'Foto de perfil actualizada', [('foto', anterior, usuario.foto.name)],
                      realizado_por=usuario, ip_origen=_ip(request))
    messages.success(request, 'Tu foto de perfil se actualizó.')
    return redirect('simulactores:perfil')


@modulo_requerido('perfil')
@require_POST
def quitar_foto_view(request):
    usuario = request.user
    if usuario.foto:
        anterior = usuario.foto.name
        _borrar_archivo(usuario.foto)
        usuario.foto = None
        usuario.save(update_fields=['foto'])
        registrar_cambios(usuario, 'Foto de perfil eliminada', [('foto', anterior, None)],
                          realizado_por=usuario, ip_origen=_ip(request))
        messages.success(request, 'Quitaste tu foto de perfil.')
    return redirect('simulactores:perfil')
