from django import forms
from infrastructure.models import Cliente, FormaDePagamento
from infrastructure.utils.cpf import cpf_valido, so_digitos


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'telefone', 'cpf', 'email', 'endereco']
        error_messages = {
            'nome': {
                'required': "O nome do cliente é obrigatório.",
                'max_length': "O nome pode ter no máximo 255 caracteres.",
            },
            'telefone': {'max_length': "O telefone pode ter no máximo 20 caracteres."},
            'email': {'invalid': "Informe um e-mail válido."},
        }

    cpf = forms.CharField(required=False, max_length=20, error_messages={'max_length': "Informe um CPF válido."})

    def clean_cpf(self):
        """Aceita com ou sem pontos e traço; guarda só os dígitos. Vazio = não informado."""
        digitos = so_digitos(self.cleaned_data['cpf'])
        if digitos and not cpf_valido(digitos):
            raise forms.ValidationError("Informe um CPF válido.")
        # A regra do banco (um CPF por loja) não é conferida pelo formulário, que não tem o campo loja.
        outros = Cliente.objects.filter(loja_id=self.instance.loja_id, cpf=digitos).exclude(pk=self.instance.pk)
        if digitos and outros.exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return digitos


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
    forma_pagamento = forms.ChoiceField(choices=FormaDePagamento.choices, error_messages={
        'required': "Informe como foi pago.",
        'invalid_choice': "Forma de pagamento inválida.",
    })
    observacao = forms.CharField(required=False, max_length=255, error_messages={
        'max_length': "A observação excede o limite máximo de 255 caracteres.",
    })

    def parametros(self):
        dados = self.cleaned_data
        return {'valor': dados['valor'], 'forma_pagamento': dados['forma_pagamento'], 'observacao': dados['observacao']}


class ApagarDadosDoClienteForm(forms.Form):
    senha = forms.CharField(
        strip=False, widget=forms.PasswordInput, error_messages={'required': "Digite sua senha para confirmar."},
    )

    def parametros(self):
        return {'senha': self.cleaned_data['senha']}
