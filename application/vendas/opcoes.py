"""Opções do produto na venda (ex.: Tamanho G, Sabor chocolate): conferir a escolha e somar o acréscimo no preço.

As escolhas chegam como {nome da opção: valor}. O item da venda guarda [{'nome': ..., 'valor': ...}] na ordem do produto.
"""
from decimal import Decimal
from application.vendas.exceptions import OpcaoNaoEscolhida, OpcoesMudaram


def chave(escolhas):
    """Igual para as mesmas escolhas em qualquer ordem: junta itens iguais e acha o item que já estava na venda."""
    return tuple(sorted(escolhas.items()))


def escolhas_do_item(opcoes):
    """[{'nome': 'Tamanho', 'valor': 'G'}] -> {'Tamanho': 'G'}."""
    return {opcao['nome']: opcao['valor'] for opcao in opcoes}


def escolher(produto, escolhas):
    """Cada opção do produto precisa de um valor que existe nela. Retorna (opções escolhidas, acréscimo total)."""
    if set(escolhas) - {opcao['nome'] for opcao in produto.opcoes}:
        raise OpcoesMudaram(produto)
    escolhidas, acrescimo = [], Decimal('0')
    for opcao in produto.opcoes:
        valores = {valor['nome']: Decimal(valor['acrescimo']) for valor in opcao['valores']}
        valor = escolhas.get(opcao['nome'])
        if valor not in valores:
            raise OpcaoNaoEscolhida(produto, opcao['nome'])
        escolhidas.append({'nome': opcao['nome'], 'valor': valor})
        acrescimo += valores[valor]
    return escolhidas, acrescimo
