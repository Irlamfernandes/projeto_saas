from decimal import Decimal
from django import forms
from infrastructure.models import Cliente


class _VendaForm(forms.Form):
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(),
        error_messages={
            'required': "Selecione o cliente.",
            'invalid_choice': "Cliente selecionado não foi encontrado.",
        },
    )
    produto = forms.CharField(max_length=150, error_messages={'required': "Informe o produto."})
    quantidade = forms.IntegerField(
        min_value=1,
        error_messages={
            'required': "Informe a quantidade.",
            'invalid': "Quantidade inválida informada.",
            'min_value': "A quantidade deve ser maior que zero.",
        },
    )
    observacoes = forms.CharField(required=False)

    def __init__(self, *args, clientes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = clientes

    def parametros(self):
        """Converte os dados validados nos argumentos esperados pelos services de venda."""
        dados = self.cleaned_data
        return {
            'cliente': dados['cliente'],
            'termo_produto': dados['produto'],
            'quantidade': dados['quantidade'],
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

    def parametros(self):
        return {**super().parametros(), 'valor_pago': self.cleaned_data['valor_pago'] or Decimal('0')}


class EditarVendaForm(_VendaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].required = False
