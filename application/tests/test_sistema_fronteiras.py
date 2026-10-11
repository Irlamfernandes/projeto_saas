"""Fronteiras do plano, do bloqueio de login, da marca da loja e dos erros do sistema (achadas pelo teste de mutação)."""
import hashlib
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from application.assinatura.exceptions import PagamentoIndisponivel, PixRecusado, PlanoIndisponivel
from application.assinatura.services import conferir_cobranca, conferir_pendentes
from application.assinatura.situacao import SituacaoDoPlano
from application.contas.tentativas import minutos_bloqueado, registrar_falha
from application.erros.services import Ocorrencia, registrar_erro
from application.lojas.exceptions import FalhaNoEnvioDaMarca, MarcaInvalida, UsuarioSemLoja
from application.lojas.services import remover_marca, trocar_marca
from application.tests.test_assinatura_services import AssinaturaTestCase
from infrastructure.models import Acao, Cobranca, LojaModel, RegistroDeAlteracao, StatusDaCobranca, TentativasDeLogin
from infrastructure.pagamentos.mercado_pago import MercadoPagoError
from tests.apoio import StorageFalso, imagem_de_teste

FALHOU = RuntimeError("falhou no fim")


# ---------------------------------------------------------------- plano e Pix

class PixTest(AssinaturaTestCase):

    def test_pix_vale_30_minutos(self):
        cobranca = self.gerar()
        self.assertAlmostEqual(cobranca.expira_em, timezone.now() + timedelta(minutes=30), delta=timedelta(seconds=5))

    def test_pix_aberto_com_5_minutos_ou_mais_e_reaproveitado(self):
        aberta = self.gerar()
        Cobranca.objects.filter(pk=aberta.pk).update(expira_em=timezone.now() + timedelta(minutes=5, seconds=20))
        self.assertEqual(self.gerar().pk, aberta.pk)

    def test_cobranca_sem_pix_nao_e_reaproveitada_nem_consultada(self):
        sem_pix = Cobranca.objects.create(
            loja=self.loja, plano=self.plano_30, usuario=self.usuario, plano_nome="30 dias", quantidade=30,
            unidade='dias', valor=self.plano_30.preco, email_pagador="Ana.Souza99@Exemplo.com",
            expira_em=timezone.now() + timedelta(minutes=20),
        )
        nova = self.gerar()
        self.assertNotEqual(nova.pk, sem_pix.pk)
        conferir_pendentes(self.loja, gateway=self.mp)
        self.assertEqual(self.mp.consultas, [nova.pagamento_id])

    def test_loja_so_com_cobranca_sem_pix_nao_consulta_nada(self):
        Cobranca.objects.create(
            loja=self.loja, plano=self.plano_30, usuario=self.usuario, plano_nome="30 dias", quantidade=30,
            unidade='dias', valor=self.plano_30.preco, email_pagador="a@b.com", expira_em=timezone.now() + timedelta(minutes=20),
        )
        self.assertEqual(conferir_pendentes(self.loja, gateway=self.mp), [])

    def test_recusado_ou_cancelado_expira_na_hora(self):
        for status in ('rejected', 'cancelled'):
            with self.subTest(status):
                cobranca = self.gerar(email=f"{status}@exemplo.com")
                self.mp.responder(cobranca, status=status)
                self.assertEqual(conferir_cobranca(cobranca, gateway=self.mp).status, StatusDaCobranca.EXPIRADA)

    def test_espera_exatos_10_minutos_depois_de_expirar(self):
        cobranca = self.gerar()
        agora = timezone.now()
        Cobranca.objects.filter(pk=cobranca.pk).update(expira_em=agora - timedelta(minutes=10))
        cobranca.refresh_from_db()
        with patch('application.assinatura.services.timezone.now', return_value=agora):
            self.assertEqual(conferir_cobranca(cobranca, gateway=self.mp).status, StatusDaCobranca.PENDENTE)
        with patch('application.assinatura.services.timezone.now', return_value=agora + timedelta(seconds=1)):
            self.assertEqual(conferir_cobranca(cobranca, gateway=self.mp).status, StatusDaCobranca.EXPIRADA)

    def test_falha_na_consulta_fica_no_log_com_o_erro(self):
        cobranca = self.gerar()
        with patch.object(self.mp, 'consultar', side_effect=MercadoPagoError("fora do ar")), \
                self.assertLogs('application.assinatura.services', 'WARNING') as log:
            conferir_cobranca(cobranca, gateway=self.mp)
        self.assertEqual(log.records[0].getMessage(), f"Não deu para consultar a cobrança {cobranca.pk} agora")
        self.assertIs(log.records[0].exc_info[0], MercadoPagoError)  # o erro vai junto para o log

    def test_pagamento_que_nao_confere_fica_no_log(self):
        cobranca = self.gerar()
        self.mp.aprovar(cobranca, valor=Decimal('5.00'))
        with self.assertLogs('application.assinatura.services', 'ERROR') as log:
            conferir_cobranca(cobranca, gateway=self.mp)
        self.assertEqual(log.records[0].getMessage(), (
            f"Pagamento {cobranca.pagamento_id} aprovado não confere com a cobrança {cobranca.pk} "
            f"(valor 5.00, moeda BRL, referência {cobranca.referencia})"
        ))

    def test_falha_ao_gerar_o_pix_fica_no_log(self):
        with self.assertLogs('application.assinatura.services', 'ERROR') as log, self.assertRaises(PagamentoIndisponivel):
            self.gerar(gateway=type(self.mp)(erro_ao_criar=MercadoPagoError("fora do ar")))
        self.assertEqual(log.records[0].getMessage(), f"Falha ao gerar o Pix da cobrança da loja {self.loja.pk}")

    def test_renovacao_que_falha_no_historico_nao_renova(self):
        cobranca = self.gerar()
        self.mp.aprovar(cobranca)
        vencimento = self.loja.vencimento
        with patch('application.assinatura.services.registrar_alteracao', side_effect=FALHOU), self.assertRaises(RuntimeError):
            conferir_cobranca(cobranca, gateway=self.mp)
        self.loja.refresh_from_db()
        cobranca.refresh_from_db()
        self.assertEqual((self.loja.vencimento, cobranca.status), (vencimento, StatusDaCobranca.PENDENTE))

    def test_historico_da_renovacao(self):
        cobranca = self.gerar()
        self.mp.aprovar(cobranca)
        anterior = self.loja.vencimento
        conferir_cobranca(cobranca, gateway=self.mp)
        self.loja.refresh_from_db()
        registro = RegistroDeAlteracao.objects.get(acao=Acao.PLANO_RENOVADO)
        self.assertEqual(registro.detalhes, {
            'vencimento': [anterior.isoformat(), self.loja.vencimento.isoformat()], 'pagamento_id': cobranca.pagamento_id,
        })


