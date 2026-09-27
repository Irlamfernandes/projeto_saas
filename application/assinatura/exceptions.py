from application.exceptions import RegraDeNegocioError


class AssinaturaError(RegraDeNegocioError):
    """Erro de regra de negócio na renovação do plano."""


class PlanoIndisponivel(AssinaturaError):
    def __init__(self):
        super().__init__("Este plano não está mais disponível. Escolha outro.")


class PixRecusado(AssinaturaError):
    def __init__(self, motivo):
        detalhe = f" ({motivo})" if motivo else ""
        super().__init__(f"O Mercado Pago não aceitou gerar o Pix{detalhe}. Confira o e-mail e tente de novo.")


class PagamentoIndisponivel(AssinaturaError):
    def __init__(self):
        super().__init__("Não foi possível falar com o Mercado Pago agora. Tente de novo em instantes.")
