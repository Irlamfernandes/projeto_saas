from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from application.produtos.selectors import ORDEM_PADRAO, ORDENACOES_PERMITIDAS
from infrastructure.models import Produto

EXTENSOES_DE_IMAGEM = ['jpg', 'jpeg', 'png', 'webp']
TAMANHO_MAXIMO_IMAGEM = 5 * 1024 * 1024


def validar_tamanho_da_imagem(arquivo):
    if arquivo.size > TAMANHO_MAXIMO_IMAGEM:
        raise ValidationError(f"A imagem '{arquivo.name}' excede o limite de 5 MB.")


class _EnvioMultiplo(forms.ClearableFileInput):
    allow_multiple_selected = True


class ImagensField(forms.ImageField):
    """Aceita vários arquivos no mesmo campo e valida cada um como imagem."""

    widget = _EnvioMultiplo
    default_error_messages = {
        'invalid_image': "Envie apenas imagens válidas (JPG, PNG ou WEBP).",
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('validators', [
            FileExtensionValidator(EXTENSOES_DE_IMAGEM, message="Envie apenas imagens JPG, PNG ou WEBP."),
            validar_tamanho_da_imagem,
        ])
        super().__init__(**kwargs)

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, (list, tuple)) else [data]
        return [super(ImagensField, self).clean(arquivo, initial) for arquivo in arquivos if arquivo]


class ProdutoForm(forms.ModelForm):
    ZERO_SE_VAZIO = {
        'preco_custo': Decimal('0.00'),
        'margem_lucro': Decimal('0.00'),
        'quantidade_estoque': 0,
    }

    imagens = ImagensField()

    class Meta:
        model = Produto
        fields = [
            'codigo_interno', 'nome', 'categoria', 'descricao',
            'preco_custo', 'preco_venda', 'margem_lucro', 'quantidade_estoque',
        ]
        localized_fields = ['preco_custo', 'preco_venda', 'margem_lucro']
        error_messages = {
            'nome': {
                'required': "O nome do produto é obrigatório.",
                'max_length': "O nome pode ter no máximo 150 caracteres.",
            },
            'codigo_interno': {'max_length': "O código interno pode ter no máximo 50 caracteres."},
            'categoria': {'max_length': "A categoria pode ter no máximo 100 caracteres."},
            'preco_venda': {
                'required': "Informe o preço de venda.",
                'invalid': "Preço de venda inválido.",
                'min_value': "O preço de venda deve ser maior que zero.",
            },
            'preco_custo': {
                'invalid': "Preço de custo inválido.",
                'min_value': "O preço de custo não pode ser negativo.",
            },
            'margem_lucro': {
                'invalid': "Margem de lucro inválida.",
                'min_value': "A margem de lucro não pode ser negativa.",
            },
            'quantidade_estoque': {
                'invalid': "Quantidade em estoque inválida.",
                'min_value': "A quantidade em estoque não pode ser negativa.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.ZERO_SE_VAZIO:
            self.fields[campo].required = False

    def clean(self):
        dados = super().clean()
        for campo, zero in self.ZERO_SE_VAZIO.items():
            if campo not in self.errors and dados.get(campo) is None:
                dados[campo] = zero
        return dados

    def parametros(self):
        return {'produto': self.instance, 'imagens': self.cleaned_data['imagens']}


class EditarProdutoForm(ProdutoForm):
    remover_imagens = forms.CharField(required=False)

    def clean_remover_imagens(self):
        ids = [parte.strip() for parte in self.cleaned_data['remover_imagens'].split(',') if parte.strip()]
        if not all(parte.isdigit() for parte in ids):
            raise ValidationError("Seleção de imagens para remover inválida.")
        return [int(parte) for parte in ids]

    def parametros(self):
        return {
            'produto': self.instance,
            'imagens_novas': self.cleaned_data['imagens'],
            'ids_imagens_remover': self.cleaned_data['remover_imagens'],
        }


class FiltroProdutosForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, error_messages={
        'max_length': "O termo de busca é muito longo.",
    })
    categoria = forms.CharField(required=False, max_length=100, error_messages={
        'max_length': "O filtro de categoria é inválido.",
    })
    ordem = forms.CharField(required=False)
    baixo_estoque = forms.BooleanField(required=False)

    def clean_ordem(self):
        ordem = self.cleaned_data['ordem']
        return ordem if ordem in ORDENACOES_PERMITIDAS else ORDEM_PADRAO

    def criterios(self):
        dados = self.cleaned_data
        return {
            'busca': dados['q'],
            'categoria': dados['categoria'],
            'baixo_estoque': dados['baixo_estoque'],
            'ordem': dados['ordem'],
        }
