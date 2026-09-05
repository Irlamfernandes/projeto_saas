from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto
from infrastructure.models.venda import Venda, ItemVenda

User = get_user_model()


class VendaEditarViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )
        
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente = Cliente.objects.create(loja=self.loja1, nome="Cliente Teste")
        
        self.produto1 = Produto.objects.create(
            loja=self.loja1, nome="Produto A", codigo_interno="PA001", 
            preco_venda=Decimal('50.00'), quantidade_estoque=10
        )
        self.produto2 = Produto.objects.create(
            loja=self.loja1, nome="Produto B", codigo_interno="PB002", 
            preco_venda=Decimal('100.00'), quantidade_estoque=2
        )

        self.venda = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente, valor_total=Decimal('100.00')
        )
        self.item_venda = ItemVenda.objects.create(
            venda=self.venda, produto=self.produto1, quantidade=2, preco_unitario=Decimal('50.00')
        )

        self.url = reverse('venda_editar', args=[self.venda.id])

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário sem loja associada recebe 403 ao acessar a edição de venda."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_nao_edita_venda_de_outra_loja(self):
        """Usuário comum recebe 404 ao tentar editar venda de outra loja."""
        venda_outra_loja = Venda.objects.create(
            loja=self.loja2, valor_total=Decimal('200.00')
        )
        self.client.force_login(self.user_loja1)
        url = reverse('venda_editar', args=[venda_outra_loja.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_carrega_pagina_com_sucesso(self):
        """GET na view de edição renderiza corretamente o template e o contexto."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interfaces/venda_editar.html')
        self.assertEqual(response.context['venda'], self.venda)

    def test_post_quantidade_invalida(self):
        """Enviar quantidade <= 0 ou inválida exibe erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': str(self.produto1.id),
            'quantidade': 0,
            'observacoes': 'Teste'
        })
        self.assertRedirects(response, self.url)

    def test_post_produto_inexistente(self):
        """Enviar produto inexistente (pesquisado por nome/código inválido) exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': '999999',
            'quantidade': 1,
            'observacoes': ''
        })
        self.assertRedirects(response, self.url)

    def test_post_estoque_insuficiente(self):
        """Tentar comprar quantidade maior que o estoque disponível gera erro e faz rollback."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': str(self.produto2.id),
            'quantidade': 5,
            'observacoes': ''
        })
        self.assertRedirects(response, self.url)

    def test_post_edicao_venda_com_sucesso(self):
        """Edita com sucesso o produto, quantidade e recalcula o total, ajustando estoques."""
        self.client.force_login(self.user_loja1)
        
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': str(self.produto2.id),
            'quantidade': 2,
            'observacoes': 'Venda atualizada com sucesso'
        }, follow=True)

        self.assertRedirects(response, reverse('vendas'))
        
        self.venda.refresh_from_db()
        self.produto1.refresh_from_db()
        self.produto2.refresh_from_db()

        self.assertEqual(self.produto1.quantidade_estoque, 12)
        self.assertEqual(self.produto2.quantidade_estoque, 0)
        self.assertEqual(self.venda.valor_total, Decimal('200.00'))
        self.assertEqual(self.venda.observacoes, 'Venda atualizada com sucesso')

    def test_superuser_edita_venda_com_sucesso(self):
        """Superusuário consegue carregar e editar venda utilizando querysets globais (.all)."""
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': str(self.produto1.id),
            'quantidade': 1,
            'observacoes': 'Editado por superuser'
        })
        self.assertRedirects(response, reverse('vendas'))

    def test_post_cliente_inexistente_exibe_erro(self):
        """Enviar um ID de cliente que não existe no banco exibe erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': '999999',
            'produto': str(self.produto1.id),
            'quantidade': 1
        })
        self.assertRedirects(response, self.url)

    def test_editar_venda_sem_item_anterior(self):
        """Edita com sucesso uma venda que não possuía nenhum item pré-vinculado."""
        self.item_venda.delete()

        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente.id,
            'produto': str(self.produto1.id),
            'quantidade': 3,
            'observacoes': 'Adicionando item do zero'
        })
        self.assertRedirects(response, reverse('vendas'))
        
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.valor_total, Decimal('150.00'))

    def test_superuser_cliente_inexistente_exibe_erro(self):
        """Superusuário que informa um ID de cliente inexistente recebe erro e redireciona."""
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {
            'cliente': '99999',
            'produto': str(self.produto1.id),
            'quantidade': 1
        })
        self.assertRedirects(response, self.url)

    def test_post_sem_cliente_atribui_como_none(self):
        """Edita uma venda sem informar cliente (campo vazio), definindo cliente como None."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': '',
            'produto': str(self.produto1.id),
            'quantidade': 1,
            'observacoes': 'Sem cliente'
        })
        self.assertRedirects(response, reverse('vendas'))
        
        self.venda.refresh_from_db()
        self.assertIsNone(self.venda.cliente)