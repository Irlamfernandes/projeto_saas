"""Registro de alterações: quem fez o quê, quando, e como estava antes."""
from decimal import Decimal
from infrastructure.models import RegistroDeAlteracao

CENTAVOS = Decimal('0.01')


def registrar_alteracao(*, loja, usuario, acao, descricao, detalhes=None, clientes=()):
    """`clientes`: os que o registro cita pelo nome (vazios são ignorados), para a LGPD achar depois."""
    registro = RegistroDeAlteracao.objects.create(
        loja=loja,
        usuario=usuario if usuario is not None and usuario.is_authenticated else None,
        acao=acao,
        descricao=descricao[:255],
        detalhes=detalhes or {},
    )
    citados = {cliente.pk for cliente in clientes if cliente is not None}
    if citados:
        registro.clientes.set(citados)
    return registro


def fotografar(instancia, campos):
    """Valores dos campos num dicionário que cabe em JSON (Decimal vira texto: '10.00')."""
    return {campo: _para_json(getattr(instancia, campo)) for campo in campos}


def diferencas(antes, depois):
    """Só o que mudou: {'campo': [antes, depois]}."""
    return {campo: [antes.get(campo), valor] for campo, valor in depois.items() if antes.get(campo) != valor}


def _para_json(valor):
    if isinstance(valor, Decimal):
        # 10, 10.00 e 10.000 são o mesmo valor: com casas fixas, digitar "10" não vira uma alteração falsa.
        # Só quantidades com frações de verdade (0.125 kg) ficam com mais de duas casas.
        if valor == valor.quantize(CENTAVOS):
            valor = valor.quantize(CENTAVOS)
        return str(valor)
    return valor
