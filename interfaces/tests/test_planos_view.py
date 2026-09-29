from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from application.assinatura.services import gerar_cobranca
from infrastructure.models import Cobranca, LojaModel, Plano, StatusDaCobranca
from infrastructure.pagamentos.mercado_pago import MercadoPagoRecusou
from tests.apoio import ComPlanosIniciais, MercadoPagoFalso

User = get_user_model()
HOJE = timezone.localdate()


class PlanosTestCase(ComPlanosIniciais, TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria", vencimento=HOJE + timedelta(days=5), email_cobranca="Dono@Padaria.com")
        self.usuario = User.objects.create_user(username="caixa", password="x", loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(self.usuario)
        self.mp = MercadoPagoFalso()
        fabrica = patch('application.assinatura.services.MercadoPago.from_settings', return_value=self.mp)
        fabrica.start()
        self.addCleanup(fabrica.stop)
        self.plano_30 = Plano.objects.get(nome="30 dias")

    def mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def cobranca(self, loja=None):
        return gerar_cobranca(loja or self.loja, self.plano_30, email="a@b.com", usuario=None, gateway=self.mp)


class EscolherPlanoTest(PlanosTestCase):

    def test_lista_os_planos_com_preco_e_o_novo_vencimento(self):
        response = self.client.get(reverse('planos'))

        for nome in ("30 dias", "90 dias", "6 meses", "12 meses"):
            self.assertContains(response, nome)
        self.assertContains(response, "R$ 0,01", count=4)
        self.assertContains(response, f"Passa a vencer em {HOJE + timedelta(days=35):%d/%m/%Y}")

    def test_email_da_ultima_renovacao_ja_vem_preenchido(self):
        self.assertContains(self.client.get(reverse('planos')), 'value="Dono@Padaria.com"')

    def test_gera_o_pix_e_leva_para_a_tela_de_pagamento(self):
        response = self.client.post(reverse('planos'), {'plano': self.plano_30.pk, 'email': "  Ana.Souza99@Exemplo.com "})

        cobranca = Cobranca.objects.get()
        self.assertRedirects(response, reverse('cobranca', args=[cobranca.pk]))
        self.assertEqual(cobranca.email_pagador, "Ana.Souza99@Exemplo.com")
        self.assertEqual(cobranca.usuario, self.usuario)

    def test_dados_invalidos_voltam_com_aviso(self):
        casos = {
            'e-mail inválido': ({'plano': self.plano_30.pk, 'email': 'nao-e-email'}, "Informe um e-mail válido, como nome@exemplo.com."),
            'sem e-mail': ({'plano': self.plano_30.pk}, "Informe o e-mail para o comprovante."),
            'plano inexistente': ({'plano': 9999, 'email': 'a@b.com'}, "Este plano não está mais disponível. Escolha outro."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                response = self.client.post(reverse('planos'), dados)
                self.assertRedirects(response, reverse('planos'))
                self.assertEqual(self.mensagens(response)[-1], mensagem)
        self.assertFalse(Cobranca.objects.exists())

    def test_recusa_do_mercado_pago_volta_com_a_explicacao(self):
        self.mp._erro_ao_criar = MercadoPagoRecusou("payer.email must be valid")
        response = self.client.post(reverse('planos'), {'plano': self.plano_30.pk, 'email': 'a@b.com'})
        self.assertRedirects(response, reverse('planos'))
        self.assertIn("payer.email must be valid", self.mensagens(response)[-1])

    def test_na_tela_de_renovar_a_faixa_de_vencido_nao_repete_o_botao(self):
        LojaModel.objects.filter(pk=self.loja.pk).update(vencimento=HOJE - timedelta(days=3))
        response = self.client.get(reverse('planos'))
        self.assertContains(response, 'data-aviso-plano')
        self.assertNotContains(response, 'btn-primario btn-pequeno shrink-0">Renovar plano')

    def test_loja_vencida_consegue_renovar(self):
        LojaModel.objects.filter(pk=self.loja.pk).update(vencimento=HOJE - timedelta(days=3))
        response = self.client.post(reverse('planos'), {'plano': self.plano_30.pk, 'email': 'a@b.com'})
        self.assertRedirects(response, reverse('cobranca', args=[Cobranca.objects.get().pk]))

    def test_superusuario_sem_loja_nao_tem_plano(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="x", deve_trocar_senha=False))
        self.assertEqual(self.client.get(reverse('planos')).status_code, 404)


class TelaDoPixTest(PlanosTestCase):

    def test_pendente_mostra_qr_code_copia_e_cola_e_acompanha(self):
        cobranca = self.cobranca()

        response = self.client.get(reverse('cobranca', args=[cobranca.pk]))

        self.assertContains(response, 'src="data:image/png;base64,iVBORw0KGgo="')
        self.assertContains(response, cobranca.pix_copia_e_cola)
        self.assertContains(response, f'data-url-situacao="{reverse("cobranca_situacao", args=[cobranca.pk])}"')
        self.assertContains(response, 'js/cobranca.js')

    @override_settings(MERCADO_PAGO_ACCESS_TOKEN='TEST-123')
    def test_avisa_quando_o_pix_e_de_teste(self):
        self.assertContains(self.client.get(reverse('cobranca', args=[self.cobranca().pk])), "Pix de teste")

    @override_settings(MERCADO_PAGO_ACCESS_TOKEN='APP_USR-123')
    def test_pix_de_producao_nao_tem_aviso_de_teste(self):
        self.assertNotContains(self.client.get(reverse('cobranca', args=[self.cobranca().pk])), "Pix de teste")

    def test_abrir_a_tela_confere_e_mostra_a_confirmacao(self):
        cobranca = self.cobranca()
        self.mp.aprovar(cobranca)

        response = self.client.get(reverse('cobranca', args=[cobranca.pk]))

        self.assertContains(response, "Pagamento confirmado!")
        self.assertContains(response, f"{HOJE + timedelta(days=35):%d/%m/%Y}")
        self.assertNotContains(response, 'data-acompanhar-cobranca')

    def test_expirada_oferece_gerar_outro(self):
        cobranca = self.cobranca()
        self.mp.responder(cobranca, status='cancelled')
        response = self.client.get(reverse('cobranca', args=[cobranca.pk]))
        self.assertContains(response, "Este Pix expirou")
        self.assertContains(response, reverse('planos'))

    def test_situacao_em_json(self):
        cobranca = self.cobranca()
        url = reverse('cobranca_situacao', args=[cobranca.pk])
        self.assertEqual(self.client.get(url).json(), {'status': 'pendente'})
        self.mp.aprovar(cobranca)
        self.assertEqual(self.client.get(url).json(), {'status': 'paga'})
        self.assertEqual(Cobranca.objects.get().status, StatusDaCobranca.PAGA)

    def test_cobranca_de_outra_loja_nao_aparece(self):
        de_fora = self.cobranca(LojaModel.objects.create(nome_loja="Outra"))
        for rota in ('cobranca', 'cobranca_situacao'):
            with self.subTest(rota):
                self.assertEqual(self.client.get(reverse(rota, args=[de_fora.pk])).status_code, 404)


class ConfiguracoesComPlanoTest(PlanosTestCase):

    def test_mostra_botao_de_renovar_e_periodo_de_teste(self):
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, "Ver planos e renovar")
        self.assertContains(response, reverse('planos'))
        self.assertContains(response, "Período de teste grátis.")

    def test_depois_do_primeiro_pagamento_sai_do_teste(self):
        cobranca = self.cobranca()
        self.mp.aprovar(cobranca)
        self.client.get(reverse('cobranca', args=[cobranca.pk]))
        self.assertNotContains(self.client.get(reverse('configuracoes')), "Período de teste grátis.")

    def test_aviso_de_vencimento_leva_direto_aos_planos(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, f'href="{reverse("planos")}" class="btn-primario btn-pequeno')


class ConfirmacaoAtualizaATelaTest(PlanosTestCase):
    """Regressão: a página da confirmação ainda mostrava 'Seu plano venceu' (loja antiga na memória)."""

    def setUp(self):
        super().setUp()
        LojaModel.objects.filter(pk=self.loja.pk).update(vencimento=HOJE - timedelta(days=2))

    def test_tela_do_pix_confirmada_ja_nao_mostra_plano_vencido(self):
        cobranca = self.cobranca()
        self.mp.aprovar(cobranca)
        response = self.client.get(reverse('cobranca', args=[cobranca.pk]))
        self.assertContains(response, "Pagamento confirmado!")
        self.assertNotContains(response, "Seu plano venceu")

    def test_pagou_e_fechou_a_tela_o_inicio_ja_entra_renovado(self):
        cobranca = self.cobranca()
        self.mp.aprovar(cobranca)

        response = self.client.get(reverse('dashboard'))

        self.assertNotContains(response, "Seu plano venceu")
        self.assertEqual(Cobranca.objects.get().status, StatusDaCobranca.PAGA)

    def test_configuracoes_confirma_e_lista_os_pix_ainda_abertos(self):
        paga = self.cobranca()
        aberta = gerar_cobranca(self.loja, Plano.objects.get(nome="90 dias"), email="a@b.com", usuario=None, gateway=self.mp)
        self.mp.aprovar(paga)

        response = self.client.get(reverse('configuracoes'))

        self.assertNotContains(response, "Vencido")
        self.assertContains(response, 'data-pix-aguardando', count=1)
        self.assertContains(response, reverse('cobranca', args=[aberta.pk]))
        self.assertContains(response, "Pix do plano 90 dias aguardando pagamento")

    def test_fim_do_teste_gratis_nao_aparece_como_periodo_de_teste(self):
        self.assertNotContains(self.client.get(reverse('configuracoes')), "Período de teste grátis.")


class SairTest(PlanosTestCase):

    def test_sair_fica_so_em_configuracoes(self):
        self.assertNotContains(self.client.get(reverse('dashboard')), f'action="{reverse("logout")}"')
        self.assertContains(self.client.get(reverse('configuracoes')), f'action="{reverse("logout")}"', count=1)
