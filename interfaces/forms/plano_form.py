from django import forms
from application.assinatura.selectors import planos_disponiveis


class RenovarPlanoForm(forms.Form):
    plano = forms.ModelChoiceField(
        queryset=planos_disponiveis(), empty_label=None,
        error_messages={'required': "Escolha um plano.", 'invalid_choice': "Este plano não está mais disponível. Escolha outro."},
    )
    # Guardado como a pessoa digitou (maiúsculas e números inclusive); só os espaços das pontas saem.
    email = forms.EmailField(max_length=254, error_messages={
        'required': "Informe o e-mail para o comprovante.",
        'invalid': "Informe um e-mail válido, como nome@exemplo.com.",
        'max_length': "O e-mail pode ter no máximo 254 caracteres.",
    })
