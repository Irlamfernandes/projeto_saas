import pytest


@pytest.fixture(autouse=True)
def _hasher_de_senha_rapido(settings):
    """PBKDF2 é propositalmente lento; nos testes basta um hasher barato."""
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
