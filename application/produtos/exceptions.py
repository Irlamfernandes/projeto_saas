from application.exceptions import RegraDeNegocioError


class ProdutoError(RegraDeNegocioError):
    """Erro de regra de negócio no cadastro de produtos."""


class ProdutoSemLoja(ProdutoError):
    def __init__(self):
        super().__init__("Superusuários devem associar o produto a uma loja específica.")


class FalhaNoEnvioDeImagem(ProdutoError):
    def __init__(self):
        super().__init__("Não foi possível enviar as imagens agora. Nada foi salvo; tente novamente.")


class ImagemInvalida(ProdutoError):
    def __init__(self, nome):
        super().__init__(f"Não foi possível ler a imagem '{nome}'. Envie uma foto JPG, PNG, WEBP ou HEIC.")


class LimiteDeFotosExcedido(ProdutoError):
    def __init__(self, maximo, disponiveis):
        if disponiveis:
            detalhe = f"Dá para adicionar mais {disponiveis}."
        else:
            detalhe = "Remova alguma antes de adicionar outra."
        super().__init__(f"Cada produto pode ter no máximo {maximo} fotos. {detalhe}")


class VariacaoNaoEncontrada(ProdutoError):
    def __init__(self):
        super().__init__("Uma das variações não existe mais. Abra o produto de novo e refaça a alteração.")


class VariacaoNaoEscolhida(ProdutoError):
    def __init__(self, produto):
        super().__init__(f"Escolha a variação de '{produto.nome}' (ex.: cor, tamanho).")


class VariacaoMudou(ProdutoError):
    def __init__(self, produto):
        super().__init__(f"As variações de '{produto.nome}' mudaram. Escolha o produto de novo.")
