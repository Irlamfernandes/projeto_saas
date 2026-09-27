"""Transforma os detalhes guardados no registro de alterações em frases legíveis."""
from datetime import date
from decimal import Decimal, InvalidOperation
from django import template
from infrastructure.utils.formatacao import reais

register = template.Library()

ROTULOS = {
    'nome': 'Nome', 'codigo_interno': 'Código', 'categoria': 'Categoria', 'preco_custo': 'Preço de custo',
    'preco_venda': 'Preço de venda', 'quantidade_estoque': 'Estoque', 'descricao': 'Descrição',
    'telefone': 'Telefone', 'email': 'E-mail', 'endereco': 'Endereço',
}
CAMPOS_EM_REAIS = {'preco_custo', 'preco_venda'}
VAZIO = '(vazio)'
ICONES_POR_ACAO = {'venda_cancelada': 'i-x', 'marca_alterada': 'i-foto', 'plano_renovado': 'i-calendario'}
ICONES_POR_ASSUNTO = {
    'venda': 'i-venda', 'pagamento': 'i-carteira', 'produto': 'i-produto', 'cliente': 'i-clientes', 'lembrete': 'i-mensagem',
}


@register.filter
def icone_da_acao(acao):
    """Ícone do registro: primeiro a ação exata, depois o assunto ('venda_editada' -> venda)."""
    if acao in ICONES_POR_ACAO:
        return ICONES_POR_ACAO[acao]
    return ICONES_POR_ASSUNTO.get(acao.split('_')[0], 'i-historico')


@register.filter
def detalhes_legiveis(detalhes):
    detalhes = detalhes or {}
    linhas = [_mudanca(campo, antes, depois) for campo, (antes, depois) in detalhes.get('alteracoes', {}).items()]
    if 'antes' in detalhes:
        linhas += [f"Antes: {_resumo_da_venda(detalhes['antes'])}", f"Depois: {_resumo_da_venda(detalhes['depois'])}"]
    if 'venda' in detalhes:
        linhas.append(_resumo_da_venda(detalhes['venda']))
    if detalhes.get('motivo'):
        linhas.append(f"Motivo: {detalhes['motivo']}")
    if 'fotos' in detalhes:
        linhas.append(_fotos(detalhes['fotos']))
    if detalhes.get('observacao'):
        linhas.append(f"Observação: {detalhes['observacao']}")
    if 'vencimento' in detalhes:
        linhas.append(_vencimento(*detalhes['vencimento']))
    return linhas


def _mudanca(campo, antes, depois):
    return f"{ROTULOS.get(campo, campo)}: {_valor(campo, antes)} → {_valor(campo, depois)}"


def _valor(campo, valor):
    if valor in (None, ''):
        return VAZIO
    if campo in CAMPOS_EM_REAIS:
        return _reais(valor)
    return str(valor)


def _reais(valor):
    return reais(valor) if _e_numero(valor) else str(valor)


def _e_numero(valor):
    try:
        Decimal(str(valor))
    except InvalidOperation:
        return False
    return True


def _resumo_da_venda(venda):
    itens = ', '.join(
        f"{item['quantidade']}× {item['produto']} ({_reais(item['preco_unitario'])})" for item in venda.get('itens', [])
    )
    partes = [venda.get('cliente') or 'Balcão', itens or 'sem itens', f"total {_reais(venda.get('total'))}"]
    if venda.get('forma_pagamento'):
        partes.append(venda['forma_pagamento'])
    pago = venda.get('pago_no_ato') or []
    if pago:
        partes.append(f"pago no ato {', '.join(_reais(v) for v in pago)}")
    vencimentos = venda.get('vencimentos') or []
    if vencimentos:
        partes.append(f"vence {', '.join(_data(v) for v in vencimentos)}")
    return ' · '.join(partes)


def _vencimento(anterior, novo):
    return f"Vencimento: {_data(anterior)} → {_data(novo)}"


def _data(iso):
    try:
        return date.fromisoformat(iso).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return str(iso)


def _fotos(fotos):
    if isinstance(fotos, int):
        return f"Fotos: {fotos}"
    return f"Fotos: {fotos.get('adicionadas', 0)} adicionada(s), {fotos.get('removidas', 0)} removida(s)"
