from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

MAXIMO_DE_ITENS = 30
QUANTIDADE_MAXIMA = Decimal('1000000')
ERRO_ITEM = "Um dos produtos da compra está incompleto. Confira produto, quantidade e custo."
MOTIVOS_SUGERIDOS = ('Venceu', 'Quebrou ou estragou', 'Consumo próprio', 'Brinde ou amostra', 'Sumiu')


def _data():
    return forms.DateField(initial=timezone.localdate, error_messages={
        'required': "Informe a data.", 'invalid': "Data inválida.",
    })


def _decimal(texto):
    """Aceita vírgula ou ponto. Recusa infinito, NaN e números absurdos."""
    numero = Decimal(texto.strip().replace(',', '.'))
    if not numero.is_finite() or numero >= QUANTIDADE_MAXIMA:
        raise InvalidOperation
    return numero


def produto_e_variacao(texto):
    """Valor do seletor de produto: '12' (produto 12) ou '12:5' (variação 5 do produto 12)."""
    produto, separador, variacao = texto.strip().partition(':')
    return int(produto), int(variacao) if separador else None


def _converter(linhas):
    try:
        return [
            (*produto_e_variacao(produto), _decimal(quantidade), _decimal(custo)) for produto, quantidade, custo in linhas
        ]
    except (ValueError, InvalidOperation):
        raise ValidationError(ERRO_ITEM) from None


class CompraForm(forms.Form):
    """Os itens chegam em listas paralelas: item_produto[], item_quantidade[] e item_custo[]."""

    data = _data()
    fornecedor = forms.CharField(required=False, max_length=120, error_messages={
        'max_length': "O fornecedor pode ter no máximo 120 caracteres.",
    })
    observacao = forms.CharField(required=False, max_length=255, error_messages={
        'max_length': "A observação pode ter no máximo 255 caracteres.",
    })
    atualizar_custo = forms.BooleanField(required=False)

    def clean(self):
        dados = super().clean()
        dados['itens'] = self._ler_itens()
        return dados

    def _ler_itens(self):
        itens = _converter(self._linhas_preenchidas())
        if any(quantidade <= 0 or custo < 0 for _, _, quantidade, custo in itens):
            raise ValidationError("A quantidade precisa ser maior que zero e o custo não pode ser negativo.")
        return [
            (produto, quantidade, custo.quantize(Decimal('0.01')), variacao)
            for produto, variacao, quantidade, custo in itens
        ]

    def _linhas_preenchidas(self):
        """Linhas (produto, quantidade, custo) com algo escrito; linhas totalmente em branco são ignoradas."""
        colunas = [self.data.getlist(nome) for nome in ('item_produto', 'item_quantidade', 'item_custo')]
        # strict=False: colunas de tamanhos diferentes (POST adulterado) viram ERRO_ITEM logo abaixo, não erro 500
        linhas = [linha for linha in zip(*colunas, strict=False) if any(parte.strip() for parte in linha)]
        if not linhas:
            raise ValidationError("Adicione pelo menos um produto à compra.")
        if len(set(map(len, colunas))) != 1 or len(linhas) > MAXIMO_DE_ITENS:
            raise ValidationError(ERRO_ITEM)
        return linhas

    def parametros(self):
        dados = self.cleaned_data
        return {
            'itens': dados['itens'], 'data': dados['data'], 'fornecedor': dados['fornecedor'],
            'observacao': dados['observacao'], 'atualizar_custo': dados['atualizar_custo'],
        }


class DespesaForm(forms.Form):
    data = _data()
    categoria = forms.CharField(max_length=60, error_messages={
        'required': "Escolha ou escreva a categoria da despesa.",
        'max_length': "A categoria pode ter no máximo 60 caracteres.",
    })
    descricao = forms.CharField(required=False, max_length=255, error_messages={
        'max_length': "A descrição pode ter no máximo 255 caracteres.",
    })
    valor = forms.DecimalField(min_value=Decimal('0.01'), max_digits=12, decimal_places=2, localize=True, error_messages={
        'required': "Informe o valor da despesa.",
        'invalid': "Valor inválido.",
        'min_value': "O valor deve ser maior que zero.",
        'max_digits': "Valor grande demais.",
        'max_whole_digits': "Valor grande demais.",
        'max_decimal_places': "Use no máximo 2 casas depois da vírgula.",
    })

    def parametros(self):
        return dict(self.cleaned_data)


class PerdaForm(forms.Form):
    data = _data()
    # '12' ou '12:5' (com a variação): ver produto_e_variacao.
    produto = forms.CharField(error_messages={'required': "Escolha o produto que se perdeu."})
    quantidade = forms.DecimalField(min_value=Decimal('0.001'), max_digits=12, decimal_places=3, localize=True,
                                    error_messages={
                                        'required': "Informe a quantidade perdida.",
                                        'invalid': "Quantidade inválida.",
                                        'min_value': "A quantidade deve ser maior que zero.",
                                        'max_digits': "Quantidade grande demais.",
                                        'max_whole_digits': "Quantidade grande demais.",
                                        'max_decimal_places': "Use no máximo 3 casas depois da vírgula.",
                                    })
    motivo = forms.CharField(max_length=120, error_messages={
        'required': "Conte o motivo da perda.",
        'max_length': "O motivo pode ter no máximo 120 caracteres.",
    })

    def __init__(self, *args, produtos, **kwargs):
        super().__init__(*args, **kwargs)
        self.produtos = produtos

    def clean_produto(self):
        try:
            produto_id, variacao_id = produto_e_variacao(self.cleaned_data['produto'])
        except ValueError:
            produto_id, variacao_id = None, None
        if not self.produtos.filter(pk=produto_id).exists():
            raise ValidationError("Produto não encontrado nesta loja.")
        return produto_id, variacao_id

    def parametros(self):
        dados = self.cleaned_data
        produto_id, variacao_id = dados['produto']
        return {
            'produto_id': produto_id, 'variacao_id': variacao_id, 'quantidade': dados['quantidade'],
            'data': dados['data'], 'motivo': dados['motivo'],
        }
