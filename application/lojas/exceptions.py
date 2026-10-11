from application.exceptions import RegraDeNegocioError


class LojaError(RegraDeNegocioError):
    """Erro de regra de negócio nas configurações da loja."""


class UsuarioSemLoja(LojaError):
    def __init__(self):
        super().__init__("Este usuário não está ligado a nenhuma loja.")


class MarcaInvalida(LojaError):
    def __init__(self):
        super().__init__("Não foi possível ler a imagem da marca. Envie uma imagem JPG, PNG, WEBP ou HEIC.")


class FalhaNoEnvioDaMarca(LojaError):
    def __init__(self):
        super().__init__("Não foi possível enviar a marca agora. Nada foi alterado; tente novamente.")
