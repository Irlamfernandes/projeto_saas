"""Registro de alterações: quem fez o quê, quando, e como estava antes."""
from decimal import Decimal
from infrastructure.models import RegistroDeAlteracao

CENTAVOS = Decimal('0.01')


def registrar_alteracao(*, loja, usuario, acao, descricao, detalhes=None):
    return RegistroDeAlteracao.objects.create(
        loja=loja,
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
        acao=acao,
        descricao=descricao[:255],
        detalhes=detalhes or {},
    )


def fotografar(instancia, campos):
    """Valores dos campos num dicionário que cabe em JSON (Decimal vira texto: '10.00')."""
    return {campo: _para_json(getattr(instancia, campo)) for campo in campos}


def diferencas(antes, depois):
    """Só o que mudou: {'campo': [antes, depois]}."""
    return {campo: [antes.get(campo), valor] for campo, valor in depois.items() if antes.get(campo) != valor}


def _para_json(valor):
    if isinstance(valor, Decimal):
        # 10 e 10.00 são o mesmo preço: com casas fixas, digitar "10" não vira uma alteração falsa.
        if valor.as_tuple().exponent > -2:
            valor = valor.quantize(CENTAVOS)
        return str(valor)
    return valor
