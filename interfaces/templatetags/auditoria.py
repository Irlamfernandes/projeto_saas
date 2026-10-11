"""Transforma os detalhes guardados no registro de alterações em frases legíveis."""
from datetime import date
from decimal import Decimal, InvalidOperation
from django import template
from infrastructure.models import Unidade
from infrastructure.utils.formatacao import item as descrever_item, numero, reais

register = template.Library()

ROTULOS = {
    'nome': 'Nome', 'codigo_interno': 'Código', 'categoria': 'Categoria', 'preco_custo': 'Preço de custo',
    'preco_venda': 'Preço de venda', 'quantidade_estoque': 'Estoque', 'descricao': 'Descrição',
    'telefone': 'Telefone', 'cpf': 'CPF', 'email': 'E-mail', 'endereco': 'Endereço',
    'unidade': 'Vendido por', 'controla_estoque': 'Controla estoque', 'opcoes': 'Opções',
}
VAZIO = '(vazio)'
ICONES_POR_ACAO = {'venda_cancelada': 'i-x', 'marca_alterada': 'i-foto', 'plano_renovado': 'i-calendario'}
ICONES_POR_ASSUNTO = {
    'venda': 'i-venda', 'pagamento': 'i-carteira', 'produto': 'i-produto', 'cliente': 'i-clientes', 'lembrete': 'i-mensagem',
    'compra': 'i-produto', 'despesa': 'i-carteira', 'perda': 'i-lixeira',
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
    if detalhes.get('itens'):
        linhas.append(f"Itens: {', '.join(detalhes['itens'])}")
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
    if isinstance(valor, bool):
        return 'sim' if valor else 'não'
    return _FORMATOS.get(campo, str)(valor)


def _estoque(valor):
    return numero(valor) if _e_numero(valor) else str(valor)


def _unidade(valor):
    return Unidade(valor).label if valor in Unidade.values else str(valor)


def _opcoes(opcoes):
    return '; '.join(map(_opcao, opcoes)) or VAZIO


def _opcao(opcao):
    """'Tamanho: P, M, G (+R$ 5,00)'."""
    return f"{opcao['nome']}: {', '.join(map(_valor_da_opcao, opcao['valores']))}"


def _valor_da_opcao(valor):
    if Decimal(valor['acrescimo']):
        return f"{valor['nome']} (+{reais(valor['acrescimo'])})"
    return valor['nome']


def _reais(valor):
    return reais(valor) if _e_numero(valor) else str(valor)


def _e_numero(valor):
    try:
        Decimal(str(valor))
    except InvalidOperation:
        return False
    return True


def _resumo_da_venda(venda):
    partes = [venda.get('cliente') or 'Balcão', _itens_da_venda(venda) or 'sem itens', f"total {_reais(venda.get('total'))}"]
    return ' · '.join(partes + _complementos_da_venda(venda))


def _itens_da_venda(venda):
    return ', '.join(
        f"{descrever_item(item['quantidade'], item.get('unidade'), item['produto'])} ({_reais(item['preco_unitario'])})"
        for item in venda.get('itens', [])
    )


def _complementos_da_venda(venda):
    """Forma de pagamento, o que foi pago no ato e os vencimentos, só quando houver."""
    pago = venda.get('pago_no_ato') or []
    vencimentos = venda.get('vencimentos') or []
    complementos = [
        venda.get('forma_pagamento'),
        pago and f"pago no ato {', '.join(_reais(v) for v in pago)}",
        vencimentos and f"vence {', '.join(_data(v) for v in vencimentos)}",
    ]
    return [texto for texto in complementos if texto]


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


# Como mostrar o valor de cada campo no histórico (o resto aparece como veio).
_FORMATOS = {
    'preco_custo': _reais, 'preco_venda': _reais, 'quantidade_estoque': _estoque, 'unidade': _unidade, 'opcoes': _opcoes,
}
