from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from infrastructure.models import Cliente, FormaDePagamento

MAXIMO_DE_ITENS = 50
ERRO_ITEM = "Um dos itens da venda é inválido. Remova-o e adicione de novo."


class _VendaForm(forms.Form):
    """Cliente vazio = venda de balcão. Os itens chegam em listas paralelas: item_produto[] e item_quantidade[]."""

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(),
        required=False,
        error_messages={'invalid_choice': "Cliente selecionado não foi encontrado."},
    )
    forma_pagamento = forms.ChoiceField(
        choices=[('', '---')] + FormaDePagamento.choices,
        required=False,
        error_messages={'invalid_choice': "Forma de pagamento inválida."},
    )
    observacoes = forms.CharField(required=False, max_length=500, error_messages={
        'max_length': "As observações podem ter no máximo 500 caracteres.",
    })

    def __init__(self, *args, clientes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = clientes

    def clean(self):
        dados = super().clean()
        dados['itens'] = self._ler_itens()
        return dados

    def _ler_itens(self):
        produtos = self.data.getlist('item_produto')
        quantidades = self.data.getlist('item_quantidade')
        if not produtos:
            raise ValidationError("Adicione pelo menos um produto à venda.")
        if len(produtos) != len(quantidades) or len(produtos) > MAXIMO_DE_ITENS:
            raise ValidationError(ERRO_ITEM)
        try:
            itens = [(int(produto), int(quantidade)) for produto, quantidade in zip(produtos, quantidades)]
        except ValueError:
            raise ValidationError(ERRO_ITEM) from None
        if any(quantidade < 1 for _, quantidade in itens):
            raise ValidationError("A quantidade de cada produto deve ser maior que zero.")
        return itens

    def _exigir_forma_se_houve_pagamento(self, dados, houve_pagamento):
        if houve_pagamento and not dados.get('forma_pagamento'):
            self.add_error('forma_pagamento', "Informe como foi pago.")

    def parametros(self):
        """Converte os dados validados nos argumentos esperados pelos services de venda."""
        dados = self.cleaned_data
        return {
            'cliente': dados['cliente'],
            'itens': dados['itens'],
            'forma_pagamento': dados['forma_pagamento'],
            'observacoes': dados['observacoes'],
        }


class NovaVendaForm(_VendaForm):
    valor_pago = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        error_messages={
            'invalid': "Valor pago inicial inválido.",
            'min_value': "O valor pago não pode ser negativo.",
        },
    )

    def clean(self):
        dados = super().clean()
        # Balcão é pago na hora; com cliente, só o que ele pagou agora.
        pagou = dados.get('cliente') is None or bool(dados.get('valor_pago'))
        self._exigir_forma_se_houve_pagamento(dados, pagou)
        return dados

    def parametros(self):
        dados = self.cleaned_data
        valor_pago = dados['valor_pago'] if dados['cliente'] else None
        return {**super().parametros(), 'valor_pago': valor_pago or Decimal('0')}


class EditarVendaForm(_VendaForm):
    def __init__(self, *args, venda, **kwargs):
        super().__init__(*args, **kwargs)
        self._venda = venda

    def clean(self):
        dados = super().clean()
        pagou = dados.get('cliente') is None or self._venda.pagamentos_no_ato.exists()
        self._exigir_forma_se_houve_pagamento(dados, pagou)
        return dados


class CancelarVendaForm(forms.Form):
    senha = forms.CharField(
        strip=False, widget=forms.PasswordInput, error_messages={'required': "Digite sua senha para confirmar."},
    )
    motivo = forms.CharField(max_length=200, error_messages={
        'required': "Conte o motivo do cancelamento.",
        'max_length': "O motivo pode ter no máximo 200 caracteres.",
    })

    def parametros(self):
        return {'senha': self.cleaned_data['senha'], 'motivo': self.cleaned_data['motivo']}