# ---------------------------------------------------------------- bloqueio de login

class BloqueioDeLoginTest(TestCase):

    def setUp(self):
        self.agora = timezone.now()

    def test_sem_nome_conta_como_nome_vazio(self):
        registrar_falha(None, agora=self.agora)
        self.assertEqual(TentativasDeLogin.objects.get().usuario, '')

    def test_nome_longo_e_cortado_no_tamanho_do_campo(self):
        registrar_falha("a" * 151, agora=self.agora)
        self.assertEqual(len(TentativasDeLogin.objects.get().usuario), 150)

    def test_minutos_arredondam_para_cima(self):
        TentativasDeLogin.objects.create(usuario='ana', ultima_falha=self.agora, bloqueado_ate=self.agora + timedelta(seconds=61))
        self.assertEqual(minutos_bloqueado('ana', agora=self.agora), 2)

    def test_erro_exatamente_15_minutos_depois_ainda_soma(self):
        registrar_falha('ana', agora=self.agora)
        registrar_falha('ana', agora=self.agora + timedelta(minutes=15))
        self.assertEqual(TentativasDeLogin.objects.get().falhas, 2)

    def test_quinta_falha_bloqueia_e_zera_a_contagem(self):
        for _ in range(5):
            registrar_falha('ana', agora=self.agora)
        tentativas = TentativasDeLogin.objects.get()
        self.assertEqual((tentativas.falhas, tentativas.bloqueado_ate), (0, self.agora + timedelta(minutes=15)))

    def test_se_gravar_falhar_a_limpeza_dos_antigos_e_desfeita(self):
        TentativasDeLogin.objects.create(usuario='velho', ultima_falha=self.agora - timedelta(days=2))
        with patch.object(TentativasDeLogin, 'save', side_effect=FALHOU), self.assertRaises(RuntimeError):
            registrar_falha('ana', agora=self.agora)
        self.assertTrue(TentativasDeLogin.objects.filter(usuario='velho').exists())


