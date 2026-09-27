from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from application.assinatura.exceptions import PagamentoIndisponivel, PixRecusado, PlanoIndisponivel
from application.assinatura.selectors import em_teste_gratis, planos_disponiveis
from application.assinatura.services import (
    MARGEM_APOS_EXPIRAR, MINUTOS_PARA_PAGAR, conferir_cobranca, conferir_pendentes, gerar_cobranca,
)
from infrastructure.models import Acao, Cobranca, LojaModel, Plano, RegistroDeAlteracao, StatusDaCobranca
from infrastructure.pagamentos.mercado_pago import MercadoPagoError, MercadoPagoRecusou
from tests.apoio import MercadoPagoFalso

HOJE = timezone.localdate()


class AssinaturaTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria", vencimento=HOJE + timedelta(days=5))
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja, deve_trocar_senha=False)
        self.plano_30 = Plano.objects.get(nome="30 dias")
        self.mp = MercadoPagoFalso()

    def gerar(self, plano=None, email="Ana.Souza99@Exemplo.com", gateway=None):
        return gerar_cobranca(self.loja, plano or self.plano_30, email=email, usuario=self.usuario, gateway=gateway or self.mp)


class PlanosIniciaisTest(TestCase):

    def test_quatro_planos_de_teste_a_um_centavo(self):
        self.assertEqual(
            [(p.nome, p.quantidade, p.unidade, p.preco) for p in planos_disponiveis()],
            [("30 dias", 30, 'dias', Decimal('0.01')), ("90 dias", 90, 'dias', Decimal('0.01')),
             ("6 meses", 6, 'meses', Decimal('0.01')), ("12 meses", 12, 'meses', Decimal('0.01'))],
        )

    def test_plano_desativado_sai_da_lista(self):
        Plano.objects.filter(nome="90 dias").update(ativo=False)
        self.assertNotIn("90 dias", [p.nome for p in planos_disponiveis()])


class GerarCobrancaTest(AssinaturaTestCase):

    def test_cria_a_cobranca_pendente_com_o_pix_e_copia_do_plano(self):
        cobranca = self.gerar()

        self.assertEqual(cobranca.status, StatusDaCobranca.PENDENTE)
        self.assertEqual((cobranca.plano_nome, cobranca.quantidade, cobranca.unidade, cobranca.valor),
                         ("30 dias", 30, 'dias', Decimal('0.01')))
        self.assertEqual((cobranca.pagamento_id, cobranca.pix_copia_e_cola, cobranca.pix_qr_code),
                         ('1001', '000201PIX1001', 'iVBORw0KGgo='))
        self.assertAlmostEqual(cobranca.expira_em, timezone.now() + timedelta(minutes=MINUTOS_PARA_PAGAR), delta=timedelta(seconds=5))
        pedido = self.mp.pix_criados[0]
        self.assertEqual(pedido['referencia'], str(cobranca.referencia))
        self.assertEqual(pedido['descricao'], "Plano 30 dias - Padaria")

    def test_email_fica_salvo_exatamente_como_digitado(self):
        self.gerar(email="Ana.Souza99@Exemplo.com")
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.email_cobranca, "Ana.Souza99@Exemplo.com")
        self.assertEqual(self.mp.pix_criados[0]['email'], "Ana.Souza99@Exemplo.com")

    def test_gerar_nao_mexe_no_vencimento(self):
        self.gerar()
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.vencimento, HOJE + timedelta(days=5))

    def test_reaproveita_o_pix_aberto_do_mesmo_plano_e_email(self):
        primeira = self.gerar()
        self.assertEqual(self.gerar(), primeira)
        self.assertEqual(len(self.mp.pix_criados), 1)

    def test_gera_outro_pix_se_mudar_o_plano_o_email_ou_estiver_perto_de_expirar(self):
        primeira = self.gerar()
        self.gerar(plano=Plano.objects.get(nome="90 dias"))
        self.gerar(email="outro@exemplo.com")
        Cobranca.objects.filter(pk=primeira.pk).update(expira_em=timezone.now() + timedelta(minutes=2))
        self.gerar()
        self.assertEqual(len(self.mp.pix_criados), 4)

    def test_plano_desativado_e_recusado(self):
        self.plano_30.ativo = False
        with self.assertRaises(PlanoIndisponivel):
            self.gerar()
        self.assertEqual(self.mp.pix_criados, [])

    def test_recusa_do_mercado_pago_nao_salva_nada(self):
        with self.assertRaisesMessage(PixRecusado, "(payer.email must be valid)"):
            self.gerar(gateway=MercadoPagoFalso(erro_ao_criar=MercadoPagoRecusou("payer.email must be valid")))
        self.assertFalse(Cobranca.objects.exists())
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.email_cobranca, '')

    def test_mercado_pago_fora_do_ar(self):
        with self.assertRaises(PagamentoIndisponivel), self.assertLogs('application.assinatura.services', 'ERROR'):
            self.gerar(gateway=MercadoPagoFalso(erro_ao_criar=MercadoPagoError("timeout")))
        self.assertFalse(Cobranca.objects.exists())

    def test_sem_gateway_usa_o_do_settings(self):
        with patch('application.assinatura.services.MercadoPago.from_settings', return_value=self.mp):
            gerar_cobranca(self.loja, self.plano_30, email="a@b.com", usuario=None)
        self.assertEqual(len(self.mp.pix_criados), 1)


