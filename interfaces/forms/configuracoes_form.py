from django import forms
from django.core.validators import FileExtensionValidator
from interfaces.forms.produto_form import EXTENSOES_DE_IMAGEM, validar_tamanho_da_imagem


class MarcaForm(forms.Form):
    marca = forms.ImageField(
        validators=[
            FileExtensionValidator(EXTENSOES_DE_IMAGEM, message="Envie uma imagem JPG, PNG ou WEBP."),
            validar_tamanho_da_imagem,
        ],
        error_messages={
            'required': "Escolha a imagem da marca.",
            'invalid_image': "Envie uma imagem válida (JPG, PNG ou WEBP).",
        },
    )
