from django.db import transaction
from application.auditoria.services import diferencas, fotografar, registrar_alteracao
from application.clientes.exceptions import ClienteComSaldo, ClienteSemLoja, SenhaNaoConfere
from infrastructure.models import Acao, Cliente, PagamentoCliente, RegistroDeAlteracao
from infrastructure.utils.formatacao import reais

OBSERVACAO_PADRAO_PAGAMENTO = 'Pagamento na caderneta'
CAMPOS_DO_CLIENTE = ('nome', 'telefone', 'email', 'endereco')


@transaction.atomic
def cadastrar_cliente(cliente, usuario=None):
    if cliente.loja_id is None:
        raise ClienteSemLoja()
    cliente.save()
    registrar_alteracao(
        loja=cliente.loja, usuario=usuario, acao=Acao.CLIENTE_CADASTRADO, descricao=cliente.nome,
        detalhes={'cliente': fotografar(cliente, CAMPOS_DO_CLIENTE)}, clientes=[cliente],
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
            detalhes={'alteracoes': alteracoes}, clientes=[cliente],
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
        detalhes={'observacao': pagamento.observacao}, clientes=[cliente],
    )
    return pagamento


REMOVIDO = '(removido)'


@transaction.atomic
def apagar_dados_pessoais(cliente, *, usuario, senha):
    """Direito do titular (LGPD): nome, telefone, e-mail e endereço saem do cadastro e do histórico.

    As vendas e os pagamentos ficam (a loja precisa deles nas contas e nos relatórios), mas passam a ser de
    "Cliente removido #id". Só com a senha de quem pede e com a caderneta zerada.
    """
    if not usuario.check_password(senha):
        raise SenhaNaoConfere()
    saldo = cliente.saldo_geral
    if saldo:
        raise ClienteComSaldo(saldo)

    anonimo = f"Cliente removido #{cliente.pk}"
    nomes, contatos = _valores_ja_usados(cliente)
    trocas = {**dict.fromkeys(contatos, REMOVIDO), **dict.fromkeys(nomes, anonimo)}
    for registro in RegistroDeAlteracao.objects.filter(clientes=cliente):
        registro.descricao = _trocar(registro.descricao, trocas)[:255]
        registro.detalhes = _trocar(registro.detalhes, trocas)
        registro.save(update_fields=['descricao', 'detalhes'])

    Cliente.objects.filter(pk=cliente.pk).update(nome=anonimo, telefone='', email='', endereco='')
    cliente.refresh_from_db()
    registrar_alteracao(
        loja=cliente.loja, usuario=usuario, acao=Acao.CLIENTE_ANONIMIZADO, descricao=anonimo, clientes=[cliente],
    )
    return cliente


def _valores_ja_usados(cliente):
    """Todos os nomes e contatos que o cliente já teve: os de hoje e os guardados no cadastro e nas edições."""
    nomes, contatos = {cliente.nome}, {getattr(cliente, campo) for campo in CAMPOS_DO_CLIENTE[1:]}
    proprios = RegistroDeAlteracao.objects.filter(clientes=cliente, acao__in=(Acao.CLIENTE_CADASTRADO, Acao.CLIENTE_EDITADO))
    for detalhes in proprios.values_list('detalhes', flat=True):
        foto, alteracoes = detalhes.get('cliente', {}), detalhes.get('alteracoes', {})
        nomes.update([foto.get('nome'), *alteracoes.get('nome', [])])
        for campo in CAMPOS_DO_CLIENTE[1:]:
            contatos.update([foto.get(campo), *alteracoes.get(campo, [])])
    return {nome for nome in nomes if nome}, {contato for contato in contatos if contato}


def _trocar(valor, trocas):
    """Troca os textos pessoais em qualquer nível (texto, lista, dicionário), do mais longo para o mais curto."""
    if isinstance(valor, dict):
        return {chave: _trocar(item, trocas) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [_trocar(item, trocas) for item in valor]
    if isinstance(valor, str):
        for antigo in sorted(trocas, key=len, reverse=True):
            valor = valor.replace(antigo, trocas[antigo])
    return valor
