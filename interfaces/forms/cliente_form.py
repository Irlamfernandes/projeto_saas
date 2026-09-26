from django import forms
from infrastructure.models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'telefone', 'email', 'endereco']
        error_messages = {
            'nome': {
                'required': "O nome do cliente é obrigatório.",
                'max_length': "O nome pode ter no máximo 255 caracteres.",
            },
            'telefone': {'max_length': "O telefone pode ter no máximo 20 caracteres."},
            'email': {'invalid': "Informe um e-mail válido."},
        }


class BuscaClientesForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, error_messages={
        'max_length': "O termo de busca é muito longo.",
    })


class PagamentoForm(forms.Form):
    valor = forms.DecimalField(
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        localize=True,
        error_messages={
            'required': "Informe o valor do pagamento.",
            'invalid': "O valor informado para o pagamento é inválido.",
            'min_value': "O valor do pagamento deve ser maior que zero.",
            'max_whole_digits': "O valor do pagamento é alto demais.",
            'max_decimal_places': "Use no máximo duas casas decimais.",
        },
    )
    observacao = forms.CharField(required=False, max_length=255, error_messages={
        'max_length': "A observação excede o limite máximo de 255 caracteres.",
    })

    def parametros(self):
        return {'valor': self.cleaned_data['valor'], 'observacao': self.cleaned_data['observacao']}
