def definir_senha_definitiva(user, senha):
    """Substitui a senha temporária (gerada pelo admin) pela senha escolhida pelo usuário."""
    user.set_password(senha)
    user.deve_trocar_senha = False
    user.save(update_fields=['password', 'deve_trocar_senha'])


def trocar_tema(user, tema):
    """Guarda a aparência escolhida (vale em qualquer aparelho em que a pessoa entrar)."""
    user.tema = tema
    user.save(update_fields=['tema'])