# ---------------------------------------------------------------- marca da loja

class MarcaDaLojaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja", logo_url='https://x/antiga.webp')
        historico = patch('application.lojas.services.registrar_alteracao', side_effect=FALHOU)
        self.historico = historico

    def logo_salvo(self):
        return LojaModel.objects.get(pk=self.loja.pk).logo_url

    def test_trocar_que_falha_no_historico_nao_troca(self):
        with self.historico, self.assertRaises(RuntimeError):
            trocar_marca(self.loja, imagem_de_teste(), usuario=None, storage=StorageFalso())
        self.assertEqual(self.logo_salvo(), 'https://x/antiga.webp')

    def test_remover_que_falha_no_historico_nao_remove(self):
        with self.historico, self.assertRaises(RuntimeError):
            remover_marca(self.loja, usuario=None, storage=StorageFalso())
        self.assertEqual(self.logo_salvo(), 'https://x/antiga.webp')

    def test_falha_no_envio_fica_no_log(self):
        with self.assertLogs('application.lojas.services', 'ERROR') as log, self.assertRaises(FalhaNoEnvioDaMarca):
            trocar_marca(self.loja, imagem_de_teste(), usuario=None, storage=StorageFalso(falhar_no_envio=0))
        self.assertEqual(log.records[0].getMessage(), f"Falha ao enviar a marca da loja {self.loja.pk}")


# ---------------------------------------------------------------- erros do sistema

class ErrosDoSistemaTest(TestCase):

    def test_so_o_tipo_basta(self):
        erro = registrar_erro(Ocorrencia('ValueError'))
        self.assertEqual((erro.mensagem, erro.caminho, erro.metodo, erro.loja_id, erro.usuario_id), ('', '', '', None, None))

    def test_mensagem_e_detalhes_cortados_no_limite(self):
        erro = registrar_erro(Ocorrencia('ValueError', mensagem='m' * 1001, detalhes='d' * 20000 + 'fim'))
        self.assertEqual(len(erro.mensagem), 1000)
        self.assertEqual((len(erro.detalhes), erro.detalhes[-3:]), (20000, 'fim'))  # o fim do traceback fica

    def test_assinatura_e_o_tipo_com_o_local(self):
        """Mudar esta conta separaria os erros já abertos em produção dos novos iguais a eles."""
        esperado = hashlib.sha256(b"ValueError|views.py:10").hexdigest()
        self.assertEqual(Ocorrencia('ValueError', mensagem='outra', local='views.py:10').assinatura, esperado)
        self.assertEqual(Ocorrencia('ValueError').assinatura, hashlib.sha256(b"ValueError|").hexdigest())
        self.assertEqual(Ocorrencia('ValueError', mensagem='sem local').assinatura,
                         hashlib.sha256(b"ValueError|sem local").hexdigest())


# ---------------------------------------------------------------- mensagens

class MensagensDoSistemaTest(SimpleTestCase):
    """O texto é o que aparece na tela: confere palavra por palavra."""

    def test_mensagens(self):
        casos = {
            PlanoIndisponivel(): "Este plano não está mais disponível. Escolha outro.",
            PixRecusado("e-mail inválido"): "O Mercado Pago não aceitou gerar o Pix (e-mail inválido). Confira o e-mail e tente de novo.",
            PixRecusado(""): "O Mercado Pago não aceitou gerar o Pix. Confira o e-mail e tente de novo.",
            PagamentoIndisponivel(): "Não foi possível falar com o Mercado Pago agora. Tente de novo em instantes.",
            UsuarioSemLoja(): "Este usuário não está ligado a nenhuma loja.",
            MarcaInvalida(): "Não foi possível ler a imagem da marca. Envie uma imagem JPG, PNG, WEBP ou HEIC.",
            FalhaNoEnvioDaMarca(): "Não foi possível enviar a marca agora. Nada foi alterado; tente novamente.",
        }
        for erro, mensagem in casos.items():
            with self.subTest(type(erro).__name__):
                self.assertEqual(str(erro), mensagem)

    def test_aviso_do_plano_vencido(self):
        vencido = SituacaoDoPlano(vencimento=date(2026, 9, 1), dias_restantes=-1)
        self.assertEqual(vencido.aviso, (
            "Seu plano venceu em 01/09/2026. Você ainda pode consultar tudo, "
            "mas para registrar vendas e fazer alterações é preciso renovar."
        ))
