import re
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from application.produtos.selectors import ORDEM_PADRAO, ORDENACOES_PERMITIDAS
from infrastructure.models import Produto, Unidade
from infrastructure.models.produto import MAXIMO_DE_OPCOES, MILESIMO, quantidade_aceita

EXTENSOES_DE_IMAGEM = ['jpg', 'jpeg', 'png', 'webp']
# Limite do arquivo enviado. O que fica guardado é bem menor: a foto é reduzida e regravada em WebP.
TAMANHO_MAXIMO_MB = 15
TAMANHO_MAXIMO_IMAGEM = TAMANHO_MAXIMO_MB * 1024 * 1024
MAXIMO_DE_VALORES = 30
TAMANHO_DO_NOME_NA_OPCAO = 40
# O que vem depois do último "+" em "G + 5,00" ou "G +R$ 5": o valor G custa R$ 5 a mais.
_ACRESCIMO = re.compile(r'(?:R\$\s*)?(\d{1,7}(?:[.,]\d{1,2})?)')


def validar_tamanho_da_imagem(arquivo):
    if arquivo.size > TAMANHO_MAXIMO_IMAGEM:
        raise ValidationError(f"A imagem '{arquivo.name}' excede o limite de {TAMANHO_MAXIMO_MB} MB.")


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


def ler_opcoes(nomes, textos):
    """Campos repetidos opcao_nome e opcao_valores (um valor por linha) -> opções do produto. Blocos vazios são ignorados."""
    opcoes = []
    for nome, texto in zip(nomes, textos):
        nome = nome.strip()
        valores = [_ler_valor(linha.strip()) for linha in texto.splitlines() if linha.strip()]
        if not nome and not valores:
            continue
        if not nome:
            raise ValidationError("Dê um nome para cada opção (ex.: Tamanho, Sabor, Cor).")
        if not valores:
            raise ValidationError(f"Escreva os valores da opção \"{nome}\", um por linha.")
        opcoes.append({'nome': nome, 'valores': valores})
    _conferir_opcoes(opcoes)
    return opcoes


def _ler_valor(linha):
    nome, mais, depois = linha.rpartition('+')
    achou = _ACRESCIMO.fullmatch(depois.strip())
    if not (mais and nome.strip() and achou):
        return {'nome': linha, 'acrescimo': '0.00'}
    acrescimo = Decimal(achou[1].replace(',', '.')).quantize(Decimal('0.01'))
    return {'nome': nome.strip(), 'acrescimo': str(acrescimo)}


def _conferir_opcoes(opcoes):
    if len(opcoes) > MAXIMO_DE_OPCOES:
        raise ValidationError(f"Cada produto pode ter até {MAXIMO_DE_OPCOES} opções.")
    _sem_repetir([opcao['nome'] for opcao in opcoes], "Há duas opções chamadas \"{}\".")
    for opcao in opcoes:
        nomes = [valor['nome'] for valor in opcao['valores']]
        if len(nomes) > MAXIMO_DE_VALORES:
            raise ValidationError(f"A opção \"{opcao['nome']}\" pode ter até {MAXIMO_DE_VALORES} valores.")
        _sem_repetir(nomes, f"O valor \"{{}}\" aparece duas vezes em \"{opcao['nome']}\".")
        longo = next((texto for texto in [opcao['nome'], *nomes] if len(texto) > TAMANHO_DO_NOME_NA_OPCAO), None)
        if longo:
            raise ValidationError(
                f"\"{longo[:20]}…\" é longo demais: use até {TAMANHO_DO_NOME_NA_OPCAO} letras em cada opção e valor.",
            )


def _sem_repetir(nomes, mensagem):
    vistos = set()
    for nome in nomes:
        if nome.casefold() in vistos:
            raise ValidationError(mensagem.format(nome))
        vistos.add(nome.casefold())


class ProdutoForm(forms.ModelForm):
    ZERO_SE_VAZIO = {
        'preco_custo': Decimal('0.00'),
        'margem_lucro': Decimal('0.00'),
        'quantidade_estoque': Decimal('0'),
        'unidade': Unidade.UNIDADE,
    }

    imagens = ImagensField()
    # Marcado = produto sem controle de estoque. Desmarcado (ou ausente) = controla, como sempre foi.
    sem_controle_de_estoque = forms.BooleanField(required=False)

    class Meta:
        model = Produto
        fields = [
            'codigo_interno', 'nome', 'categoria', 'descricao',
            'preco_custo', 'preco_venda', 'margem_lucro', 'unidade', 'quantidade_estoque',
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
                'max_digits': "Quantidade em estoque grande demais.",
                'max_whole_digits': "Quantidade em estoque grande demais.",
                'max_decimal_places': "Use no máximo 3 casas depois da vírgula na quantidade em estoque.",
            },
            'unidade': {'invalid_choice': "Unidade de medida inválida."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.ZERO_SE_VAZIO:
            self.fields[campo].required = False

    def clean(self):
        dados = super().clean()
        for campo, zero in self.ZERO_SE_VAZIO.items():
            if campo not in self.errors and dados.get(campo) in (None, ''):
                dados[campo] = zero
        self.instance.controla_estoque = not dados.get('sem_controle_de_estoque')
        try:
            self.instance.opcoes = ler_opcoes(self.data.getlist('opcao_nome'), self.data.getlist('opcao_valores'))
        except ValidationError as erro:
            self.add_error(None, erro)
        if not self.instance.controla_estoque:
            dados['quantidade_estoque'] = Decimal('0')
        if 'quantidade_estoque' in dados:
            # Mesma forma que vem do banco (3 casas): o histórico só registra o que mudou de verdade.
            dados['quantidade_estoque'] = dados['quantidade_estoque'].quantize(MILESIMO)
            if not quantidade_aceita(dados['quantidade_estoque'], dados.get('unidade')):
                self.add_error('quantidade_estoque', "Esta unidade só aceita números inteiros no estoque.")
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
