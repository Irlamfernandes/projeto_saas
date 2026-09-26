from application.exceptions import RegraDeNegocioError


class VendaError(RegraDeNegocioError):
    """Erro de regra de negócio no fluxo de vendas."""


class ProdutoNaoEncontrado(VendaError):
    def __init__(self, termo):
        super().__init__(f"Produto '{termo}' não foi encontrado pelo Código Interno ou Nome.")


class EstoqueInsuficiente(VendaError):
    def __init__(self, produto):
        super().__init__(
            f"Estoque insuficiente para '{produto.nome}'. Disponível: {produto.quantidade_estoque}."
        )
