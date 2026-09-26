from application.exceptions import RegraDeNegocioError


class ClienteSemLoja(RegraDeNegocioError):
    def __init__(self):
        super().__init__("Superusuários devem associar o cliente a uma loja específica.")
