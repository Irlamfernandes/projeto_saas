import json
from decimal import Decimal, InvalidOperation
from django import forms
from django.core.exceptions import ValidationError
from infrastructure.models import Cliente, FormaDePagamento

MAXIMO_DE_ITENS = 50
MAXIMO_DE_PARCELAS = 12
QUANTIDADE_MAXIMA = Decimal('1000000')
ERRO_ITEM = "Um dos itens da venda é inválido. Remova-o e adicione de novo."


def _escolhas(texto):
    """Opções escolhidas no item, em JSON: {"Tamanho": "G"}. Vazio = produto sem opções."""
    if not texto.strip():
        return {}
    escolhas = json.loads(texto)
    if not isinstance(escolhas, dict) or not all(isinstance(v, str) for v in escolhas.values()):
        raise ValueError
    return escolhas


def _quantidade(texto):
    """Aceita vírgula ou ponto (2,5 ou 2.5). As casas permitidas dependem da unidade e são conferidas na venda."""
    quantidade = Decimal(texto.strip().replace(',', '.'))
    if not quantidade.is_finite() or quantidade >= QUANTIDADE_MAXIMA:
        raise InvalidOperation
    return quantidade


class _VendaForm(forms.Form):
    """Cliente vazio = venda de balcão. Os itens chegam em listas paralelas: item_produto[], item_quantidade[]
    e item_opcoes[] (esta pode faltar: sem opções em nenhum item)."""

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
        dados['vencimentos'] = self._ler_vencimentos()
        return dados

    def _ler_vencimentos(self):
        """Uma data por parcela do que fica na caderneta (campo `vencimento` repetido). Nenhuma = sem prazo."""
        textos = [texto for texto in self.data.getlist('vencimento') if texto.strip()]
        if len(textos) > MAXIMO_DE_PARCELAS:
            raise ValidationError(f"Divida em no máximo {MAXIMO_DE_PARCELAS} parcelas.")
        campo = forms.DateField(error_messages={'invalid': "Data de vencimento inválida."})
        return sorted(campo.clean(texto) for texto in textos)

    def _ler_itens(self):
        produtos = self.data.getlist('item_produto')
        quantidades = self.data.getlist('item_quantidade')
        opcoes = self.data.getlist('item_opcoes') or [''] * len(produtos)
        if not produtos:
            raise ValidationError("Adicione pelo menos um produto à venda.")
        if not len(produtos) == len(quantidades) == len(opcoes) or len(produtos) > MAXIMO_DE_ITENS:
            raise ValidationError(ERRO_ITEM)
        try:
            itens = [
                (int(produto), _quantidade(quantidade), _escolhas(escolhas))
                for produto, quantidade, escolhas in zip(produtos, quantidades, opcoes)
            ]
        except (ValueError, InvalidOperation):
            raise ValidationError(ERRO_ITEM) from None
        if any(quantidade <= 0 for _, quantidade, _escolhas in itens):
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
            'vencimentos': dados['vencimentos'],
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
