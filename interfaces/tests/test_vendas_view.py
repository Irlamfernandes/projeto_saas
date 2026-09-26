from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto
from infrastructure.models.venda import Venda, ItemVenda, PagamentoCliente

User = get_user_model()


class VendasViewTest(TestCase):

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

        self.cliente1 = Cliente.objects.create(loja=self.loja1, nome="Cliente Alpha")
        self.cliente2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Beta")

        self.produto1 = Produto.objects.create(
            loja=self.loja1, nome="Produto A", codigo_interno="PA001",
            preco_venda=Decimal('50.00'), quantidade_estoque=10
        )
        self.produto2 = Produto.objects.create(
            loja=self.loja2, nome="Produto B", codigo_interno="PB002",
            preco_venda=Decimal('100.00'), quantidade_estoque=5
        )

        self.url = reverse('vendas')

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar a página de vendas."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_usuario_comum_ve_apenas_dados_da_sua_loja(self):
        """Usuário comum visualiza apenas vendas, produtos e clientes da sua própria loja."""
        venda_loja1 = Venda.objects.create(loja=self.loja1, cliente=self.cliente1, valor_total=Decimal('50.00'))
        venda_loja2 = Venda.objects.create(loja=self.loja2, cliente=self.cliente2, valor_total=Decimal('100.00'))

        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(venda_loja1, response.context['vendas'])
        self.assertNotIn(venda_loja2, response.context['vendas'])
        self.assertIn(self.produto1, response.context['produtos'])
        self.assertNotIn(self.produto2, response.context['produtos'])

    def test_get_superuser_ve_todos_os_dados(self):
        """Superusuário visualiza vendas, produtos e clientes de todas as lojas."""
        venda_loja1 = Venda.objects.create(loja=self.loja1, cliente=self.cliente1, valor_total=Decimal('50.00'))
        venda_loja2 = Venda.objects.create(loja=self.loja2, cliente=self.cliente2, valor_total=Decimal('100.00'))

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(venda_loja1, response.context['vendas'])
        self.assertIn(venda_loja2, response.context['vendas'])

    def test_post_quantidade_invalida(self):
        """Enviar quantidade inválida ou zero exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 0,
            'valor_pago': '0'
        })
        self.assertRedirects(response, self.url)

    def test_post_quantidade_formato_invalido(self):
        """Enviar quantidade com formato não numérico exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 'abc',
            'valor_pago': '0'
        })
        self.assertRedirects(response, self.url)

    def test_post_valor_pago_invalido(self):
        """Enviar valor pago com formato inválido exibe erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 1,
            'valor_pago': 'abc'
        })
        self.assertRedirects(response, self.url)

    def test_post_cliente_inexistente(self):
        """Enviar ID de cliente inexistente retorna erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': 99999,
            'produto': str(self.produto1.id),
            'quantidade': 1,
            'valor_pago': '0'
        })
        self.assertRedirects(response, self.url)

    def test_post_produto_inexistente(self):
        """Enviar produto inexistente exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': '999999',
            'quantidade': 1,
            'valor_pago': '0'
        })
        self.assertRedirects(response, self.url)

    def test_post_estoque_insuficiente(self):
        """Tentar vender quantidade maior que o estoque atual falha com mensagem de erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 20, # Estoque é 10
            'valor_pago': '0'
        })
        self.assertRedirects(response, self.url)
        self.assertEqual(Venda.objects.filter(loja=self.loja1).count(), 0)

    def test_post_venda_realizada_com_sucesso(self):
        """Realiza venda com sucesso, criando item, abatendo estoque e registrando pagamento inicial se houver."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 3,
            'valor_pago': '50.00',
            'observacoes': 'Teste de venda'
        }, follow=True)

        self.assertRedirects(response, self.url)
        
        # Verifica criação da venda e item
        venda = Venda.objects.filter(loja=self.loja1).latest('id')
        self.assertEqual(venda.valor_total, Decimal('150.00')) # 3 * 50.00
        self.assertEqual(venda.observacoes, 'Teste de venda')
        
        item = ItemVenda.objects.get(venda=venda)
        self.assertEqual(item.produto, self.produto1)
        self.assertEqual(item.quantidade, 3)

        # Verifica baixa no estoque (10 - 3 = 7)
        self.produto1.refresh_from_db()
        self.assertEqual(self.produto1.quantidade_estoque, 7)

        # Verifica registro do pagamento inicial
        pagamento = PagamentoCliente.objects.get(cliente=self.cliente1)
        self.assertEqual(pagamento.valor, Decimal('50.00'))

    def test_post_valor_pago_negativo(self):
        """Enviar um valor pago negativo exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 1,
            'valor_pago': '-10.00'
        })
        self.assertRedirects(response, self.url)

    def test_superuser_realiza_venda_com_sucesso(self):
        """Superusuário realiza venda utilizando os blocos globais de cliente e produto."""
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {
            'cliente': self.cliente1.id,
            'produto': str(self.produto1.id),
            'quantidade': 2,
            'valor_pago': '20.00',
            'observacoes': 'Venda do superuser'
        }, follow=True)

        self.assertRedirects(response, self.url)
        venda = Venda.objects.filter(observacoes='Venda do superuser').first()
        self.assertIsNotNone(venda)
        self.assertEqual(venda.valor_total, Decimal('100.00'))

    def _vender(self, produto, **extra):
        self.client.force_login(self.user_loja1)
        dados = {'cliente': self.cliente1.id, 'produto': produto, 'quantidade': 1, 'valor_pago': '', **extra}
        return self.client.post(self.url, dados)

    def test_venda_pelo_codigo_interno(self):
        """Regressão: o datalist envia o código interno e isso gerava HTTP 500."""
        response = self._vender('pa001')

        self.assertRedirects(response, self.url)
        self.assertEqual(Venda.objects.get().itens.get().produto, self.produto1)

    def test_venda_pelo_nome_do_produto(self):
        """Regressão: produto sem código é enviado pelo nome e isso gerava HTTP 500."""
        self._vender('Produto A')
        self.assertEqual(Venda.objects.get().itens.get().produto, self.produto1)

    def test_produto_digitado_inexistente_exibe_erro_sem_quebrar(self):
        response = self._vender('Fanta')

        self.assertRedirects(response, self.url)
        self.assertFalse(Venda.objects.exists())
        mensagens = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(mensagens, ["Produto 'Fanta' não foi encontrado pelo Código Interno ou Nome."])

    def test_usuario_de_loja_inativa_recebe_permission_denied(self):
        self.loja1.ativo = False
        self.loja1.save()
        self.client.force_login(self.user_loja1)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_usuario_comum_nao_vende_para_cliente_de_outra_loja(self):
        self._vender('PA001', cliente=self.cliente2.id)
        self.assertFalse(Venda.objects.exists())
