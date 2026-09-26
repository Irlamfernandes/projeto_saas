def definir_senha_definitiva(user, senha):
    """Substitui a senha temporária (gerada pelo admin) pela senha escolhida pelo usuário."""
    user.set_password(senha)
    user.deve_trocar_senha = False
    user.save(update_fields=['password', 'deve_trocar_senha'])