class ConferirCobrancaTest(AssinaturaTestCase):

    def setUp(self):
        super().setUp()
        self.cobranca = self.gerar()

    def conferir(self):
        return conferir_cobranca(self.cobranca, gateway=self.mp)

    def assertVencimento(self, esperado):
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.vencimento, esperado)

    def test_pagamento_aprovado_que_confere_renova_somando_ao_vencimento(self):
        self.mp.aprovar(self.cobranca)

        cobranca = self.conferir()

        self.assertEqual(cobranca.status, StatusDaCobranca.PAGA)
        self.assertVencimento(HOJE + timedelta(days=35))
        self.assertEqual((cobranca.vencimento_anterior, cobranca.vencimento_novo), (HOJE + timedelta(days=5), HOJE + timedelta(days=35)))
        self.assertIsNotNone(cobranca.paga_em)

    def test_registra_a_renovacao_no_historico(self):
        self.mp.aprovar(self.cobranca)
        self.conferir()
        registro = RegistroDeAlteracao.objects.get(acao=Acao.PLANO_RENOVADO)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.descricao, f"Plano 30 dias · R$ 0,01 · até {HOJE + timedelta(days=35):%d/%m/%Y}")

    def test_conferir_de_novo_nao_soma_o_tempo_duas_vezes(self):
        self.mp.aprovar(self.cobranca)
        paga = self.conferir()
        conferir_cobranca(paga, gateway=self.mp)
        conferir_cobranca(Cobranca.objects.get(pk=self.cobranca.pk), gateway=self.mp)

        self.assertVencimento(HOJE + timedelta(days=35))
        self.assertEqual(len(self.mp.consultas), 1)
        self.assertEqual(RegistroDeAlteracao.objects.filter(acao=Acao.PLANO_RENOVADO).count(), 1)

    def test_corrida_entre_duas_conferencias_so_renova_uma_vez(self):
        """Duas abas com a mesma cobrança antiga em memória: a segunda encontra a cobrança já paga."""
        copia_antiga = Cobranca.objects.get(pk=self.cobranca.pk)
        self.mp.aprovar(self.cobranca)
        self.conferir()
        conferir_cobranca(copia_antiga, gateway=self.mp)
        self.assertVencimento(HOJE + timedelta(days=35))

    def test_aprovado_que_nao_confere_nao_renova(self):
        """Só vale o pagamento desta cobrança, com o valor certo, em reais."""
        casos = {
            'valor menor': {'valor': Decimal('0.00')},
            'outra referência': {'referencia': 'outra-cobranca'},
            'outra moeda': {'moeda': 'USD'},
            'outro pagamento': {'pagamento_id': '999'},
            'sem valor': {'valor': None},
        }
        for caso, diferenca in casos.items():
            with self.subTest(caso), self.assertLogs('application.assinatura.services', 'ERROR'):
                self.mp.aprovar(self.cobranca, **diferenca)
                self.assertEqual(self.conferir().status, StatusDaCobranca.PENDENTE)
        self.assertVencimento(HOJE + timedelta(days=5))

    def test_pendente_continua_esperando(self):
        self.assertEqual(self.conferir().status, StatusDaCobranca.PENDENTE)
        self.assertVencimento(HOJE + timedelta(days=5))

    def test_cancelado_ou_recusado_expira(self):
        for status in ('cancelled', 'rejected'):
            with self.subTest(status):
                Cobranca.objects.filter(pk=self.cobranca.pk).update(status=StatusDaCobranca.PENDENTE)
                self.mp.responder(self.cobranca, status=status)
                self.assertEqual(self.conferir().status, StatusDaCobranca.EXPIRADA)

    def test_so_desiste_um_tempo_depois_de_expirar(self):
        Cobranca.objects.filter(pk=self.cobranca.pk).update(expira_em=timezone.now() - timedelta(minutes=1))
        self.cobranca.refresh_from_db()
        self.assertEqual(self.conferir().status, StatusDaCobranca.PENDENTE)

        Cobranca.objects.filter(pk=self.cobranca.pk).update(expira_em=timezone.now() - MARGEM_APOS_EXPIRAR - timedelta(minutes=1))
        self.cobranca.refresh_from_db()
        self.assertEqual(self.conferir().status, StatusDaCobranca.EXPIRADA)

    def test_pix_pago_no_ultimo_minuto_ainda_e_confirmado_depois_de_expirado(self):
        Cobranca.objects.filter(pk=self.cobranca.pk).update(status=StatusDaCobranca.EXPIRADA)
        self.cobranca.refresh_from_db()
        self.mp.aprovar(self.cobranca)
        self.assertEqual(self.conferir().status, StatusDaCobranca.PAGA)

    def test_mercado_pago_fora_do_ar_nao_muda_nada(self):
        class Fora(MercadoPagoFalso):
            def consultar(self, pagamento_id):
                raise MercadoPagoError("timeout")
        with self.assertLogs('application.assinatura.services', 'WARNING'):
            self.assertEqual(conferir_cobranca(self.cobranca, gateway=Fora()).status, StatusDaCobranca.PENDENTE)

    def test_cobranca_sem_pix_nao_consulta(self):
        Cobranca.objects.filter(pk=self.cobranca.pk).update(pagamento_id='')
        self.cobranca.refresh_from_db()
        self.conferir()
        self.assertEqual(self.mp.consultas, [])

    def test_plano_vencido_renova_a_partir_de_hoje(self):
        LojaModel.objects.filter(pk=self.loja.pk).update(vencimento=date(2020, 1, 1))
        self.mp.aprovar(self.cobranca)
        self.conferir()
        self.assertVencimento(HOJE + timedelta(days=30))

    def test_sem_gateway_usa_o_do_settings(self):
        with patch('application.assinatura.services.MercadoPago.from_settings', return_value=self.mp):
            conferir_cobranca(self.cobranca)
        self.assertEqual(self.mp.consultas, [self.cobranca.pagamento_id])


