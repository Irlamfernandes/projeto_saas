"""Plano da loja nas telas: avisos antes de vencer e modo só consulta depois."""
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models import LojaModel, Produto, Venda
from tests.apoio import imagem_de_teste


class PlanoNasTelasTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria")
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(self.usuario)

    def vencer_em(self, dias):
        self.loja.vencimento = timezone.localdate() + timedelta(days=dias)
        self.loja.save()


class AvisosTest(PlanoNasTelasTestCase):

    def test_sem_aviso_quando_falta_mais_de_uma_semana(self):
        self.vencer_em(8)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'data-aviso-plano')

    def test_inicio_avisa_na_semana_do_vencimento(self):
        self.vencer_em(3)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, "Seu plano vence em 3 dias")
        self.assertContains(response, f'href="{reverse("configuracoes")}#plano"')

    def test_aviso_antes_de_vencer_aparece_so_no_inicio(self):
        self.vencer_em(3)
        self.assertNotContains(self.client.get(reverse('produtos')), 'data-aviso-plano')

    def test_vencido_mostra_a_faixa_em_todas_as_telas(self):
        self.vencer_em(-1)
        for rota in ('dashboard', 'vendas', 'produtos', 'clientes', 'relatorios'):
            with self.subTest(rota=rota):
                response = self.client.get(reverse(rota))
                self.assertContains(response, 'data-aviso-plano', count=1)
                self.assertContains(response, "Você ainda pode consultar tudo")

    def test_configuracoes_mostra_vencimento_e_situacao(self):
        self.vencer_em(10)
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, self.loja.vencimento.strftime('%d/%m/%Y'))
        self.assertContains(response, "Em dia")
        self.assertContains(response, "Faltam 10 dias.")

        self.vencer_em(-2)
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, "Vencido")
        self.assertContains(response, "Uso limitado")

    def test_configuracoes_de_superusuario_nao_tem_plano(self):
        admin = get_user_model().objects.create_superuser(username="admin", password="x", deve_trocar_senha=False)
        self.client.force_login(admin)
        self.assertNotContains(self.client.get(reverse('configuracoes')), 'id="plano"')


class ModoSoConsultaTest(PlanoNasTelasTestCase):

    def setUp(self):
        super().setUp()
        self.produto = Produto.objects.create(loja=self.loja, nome="Pão", preco_venda=Decimal('1'), quantidade_estoque=5)
        self.vencer_em(-1)

    def test_nao_registra_venda(self):
        response = self.client.post(reverse('vendas'), {
            'item_produto': [self.produto.pk], 'item_quantidade': [1], 'forma_pagamento': 'pix',
        }, HTTP_REFERER='http://testserver' + reverse('vendas'))

        self.assertEqual(response.url, 'http://testserver' + reverse('vendas'))
        self.assertFalse(Venda.objects.exists())
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade_estoque, 5)

    def test_consultas_e_exportacoes_continuam(self):
        self.assertEqual(self.client.get(reverse('vendas')).status_code, 200)
        self.assertEqual(self.client.get(reverse('exportar_excel_modular', args=['resumo'])).status_code, 200)

    def test_configuracoes_continua_funcionando_para_poder_renovar(self):
        from unittest.mock import patch
        from tests.apoio import StorageFalso
        with patch('application.lojas.services.SupabaseStorage.from_settings', return_value=StorageFalso()):
            response = self.client.post(reverse('marca_enviar'), {'marca': imagem_de_teste()})
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], ["Marca atualizada! Ela já aparece no topo e nos PDFs."])
