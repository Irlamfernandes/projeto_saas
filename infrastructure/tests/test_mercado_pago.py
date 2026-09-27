from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException
from infrastructure.pagamentos.mercado_pago import (
    MercadoPago, MercadoPagoError, MercadoPagoNaoConfigurado, MercadoPagoRecusou, PixGerado,
)

EXPIRA = datetime(2026, 9, 27, 10, 30, tzinfo=ZoneInfo('America/Sao_Paulo'))
RESPOSTA_PIX = {
    'id': 123456789, 'status': 'pending',
    'point_of_interaction': {'transaction_data': {'qr_code': '000201PIX', 'qr_code_base64': 'iVBORw0KGgo='}},
}


def resposta(status=200, dados=None):
    item = MagicMock(status_code=status)
    if isinstance(dados, Exception):
        item.json.side_effect = dados
    else:
        item.json.return_value = dados
    return item


@patch('infrastructure.pagamentos.mercado_pago.requests')
class CriarPixTest(SimpleTestCase):

    def setUp(self):
        self.mp = MercadoPago(" TEST-token ")

    def criar(self):
        return self.mp.criar_pix(valor=Decimal('0.01'), descricao="Plano 30 dias - Padaria", email="Ana.Souza99@Exemplo.com",
                                 referencia="ref-1", expira_em=EXPIRA)

    def test_gera_o_pix_com_referencia_idempotencia_e_expiracao(self, requests_mock):
        requests_mock.post.return_value = resposta(201, RESPOSTA_PIX)

        pix = self.criar()

        self.assertEqual(pix, PixGerado('123456789', '000201PIX', 'iVBORw0KGgo='))
        chamada = requests_mock.post.call_args
        self.assertEqual(chamada.args, (MercadoPago.URL,))
        self.assertEqual(chamada.kwargs['headers'], {'Authorization': 'Bearer TEST-token', 'X-Idempotency-Key': 'ref-1'})
        self.assertEqual(chamada.kwargs['json'], {
            'transaction_amount': 0.01, 'description': "Plano 30 dias - Padaria", 'payment_method_id': 'pix',
            'payer': {'email': "Ana.Souza99@Exemplo.com"}, 'external_reference': 'ref-1',
            'date_of_expiration': '2026-09-27T10:30:00.000-03:00',
        })
        self.assertEqual(chamada.kwargs['timeout'], MercadoPago.TIMEOUT_SEGUNDOS)

    def test_recusa_traz_a_explicacao_do_mercado_pago(self, requests_mock):
        requests_mock.post.return_value = resposta(400, {'message': 'bad_request', 'cause': [{'code': 1, 'description': 'payer.email must be valid'}]})
        with self.assertRaisesMessage(MercadoPagoRecusou, 'payer.email must be valid'):
            self.criar()

    def test_recusa_sem_causas_usa_a_mensagem_ou_fica_vazia(self, requests_mock):
        requests_mock.post.return_value = resposta(400, {'message': 'invalid amount'})
        with self.assertRaisesMessage(MercadoPagoRecusou, 'invalid amount'):
            self.criar()
        requests_mock.post.return_value = resposta(422, ValueError())
        with self.assertRaises(MercadoPagoRecusou):
            self.criar()

    def test_falhas_viram_mercado_pago_error(self, requests_mock):
        requests_mock.RequestException = RequestException
        casos = {
            'rede': {'side_effect': RequestException('caiu')},
            'status': {'side_effect': None, 'return_value': resposta(500, {})},
            'json': {'side_effect': None, 'return_value': resposta(201, ValueError())},
            'sem pix': {'side_effect': None, 'return_value': resposta(201, {'id': 1})},
        }
        for caso, comportamento in casos.items():
            with self.subTest(caso), self.assertRaises(MercadoPagoError):
                requests_mock.post.configure_mock(**comportamento)
                self.criar()

    def test_status_inesperado_fica_no_log_sem_o_token(self, requests_mock):
        requests_mock.post.return_value = resposta(500, {})
        with self.assertRaises(MercadoPagoError), self.assertLogs('infrastructure.pagamentos.mercado_pago', 'ERROR') as logs:
            self.criar()
        self.assertNotIn('TEST-token', ' '.join(logs.output))

    def test_sem_token_nao_chama_a_api(self, requests_mock):
        with self.assertRaises(MercadoPagoNaoConfigurado):
            MercadoPago('').criar_pix(valor=1, descricao='', email='', referencia='', expira_em=EXPIRA)
        requests_mock.post.assert_not_called()


@patch('infrastructure.pagamentos.mercado_pago.requests')
class ConsultarTest(SimpleTestCase):

    def test_le_status_valor_moeda_e_referencia(self, requests_mock):
        requests_mock.get.return_value = resposta(200, {
            'id': 123, 'status': 'approved', 'transaction_amount': 0.01, 'currency_id': 'BRL', 'external_reference': 'ref-1',
        })

        pagamento = MercadoPago('tok').consultar('123')

        self.assertEqual(requests_mock.get.call_args.args, (f"{MercadoPago.URL}/123",))
        self.assertEqual((pagamento.pagamento_id, pagamento.valor, pagamento.moeda, pagamento.referencia),
                         ('123', Decimal('0.01'), 'BRL', 'ref-1'))
        self.assertTrue(pagamento.aprovado)

    def test_campos_ausentes_nao_quebram(self, requests_mock):
        requests_mock.get.return_value = resposta(200, {'status': 'pending', 'external_reference': None})
        pagamento = MercadoPago('tok').consultar('1')
        self.assertEqual((pagamento.valor, pagamento.referencia, pagamento.moeda), (None, '', ''))
        self.assertFalse(pagamento.aprovado)


class FromSettingsTest(SimpleTestCase):

    @override_settings(MERCADO_PAGO_ACCESS_TOKEN='TEST-do-settings')
    @patch('infrastructure.pagamentos.mercado_pago.requests')
    def test_usa_o_token_do_settings(self, requests_mock):
        requests_mock.get.return_value = resposta(200, {'status': 'pending'})
        MercadoPago.from_settings().consultar('1')
        self.assertEqual(requests_mock.get.call_args.kwargs['headers']['Authorization'], 'Bearer TEST-do-settings')
