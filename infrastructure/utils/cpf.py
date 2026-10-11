"""CPF do cliente: guardado só com os 11 dígitos e mostrado como 123.456.789-09."""
TAMANHO = 11


def so_digitos(texto):
    return ''.join(letra for letra in texto or '' if letra.isdigit())


def _digito_verificador(digitos):
    peso_inicial = len(digitos) + 1
    soma = sum(int(digito) * (peso_inicial - posicao) for posicao, digito in enumerate(digitos))
    resto = soma * 10 % 11
    return '0' if resto == 10 else str(resto)


def cpf_valido(digitos):
    """11 dígitos, não todos iguais (111.111.111-11 passa na conta, mas não existe) e com os 2 verificadores certos."""
    if len(digitos) != TAMANHO or len(set(digitos)) == 1:
        return False
    primeiro = _digito_verificador(digitos[:9])
    return digitos[9:] == primeiro + _digito_verificador(digitos[:9] + primeiro)


def formatar_cpf(digitos):
    if len(digitos) != TAMANHO:
        return digitos
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
