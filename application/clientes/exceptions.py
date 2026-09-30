from application.exceptions import RegraDeNegocioError
from infrastructure.utils.formatacao import reais


class ClienteSemLoja(RegraDeNegocioError):
    def __init__(self):
        super().__init__("Superusuários devem associar o cliente a uma loja específica.")


class SenhaNaoConfere(RegraDeNegocioError):
    def __init__(self):
        super().__init__("Senha incorreta. Os dados do cliente não foram apagados.")


class ClienteComSaldo(RegraDeNegocioError):
    """A LGPD permite guardar os dados enquanto houver valor a acertar (cobrar ou devolver)."""

    def __init__(self, saldo):
        situacao = f"tem {reais(-saldo)} de crédito" if saldo.is_signed() else f"deve {reais(saldo)}"  # negativo = crédito
        super().__init__(
            f"Este cliente ainda {situacao} na caderneta. Acerte o saldo antes de apagar os dados: "
            "a lei permite guardá-los enquanto houver valor a receber ou a devolver."
        )
