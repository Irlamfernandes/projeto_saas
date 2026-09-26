from django.test import TestCase
from interfaces.forms.login_form import LoginForm


class LoginFormTest(TestCase):

    def test_form_valido_com_dados_corretos(self):
        """O formulário deve ser válido quando fornecidos username e password válidos."""
        form_data = {
            'username': 'admin_loja',
            'password': 'minhasenhasegura123'
        }
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalido_sem_username(self):
        """O formulário deve ser inválido se o username estiver ausente."""
        form_data = {
            'username': '',
            'password': 'minhasenhasegura123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_form_invalido_sem_password(self):
        """O formulário deve ser inválido se a senha estiver ausente."""
        form_data = {
            'username': 'admin_loja',
            'password': ''
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_username_excede_max_length(self):
        """O formulário deve falhar se o username ultrapassar 150 caracteres."""
        username_longo = 'a' * 151
        form_data = {
            'username': username_longo,
            'password': 'senha'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_password_excede_max_length(self):
        """O formulário deve falhar se a senha ultrapassar 128 caracteres."""
        password_longa = 'a' * 129
        form_data = {
            'username': 'admin',
            'password': password_longa
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_widgets_e_atributos(self):
        """Campos usam o componente visual `entrada` e os atributos de preenchimento automático."""
        form = LoginForm()
        
        # Valida campo username
        username_html = str(form['username'])
        self.assertIn('class="entrada"', username_html)
        self.assertIn('placeholder="Seu nome de usuário"', username_html)
        self.assertIn('autocapitalize="none"', username_html)
        self.assertIn('autocomplete="username"', username_html)

        # Valida campo password
        password_html = str(form['password'])
        self.assertIn('type="password"', password_html)
        self.assertIn('class="entrada"', password_html)
        self.assertIn('placeholder="Sua senha"', password_html)
        self.assertIn('autocomplete="current-password"', password_html)