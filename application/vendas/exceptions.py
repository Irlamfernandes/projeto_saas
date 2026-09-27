from application.exceptions import RegraDeNegocioError


class VendaError(RegraDeNegocioError):
    """Erro de regra de negócio no fluxo de vendas."""


class ProdutoNaoEncontrado(VendaError):
    def __init__(self):
        super().__init__("Um dos produtos escolhidos não foi encontrado nesta loja. Busque de novo e tente outra vez.")


class EstoqueInsuficiente(VendaError):
    def __init__(self, produto):
        super().__init__(
            f"Estoque insuficiente para '{produto.nome}'. Disponível: {produto.quantidade_estoque}."
        )


class VendaSemItens(VendaError):
    def __init__(self):
        super().__init__("Adicione pelo menos um produto à venda.")


class VendaSemLoja(VendaError):
    def __init__(self):
        super().__init__("Venda de balcão precisa de uma loja: entre com um usuário de loja ou escolha um cliente.")


class SenhaIncorreta(VendaError):
    def __init__(self):
        super().__init__("Senha incorreta. A venda não foi cancelada.")
