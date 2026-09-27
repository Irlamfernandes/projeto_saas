"""Cliente mínimo da API de pagamentos do Mercado Pago: gerar Pix e consultar um pagamento.

O token fica só no servidor e nunca vai para a página nem para os logs.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MercadoPagoError(Exception):
    """Falha ao falar com o Mercado Pago (rede, configuração ou resposta inesperada)."""


class MercadoPagoNaoConfigurado(MercadoPagoError):
    """Token ausente no .env."""


class MercadoPagoRecusou(MercadoPagoError):
    """O Mercado Pago recusou o pedido (ex.: e-mail inválido); a mensagem vem dele."""


@dataclass(frozen=True)
class PixGerado:
    pagamento_id: str
    copia_e_cola: str
    qr_code_base64: str


@dataclass(frozen=True)
class PagamentoConsultado:
    pagamento_id: str
    status: str
    valor: Decimal | None
    moeda: str
    referencia: str

    @property
    def aprovado(self):
        return self.status == 'approved'


class MercadoPago:
    URL = 'https://api.mercadopago.com/v1/payments'
    TIMEOUT_SEGUNDOS = 15

    def __init__(self, token):
        self._token = (token or '').strip()

    @classmethod
    def from_settings(cls):
        return cls(settings.MERCADO_PAGO_ACCESS_TOKEN)

    def criar_pix(self, *, valor, descricao, email, referencia, expira_em):
        """`referencia` vai como external_reference e como chave de idempotência (repetir não duplica o Pix)."""
        corpo = {
            'transaction_amount': float(valor),
            'description': descricao,
            'payment_method_id': 'pix',
            'payer': {'email': email},
            'external_reference': referencia,
            'date_of_expiration': expira_em.isoformat(timespec='milliseconds'),
        }
        dados = self._pedir('post', self.URL, json=corpo, headers={'X-Idempotency-Key': referencia})
        try:
            transacao = dados['point_of_interaction']['transaction_data']
            return PixGerado(str(dados['id']), transacao['qr_code'], transacao['qr_code_base64'])
        except (KeyError, TypeError) as erro:
            raise MercadoPagoError("Resposta do Mercado Pago sem os dados do Pix.") from erro

    def consultar(self, pagamento_id):
        dados = self._pedir('get', f"{self.URL}/{pagamento_id}")
        return PagamentoConsultado(
            pagamento_id=str(dados.get('id', '')),
            status=str(dados.get('status', '')),
            valor=_decimal(dados.get('transaction_amount')),
            moeda=str(dados.get('currency_id', '')),
            referencia=str(dados.get('external_reference') or ''),
        )

    def _pedir(self, metodo, url, headers=None, **kwargs):
        if not self._token:
            raise MercadoPagoNaoConfigurado("MERCADO_PAGO_ACCESS_TOKEN não configurado no .env.")
        try:
            resposta = getattr(requests, metodo)(
                url, headers={'Authorization': f"Bearer {self._token}", **(headers or {})},
                timeout=self.TIMEOUT_SEGUNDOS, **kwargs,
            )
        except requests.RequestException as erro:
            raise MercadoPagoError(f"Erro de comunicação com o Mercado Pago: {erro}") from erro

        if resposta.status_code in (400, 422):
            raise MercadoPagoRecusou(_mensagem_de_erro(resposta))
        if resposta.status_code not in (200, 201):
            logger.error("Mercado Pago respondeu %s em %s %s", resposta.status_code, metodo.upper(), url)
            raise MercadoPagoError(f"Mercado Pago respondeu {resposta.status_code}.")
        try:
            return resposta.json()
        except ValueError as erro:
            raise MercadoPagoError("Resposta do Mercado Pago ilegível.") from erro


def _mensagem_de_erro(resposta):
    try:
        dados = resposta.json()
    except ValueError:
        return ''
    causas = [c.get('description', '') for c in dados.get('cause') or [] if isinstance(c, dict)]
    return '; '.join(filter(None, causas)) or str(dados.get('message', ''))


def _decimal(valor):
    try:
        return Decimal(str(valor)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return None
