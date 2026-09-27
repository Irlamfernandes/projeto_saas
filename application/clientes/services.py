from django.db import transaction
from application.auditoria.services import diferencas, fotografar, registrar_alteracao
from application.clientes.exceptions import ClienteSemLoja
from application.formatacao import reais
from infrastructure.models import Acao, Cliente, PagamentoCliente

OBSERVACAO_PADRAO_PAGAMENTO = 'Pagamento na caderneta'
CAMPOS_DO_CLIENTE = ('nome', 'telefone', 'email', 'endereco')


@transaction.atomic
def cadastrar_cliente(cliente, usuario=None):
    if cliente.loja_id is None:
        raise ClienteSemLoja()
    cliente.save()
    registrar_alteracao(
        loja=cliente.loja, usuario=usuario, acao=Acao.CLIENTE_CADASTRADO, descricao=cliente.nome,
        detalhes={'cliente': fotografar(cliente, CAMPOS_DO_CLIENTE)},
    )
    return cliente


@transaction.atomic
def atualizar_cliente(cliente, usuario=None):
    """Salva a edição e registra só os campos que mudaram."""
    antes = fotografar(Cliente.objects.get(pk=cliente.pk), CAMPOS_DO_CLIENTE)
    cliente.save()
    alteracoes = diferencas(antes, fotografar(cliente, CAMPOS_DO_CLIENTE))
    if alteracoes:
        registrar_alteracao(
            loja=cliente.loja, usuario=usuario, acao=Acao.CLIENTE_EDITADO, descricao=cliente.nome,
            detalhes={'alteracoes': alteracoes},
        )
    return cliente


@transaction.atomic
def registrar_pagamento(cliente, *, valor, forma_pagamento='', observacao='', usuario=None):
    """Abate `valor` do saldo do cliente na caderneta da loja dele."""
    pagamento = PagamentoCliente.objects.create(
        loja=cliente.loja,
        cliente=cliente,
        valor=valor,
        forma_pagamento=forma_pagamento,
        observacao=observacao or OBSERVACAO_PADRAO_PAGAMENTO,
    )
    registrar_alteracao(
        loja=cliente.loja, usuario=usuario, acao=Acao.PAGAMENTO_REGISTRADO,
        descricao=f"{cliente.nome} · {reais(pagamento.valor)} · {pagamento.get_forma_pagamento_display() or 'forma não informada'}",
        detalhes={'observacao': pagamento.observacao},
    )
    return pagamento
