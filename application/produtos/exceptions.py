from application.exceptions import RegraDeNegocioError


class ProdutoError(RegraDeNegocioError):
    """Erro de regra de negócio no cadastro de produtos."""


class ProdutoSemLoja(ProdutoError):
    def __init__(self):
        super().__init__("Superusuários devem associar o produto a uma loja específica.")


class FalhaNoEnvioDeImagem(ProdutoError):
    def __init__(self):
        super().__init__("Não foi possível enviar as imagens agora. Nada foi salvo; tente novamente.")
