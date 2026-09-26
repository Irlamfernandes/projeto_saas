from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

_MENSAGENS_DO_CAMPO = {
    'required': "Os campos de senha não podem estar vazios.",
    'max_length': "A senha excede o limite máximo de caracteres permitido.",
}


class NovaSenhaForm(forms.Form):
    """Troca de senha. Na troca voluntária (sem senha temporária pendente) exige a senha atual."""

    senha_atual = forms.CharField(max_length=128, strip=False, error_messages={
        'required': "Informe sua senha atual.",
    })
    nova_senha = forms.CharField(max_length=128, strip=False, error_messages=_MENSAGENS_DO_CAMPO)
    confirmacao_senha = forms.CharField(max_length=128, strip=False, error_messages=_MENSAGENS_DO_CAMPO)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user.deve_trocar_senha:
            del self.fields['senha_atual']

    def clean_senha_atual(self):
        senha = self.cleaned_data['senha_atual']
        if not self.user.check_password(senha):
            raise ValidationError("A senha atual está incorreta.")
        return senha

    def clean(self):
        dados = super().clean()
        senha, confirmacao = dados.get('nova_senha'), dados.get('confirmacao_senha')
        if senha is None or confirmacao is None:
            return dados
        if senha != confirmacao:
            raise ValidationError("As senhas não coincidem.")
        password_validation.validate_password(senha, self.user)
        return dados

    def lista_de_erros(self):
        """Todas as mensagens, sem repetição, na ordem em que ocorreram."""
        return list(dict.fromkeys(erro for erros in self.errors.values() for erro in erros))
