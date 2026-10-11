"""Variações do produto (Azul P, Branca M, Chocolate...): salvas junto com o produto, cada uma com o seu estoque."""
from application.auditoria.services import fotografar
from application.produtos.exceptions import VariacaoMudou, VariacaoNaoEncontrada, VariacaoNaoEscolhida
from infrastructure.models import Variacao

CAMPOS_DA_VARIACAO = ('nome', 'acrescimo', 'quantidade_estoque')


def salvar_variacoes(produto, variacoes):
    """Deixa o produto com exatamente estas variações: as que têm id são atualizadas, as sem id são criadas e as
    que sumiram da lista são excluídas (as vendas antigas guardam o nome delas)."""
    existentes = {variacao.pk: variacao for variacao in produto.variacoes.all()}
    ids = {dados['id'] for dados in variacoes if dados['id']}
    if not ids <= set(existentes):
        raise VariacaoNaoEncontrada()
    produto.variacoes.exclude(pk__in=ids).delete()
    _liberar_nomes_trocados(existentes, variacoes)
    for dados in variacoes:
        variacao = existentes.get(dados['id']) or Variacao(produto=produto)
        variacao.nome = dados['nome']
        variacao.acrescimo = dados['acrescimo']
        variacao.quantidade_estoque = dados['quantidade']
        variacao.save()


def _liberar_nomes_trocados(existentes, variacoes):
    """Quem troca de nome ganha antes um nome provisório: "Azul" virando "Branca" e "Branca" virando "Azul" na
    mesma edição não esbarram na regra de um nome por produto."""
    for dados in variacoes:
        variacao = existentes.get(dados['id'])
        if variacao and variacao.nome != dados['nome']:
            variacao.nome = f"#{variacao.pk}"
            variacao.save(update_fields=['nome'])


def resumo_das_variacoes(produto):
    """Para o histórico: [{'nome': 'Azul P', 'acrescimo': '0.00', 'quantidade_estoque': '10.00'}, ...]."""
    return [fotografar(variacao, CAMPOS_DA_VARIACAO) for variacao in produto.variacoes.all()]


def travar_variacoes(ids_dos_produtos):
    """{id do produto: {id da variação: variação}}, travadas sempre na mesma ordem (duas vendas ao mesmo tempo não
    se bloqueiam uma à outra)."""
    variacoes = {}
    for variacao in Variacao.objects.select_for_update().filter(produto__in=ids_dos_produtos).order_by('pk'):
        variacoes.setdefault(variacao.produto_id, {})[variacao.pk] = variacao
    return variacoes


def escolher_variacao(produto, variacao_id, variacoes):
    """`variacoes`: {id: variação} do produto. Produto com variações exige uma delas; sem variações, nenhuma."""
    if variacao_id is None:
        if variacoes:
            raise VariacaoNaoEscolhida(produto)
        return None
    variacao = variacoes.get(variacao_id)
    if variacao is None:
        raise VariacaoMudou(produto)
    return variacao


def opcoes_do_item(variacao):
    """O que o item da venda guarda para mostrar ao lado do nome: 'Camiseta (Azul P)'."""
    return [{'nome': 'Variação', 'valor': variacao.nome}] if variacao else []
