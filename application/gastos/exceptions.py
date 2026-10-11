from application.exceptions import RegraDeNegocioError


class GastoError(RegraDeNegocioError):
    """Erro de regra de negócio em compras, despesas e perdas."""


class CompraSemItens(GastoError):
    def __init__(self):
        super().__init__("Adicione pelo menos um produto à compra.")


class ProdutoDeOutraLoja(GastoError):
    def __init__(self):
        super().__init__("Um dos produtos escolhidos não foi encontrado nesta loja.")


class QuantidadeInvalidaParaUnidade(GastoError):
    def __init__(self, produto):
        super().__init__(f"'{produto.nome}' é contado por {produto.get_unidade_display().lower()}: confira a quantidade.")


class EstoqueNaoCobreAPerda(GastoError):
    def __init__(self, nome, disponivel):
        super().__init__(f"'{nome}' tem só {disponivel} em estoque.")


class EstoqueJaUsado(GastoError):
    def __init__(self, nome):
        super().__init__(
            f"Não dá para excluir: parte do '{nome}' desta compra já foi vendida ou baixada. "
            "Acerte o estoque no cadastro do produto, se precisar."
        )
