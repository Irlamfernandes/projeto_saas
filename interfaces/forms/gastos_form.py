from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from infrastructure.models import Produto

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
        colunas = [self.data.getlist(nome) for nome in ('item_produto', 'item_quantidade', 'item_custo')]
        linhas = [linha for linha in zip(*colunas) if any(parte.strip() for parte in linha)]
        if not linhas:
            raise ValidationError("Adicione pelo menos um produto à compra.")
        if len(set(map(len, colunas))) != 1 or len(linhas) > MAXIMO_DE_ITENS:
            raise ValidationError(ERRO_ITEM)
        try:
            itens = [(int(produto), _decimal(quantidade), _decimal(custo)) for produto, quantidade, custo in linhas]
        except (ValueError, InvalidOperation):
            raise ValidationError(ERRO_ITEM) from None
        if any(quantidade <= 0 or custo < 0 for _, quantidade, custo in itens):
            raise ValidationError("A quantidade precisa ser maior que zero e o custo não pode ser negativo.")
        return [(produto, quantidade, custo.quantize(Decimal('0.01'))) for produto, quantidade, custo in itens]

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
    produto = forms.ModelChoiceField(queryset=Produto.objects.none(), error_messages={
        'required': "Escolha o produto que se perdeu.",
        'invalid_choice': "Produto não encontrado nesta loja.",
    })
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
        self.fields['produto'].queryset = produtos

    def parametros(self):
        dados = self.cleaned_data
        return {
            'produto_id': dados['produto'].pk, 'quantidade': dados['quantidade'], 'data': dados['data'],
            'motivo': dados['motivo'],
        }
