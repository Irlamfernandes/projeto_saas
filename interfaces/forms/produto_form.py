from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from application.produtos.selectors import ORDEM_PADRAO, ORDENACOES_PERMITIDAS
from infrastructure.models import Produto, Unidade
from infrastructure.models.produto import MAXIMO_DE_VARIACOES, MILESIMO, TAMANHO_DO_NOME_DA_VARIACAO, quantidade_aceita

# HEIC/HEIF: o formato das fotos do iPhone e de vários Androids (lido pelo pi-heif, ligado em infrastructure/apps.py).
EXTENSOES_DE_IMAGEM = ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif']
# Limite do arquivo enviado. O que fica guardado é bem menor: a foto é reduzida e regravada em WebP.
TAMANHO_MAXIMO_MB = 25
TAMANHO_MAXIMO_IMAGEM = TAMANHO_MAXIMO_MB * 1024 * 1024
CENTAVO = Decimal('0.01')
LIMITE_DO_ACRESCIMO = Decimal('100000000')  # o campo guarda até 99.999.999,99
LIMITE_DA_QUANTIDADE = Decimal('1000000000')  # 12 dígitos, 3 depois da vírgula


def validar_tamanho_da_imagem(arquivo):
    if arquivo.size > TAMANHO_MAXIMO_IMAGEM:
        raise ValidationError(f"A imagem '{arquivo.name}' excede o limite de {TAMANHO_MAXIMO_MB} MB.")


class _EnvioMultiplo(forms.ClearableFileInput):
    allow_multiple_selected = True


class ImagensField(forms.ImageField):
    """Aceita vários arquivos no mesmo campo e valida cada um como imagem."""

    widget = _EnvioMultiplo
    default_error_messages = {
        'invalid_image': "Envie apenas imagens válidas (JPG, PNG, WEBP ou HEIC).",
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('validators', [
            FileExtensionValidator(EXTENSOES_DE_IMAGEM, message="Envie apenas imagens JPG, PNG, WEBP ou HEIC."),
            validar_tamanho_da_imagem,
        ])
        super().__init__(**kwargs)

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, (list, tuple)) else [data]
        return [super(ImagensField, self).clean(arquivo, initial) for arquivo in arquivos if arquivo]


def ler_variacoes(dados, unidade, controla_estoque):
    """Linhas repetidas variacao_id, variacao_nome, variacao_acrescimo e variacao_quantidade -> lista de variações.

    Linha toda em branco é ignorada. O acréscimo e a quantidade são opcionais (vazio = 0); sem controle de estoque,
    a quantidade nem é lida. `id` vazio = variação nova.
    """
    linhas = zip(
        dados.getlist('variacao_id'), dados.getlist('variacao_nome'),
        dados.getlist('variacao_acrescimo'), dados.getlist('variacao_quantidade'), strict=False,
    )  # listas vindas do POST: sobra adulterada é ignorada
    variacoes = []
    for id_texto, nome, acrescimo, quantidade in linhas:
        nome = nome.strip()
        if not (nome or acrescimo.strip() or quantidade.strip()):
            continue
        if not nome:
            raise ValidationError("Dê um nome para cada variação (ex.: Azul P, Chocolate).")
        variacoes.append({
            'id': _id_da_variacao(id_texto),
            'nome': nome,
            'acrescimo': _numero(acrescimo, f"Acréscimo inválido em \"{nome}\".", LIMITE_DO_ACRESCIMO).quantize(CENTAVO),
            'quantidade': _quantidade(quantidade, nome, unidade) if controla_estoque else Decimal('0'),
        })
    _conferir_variacoes(variacoes)
    return variacoes


def _id_da_variacao(texto):
    if not texto.strip():
        return None
    if not texto.strip().isdigit():
        raise ValidationError("Variação inválida.")
    return int(texto)


def _numero(texto, mensagem, limite):
    """'5,00', '5.00', 'R$ 5' ou vazio (0). Negativo ou grande demais é recusado."""
    texto = texto.replace('R$', '').strip().replace(',', '.')
    try:
        numero = Decimal(texto or '0')
    except InvalidOperation:
        raise ValidationError(mensagem) from None
    if not numero.is_finite() or numero < 0 or numero >= limite:
        raise ValidationError(mensagem)
    return numero


def _quantidade(texto, nome, unidade):
    quantidade = _numero(texto, f"Quantidade inválida em \"{nome}\".", LIMITE_DA_QUANTIDADE).quantize(MILESIMO)
    if not quantidade_aceita(quantidade, unidade):
        raise ValidationError(f"Esta unidade só aceita números inteiros: confira a quantidade de \"{nome}\".")
    return quantidade


def _conferir_variacoes(variacoes):
    if len(variacoes) > MAXIMO_DE_VARIACOES:
        raise ValidationError(f"Cada produto pode ter até {MAXIMO_DE_VARIACOES} variações.")
    vistos = set()
    for variacao in variacoes:
        nome = variacao['nome']
        if len(nome) > TAMANHO_DO_NOME_DA_VARIACAO:
            raise ValidationError(
                f"\"{nome[:20]}…\" é longo demais: use até {TAMANHO_DO_NOME_DA_VARIACAO} letras no nome da variação.",
            )
        if nome.casefold() in vistos:
            raise ValidationError(f"Há duas variações chamadas \"{nome}\".")
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
            self.variacoes = ler_variacoes(self.data, dados.get('unidade'), self.instance.controla_estoque)
        except ValidationError as erro:
            self.variacoes = []
            self.add_error(None, erro)
        if not self.instance.controla_estoque:
            dados['quantidade_estoque'] = Decimal('0')
        elif self.variacoes:  # com variações, o estoque do produto é a soma delas
            dados['quantidade_estoque'] = sum((variacao['quantidade'] for variacao in self.variacoes), Decimal('0'))
        if 'quantidade_estoque' in dados:
            # Mesma forma que vem do banco (3 casas): o histórico só registra o que mudou de verdade.
            dados['quantidade_estoque'] = dados['quantidade_estoque'].quantize(MILESIMO)
            if not quantidade_aceita(dados['quantidade_estoque'], dados.get('unidade')):
                self.add_error('quantidade_estoque', "Esta unidade só aceita números inteiros no estoque.")
        return dados

    def parametros(self):
        return {'produto': self.instance, 'variacoes': self.variacoes, 'imagens': self.cleaned_data['imagens']}


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
            'variacoes': self.variacoes,
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
