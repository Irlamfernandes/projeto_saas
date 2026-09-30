from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models import Cliente, LojaModel, Venda

User = get_user_model()


class ApagarDadosNaCadernetaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja", vencimento=timezone.localdate() + timedelta(days=30))
        self.usuario = User.objects.create_user(username="caixa", password="senha-certa", loja=self.loja, deve_trocar_senha=False)
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Maria", telefone="24999998888")
        self.client.force_login(self.usuario)
        self.extrato = reverse('extrato_cliente', args=[self.cliente.pk])
        self.apagar = reverse('cliente_apagar_dados', args=[self.cliente.pk])

    def test_caderneta_oferece_apagar_com_senha(self):
        resposta = self.client.get(self.extrato)
        self.assertContains(resposta, 'data-abrir-dialogo="modal-apagar-dados"')
        self.assertContains(resposta, f'action="{self.apagar}"')
        self.assertNotContains(resposta, "acerte antes o saldo da caderneta")

    def test_com_saldo_avisa_em_vez_de_oferecer_o_botao(self):
        Venda.objects.create(loja=self.loja, cliente=self.cliente, valor_total=Decimal('10'))
        resposta = self.client.get(self.extrato)
        self.assertContains(resposta, "acerte antes o saldo da caderneta")
        self.assertNotContains(resposta, 'data-abrir-dialogo="modal-apagar-dados"')
        self.assertNotContains(resposta, 'id="modal-apagar-dados"')

    def test_apagar(self):
        resposta = self.client.post(self.apagar, {'senha': 'senha-certa'}, follow=True)
        self.assertRedirects(resposta, self.extrato)
        self.assertContains(resposta, "Dados pessoais apagados.")
        self.assertContains(resposta, "foram apagados a pedido dele")
        self.assertNotContains(resposta, 'id="modal-apagar-dados"')
        self.assertNotContains(resposta, "24999998888")

    def test_senha_errada_ou_vazia(self):
        self.assertContains(self.client.post(self.apagar, {'senha': 'x'}, follow=True), "Senha incorreta.")
        self.assertContains(self.client.post(self.apagar, {}, follow=True), "Digite sua senha para confirmar.")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nome, "Maria")

    def test_vale_mesmo_com_o_plano_vencido(self):
        LojaModel.objects.filter(pk=self.loja.pk).update(vencimento=timezone.localdate() - timedelta(days=5))
        self.client.post(self.apagar, {'senha': 'senha-certa'})
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.dados_apagados)

    def test_so_por_post_e_so_da_propria_loja(self):
        self.assertEqual(self.client.get(self.apagar).status_code, 405)
        outra = LojaModel.objects.create(nome_loja="Outra")
        de_fora = Cliente.objects.create(loja=outra, nome="Zé")
        resposta = self.client.post(reverse('cliente_apagar_dados', args=[de_fora.pk]), {'senha': 'senha-certa'})
        self.assertEqual(resposta.status_code, 404)


class PaginasLegaisTest(TestCase):

    def test_abrem_sem_login(self):
        termos = self.client.get(reverse('termos'))
        self.assertContains(termos, "<h1 class=\"text-2xl sm:text-3xl font-bold\">Termos de uso</h1>", html=False)
        self.assertContains(termos, "Não emite nota fiscal")
        self.assertContains(termos, "<b>90 dias</b>")
        privacidade = self.client.get(reverse('privacidade'))
        self.assertContains(privacidade, "Política de privacidade")
        self.assertContains(privacidade, "a <b>loja</b> é a controladora")
        self.assertContains(privacidade, "Não há cookies de publicidade")
        self.assertContains(privacidade, 'aria-current="page"')

    def test_links_no_login_e_no_sistema(self):
        self.assertContains(self.client.get(reverse('login')), f'href="{reverse("privacidade")}"')
        loja = LojaModel.objects.create(nome_loja="Loja")
        self.client.force_login(User.objects.create_user(username="u", password="x", loja=loja, deve_trocar_senha=False))
        self.assertContains(self.client.get(reverse('dashboard')), f'href="{reverse("termos")}"')