class TesteGratisTest(AssinaturaTestCase):

    def test_so_sai_do_teste_gratis_com_pagamento_confirmado(self):
        cobranca = self.gerar()
        self.assertTrue(em_teste_gratis(self.loja))
        self.mp.aprovar(cobranca)
        conferir_cobranca(cobranca, gateway=self.mp)
        self.assertFalse(em_teste_gratis(self.loja))


class ConferirPendentesTest(AssinaturaTestCase):
    """Quem paga e fecha a tela antes da confirmação tem o plano renovado na próxima visita."""

    def test_sem_pix_aberto_nao_chama_o_mercado_pago(self):
        class Proibido:
            def consultar(self, pagamento_id):
                raise AssertionError("não deveria consultar")
        self.assertEqual(conferir_pendentes(self.loja, gateway=Proibido()), [])

    def test_confirma_os_pagos_e_mantem_os_que_aguardam(self):
        paga = self.gerar()
        aguardando = self.gerar(plano=Plano.objects.get(nome="90 dias"))
        self.mp.aprovar(paga)

        conferidas = conferir_pendentes(self.loja, gateway=self.mp)

        self.assertEqual({c.pk: c.status for c in conferidas},
                         {paga.pk: StatusDaCobranca.PAGA, aguardando.pk: StatusDaCobranca.PENDENTE})
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.vencimento, HOJE + timedelta(days=35))

    def test_ignora_as_ja_pagas_ou_expiradas_e_as_de_outra_loja(self):
        cobranca = self.gerar()
        Cobranca.objects.filter(pk=cobranca.pk).update(status=StatusDaCobranca.EXPIRADA)
        outra = LojaModel.objects.create(nome_loja="Outra")
        gerar_cobranca(outra, self.plano_30, email="a@b.com", usuario=None, gateway=self.mp)
        self.assertEqual(conferir_pendentes(self.loja, gateway=self.mp), [])
        self.assertEqual(self.mp.consultas, [])

    def test_sem_gateway_usa_o_do_settings(self):
        self.gerar()
        with patch('application.assinatura.services.MercadoPago.from_settings', return_value=self.mp):
            conferir_pendentes(self.loja)
        self.assertEqual(len(self.mp.consultas), 1)
