from application.exceptions import RegraDeNegocioError
from infrastructure.utils.formatacao import quantidade


class VendaError(RegraDeNegocioError):
    """Erro de regra de negócio no fluxo de vendas."""


class ProdutoNaoEncontrado(VendaError):
    def __init__(self):
        super().__init__("Um dos produtos escolhidos não foi encontrado nesta loja. Busque de novo e tente outra vez.")


class EstoqueInsuficiente(VendaError):
    def __init__(self, produto):
        disponivel = quantidade(produto.quantidade_estoque, produto.unidade)
        super().__init__(f"Estoque insuficiente para '{produto.nome}'. Disponível: {disponivel}")


class QuantidadeFracionada(VendaError):
    def __init__(self, produto):
        if produto.casas_decimais:
            detalhe = f"use no máximo {produto.casas_decimais} casas depois da vírgula"
        else:
            detalhe = "use só números inteiros"
        super().__init__(f"'{produto.nome}' é vendido por {produto.get_unidade_display().lower()}: {detalhe}.")


class VendaSemItens(VendaError):
    def __init__(self):
        super().__init__("Adicione pelo menos um produto à venda.")


class VendaSemLoja(VendaError):
    def __init__(self):
        super().__init__("Venda de balcão precisa de uma loja: entre com um usuário de loja ou escolha um cliente.")


class SenhaIncorreta(VendaError):
    def __init__(self):
        super().__init__("Senha incorreta. A venda não foi cancelada.")


class OpcaoNaoEscolhida(VendaError):
    def __init__(self, produto, opcao):
        super().__init__(f"Escolha a opção \"{opcao}\" de '{produto.nome}'.")


class OpcoesMudaram(VendaError):
    def __init__(self, produto):
        super().__init__(f"As opções de '{produto.nome}' mudaram. Tire o produto da venda e adicione de novo.")
