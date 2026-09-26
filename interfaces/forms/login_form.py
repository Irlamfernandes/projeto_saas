from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'entrada',
            'placeholder': 'Seu nome de usuário',
            'autocomplete': 'username',
            'autocapitalize': 'none',
        }),
        label='Usuário'
    )
    password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'entrada',
            'placeholder': 'Sua senha',
            'autocomplete': 'current-password',
        }),
        label='Senha'
    )
