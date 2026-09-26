from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models import Cliente, LojaModel, Produto, Venda

User = get_user_model()


class AcessoLojaInativaTest(TestCase):
    """Toda tela operacional deve barrar usuários de loja desativada."""

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Fechada")
        self.usuario = User.objects.create_user(username="operador", password="senha123", loja=self.loja)
        cliente = Cliente.objects.create(loja=self.loja, nome="Cliente")
        produto = Produto.objects.create(loja=self.loja, nome="Produto", preco_venda=Decimal('1.00'))
        venda = Venda.objects.create(loja=self.loja)
        self.urls = [
            reverse('dashboard'),
            reverse('produtos'),
            reverse('editar_produto', args=[produto.pk]),
            reverse('clientes'),
            reverse('editar_cliente', args=[cliente.pk]),
            reverse('vendas'),
            reverse('venda_editar', args=[venda.pk]),
            reverse('extrato_cliente', args=[cliente.pk]),
            reverse('extrato_pdf', args=[cliente.pk]),
            reverse('relatorios'),
            reverse('exportar_pdf_modular', args=['vendas']),
            reverse('exportar_excel_modular', args=['vendas']),
        ]
        self.loja.ativo = False
        self.loja.save()
        self.client.force_login(self.usuario)

    def test_todas_as_telas_retornam_403(self):
        for url in self.urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_login_e_recusado_com_mensagem(self):
        self.client.logout()

        response = self.client.post(reverse('login'), {'username': 'operador', 'password': 'senha123'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Esta loja está desativada')
        self.assertNotIn('_auth_user_id', self.client.session)
