from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from infrastructure.models import Cliente, LojaModel, PagamentoCliente, Produto, RegistroDeAlteracao, Venda

User = get_user_model()


class VendasViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)
        self.superuser = User.objects.create_superuser(deve_trocar_senha=False, username="admin", password="password")
        self.user_loja1 = User.objects.create_user(deve_trocar_senha=False, username="user_loja1", password="password", loja=self.loja1)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(deve_trocar_senha=False, username="user_sem_loja", password="password", loja=None)

        self.cliente1 = Cliente.objects.create(loja=self.loja1, nome="Cliente Alpha")
        self.cliente2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Beta")
        self.produto1 = Produto.objects.create(
            loja=self.loja1, nome="Produto A", codigo_interno="PA001", preco_venda=Decimal('50.00'), quantidade_estoque=10,
        )
        self.cafe = Produto.objects.create(loja=self.loja1, nome="Café", preco_venda=Decimal('5.00'), quantidade_estoque=20)
        self.esgotado = Produto.objects.create(loja=self.loja1, nome="Esgotado", preco_venda=Decimal('1.00'), quantidade_estoque=0)
        self.produto2 = Produto.objects.create(loja=self.loja2, nome="Produto B", preco_venda=Decimal('100.00'), quantidade_estoque=5)
        self.url = reverse('vendas')

    def _vender(self, itens, usuario=None, **campos):
        self.client.force_login(usuario or self.user_loja1)
        dados = {'cliente': self.cliente1.pk, 'forma_pagamento': 'pix', **campos}
        dados['item_produto'] = [produto.pk for produto, _ in itens]
        dados['item_quantidade'] = [quantidade for _, quantidade in itens]
        return self.client.post(self.url, dados)

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_usuario_sem_loja_recebe_permission_denied(self):
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_usuario_de_loja_inativa_recebe_permission_denied(self):
        self.loja1.ativo = False
        self.loja1.save()
        self.client.force_login(self.user_loja1)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_get_mostra_so_a_loja_do_usuario_e_o_catalogo_com_estoque(self):
        minha = Venda.objects.create(loja=self.loja1, cliente=self.cliente1, valor_total=Decimal('50.00'))
        Venda.objects.create(loja=self.loja2, cliente=self.cliente2, valor_total=Decimal('100.00'))
        self.client.force_login(self.user_loja1)

        response = self.client.get(self.url)

        self.assertEqual(list(response.context['vendas']), [minha])
        self.assertEqual(list(response.context['clientes']), [self.cliente1])
        self.assertEqual([p['nome'] for p in response.context['catalogo']], ["Café", "Produto A"])
        self.assertEqual(response.context['catalogo'][0], {
            'id': self.cafe.pk, 'nome': "Café", 'codigo': '', 'preco': '5.00', 'estoque': 20, 'unidade': 'un.', 'casas': 0,
            'opcoes': [],
        })
        self.assertContains(response, 'id="catalogo-venda"')

    def test_venda_com_varios_produtos(self):
        response = self._vender([(self.produto1, 2), (self.cafe, 3)], valor_pago='20.00')

        self.assertRedirects(response, self.url)
        self.assertIn("Venda realizada com sucesso!", self._mensagens(response))
        venda = Venda.objects.get()
        self.assertEqual((venda.cliente, venda.valor_total, venda.forma_pagamento), (self.cliente1, Decimal('115.00'), 'pix'))
        self.assertEqual(venda.itens.count(), 2)
        self.assertEqual(PagamentoCliente.objects.get().venda, venda)
        self.assertEqual(RegistroDeAlteracao.objects.get().usuario, self.user_loja1)

    def test_venda_a_prazo_com_vencimento_aparece_no_historico(self):
        self._vender([(self.cafe, 2)], vencimento='2026-10-15')

        venda = Venda.objects.get()
        self.assertEqual(list(venda.parcelas.values_list('vencimento', flat=True)), [date(2026, 10, 15)])
        response = self.client.get(self.url)
        self.assertContains(response, 'vence 15/10/2026')
        self.assertContains(response, 'data-prazo-dias="30"')

    def test_venda_por_quilo_e_de_produto_sem_controle(self):
        queijo = Produto.objects.create(loja=self.loja1, nome="Queijo", preco_venda=Decimal('39.90'), unidade='kg',
                                        quantidade_estoque=Decimal('2'))
        bolo = Produto.objects.create(loja=self.loja1, nome="Bolo", preco_venda=Decimal('50.00'), controla_estoque=False)

        response = self._vender([(queijo, '0,35'), (bolo, 2)])

        self.assertIn("Venda realizada com sucesso!", self._mensagens(response))
        self.assertEqual(Venda.objects.get().valor_total, Decimal('113.97'))
        pagina = self.client.get(self.url)
        self.assertContains(pagina, '0,35 kg Queijo')
        self.assertIn(bolo.pk, [p['id'] for p in pagina.context['catalogo']])

    def test_venda_parcelada_aparece_resumida_no_historico(self):
        self._vender([(self.cafe, 6)], vencimento=['2026-10-15', '2026-11-15', '2026-12-15'])

        self.assertEqual(Venda.objects.get().parcelas.count(), 3)
        self.assertContains(self.client.get(self.url), '3 parcelas a partir de 15/10/2026')

    def test_venda_de_balcao_na_loja_do_usuario(self):
        self._vender([(self.cafe, 1)], cliente='', forma_pagamento='dinheiro')

        venda = Venda.objects.get()
        self.assertEqual((venda.cliente, venda.loja, venda.forma_pagamento), (None, self.loja1, 'dinheiro'))

    def test_superusuario_sem_loja_nao_vende_no_balcao(self):
        response = self._vender([(self.cafe, 1)], usuario=self.superuser, cliente='', forma_pagamento='dinheiro')

        self.assertFalse(Venda.objects.exists())
        self.assertIn("Venda de balcão precisa de uma loja", self._mensagens(response)[0])

    def test_superusuario_vende_para_cliente_de_qualquer_loja(self):
        self._vender([(self.produto2, 1)], usuario=self.superuser, cliente=self.cliente2.pk)
        self.assertEqual(Venda.objects.get().loja, self.loja2)

    def test_erros_de_regra_aparecem_como_mensagem(self):
        casos = {
            'estoque insuficiente': ([(self.produto1, 11)], "Estoque insuficiente para 'Produto A'. Disponível: 10 un."),
            'produto de outra loja': ([(self.produto2, 1)], "Um dos produtos escolhidos não foi encontrado nesta loja."),
            'sem forma no balcão': ([(self.cafe, 1)], "Informe como foi pago."),
        }
        for nome, (itens, mensagem) in casos.items():
            with self.subTest(nome):
                extras = {'cliente': '', 'forma_pagamento': ''} if nome == 'sem forma no balcão' else {}
                response = self._vender(itens, **extras)
                self.assertTrue(self._mensagens(response)[-1].startswith(mensagem), self._mensagens(response))
                self.assertFalse(Venda.objects.exists())

    def test_usuario_comum_nao_vende_para_cliente_de_outra_loja(self):
        self._vender([(self.cafe, 1)], cliente=self.cliente2.pk)
        self.assertFalse(Venda.objects.exists())

    def test_quantidade_de_consultas_nao_cresce_com_o_numero_de_clientes(self):
        """Regressão: o saldo de cada cliente no select custava 2 consultas por cliente (N+1)."""
        def consultas_da_pagina():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(self.url)
            return len(ctx.captured_queries)

        self.client.force_login(self.user_loja1)
        Venda.objects.create(loja=self.loja1, cliente=self.cliente1, valor_total=Decimal('10.00'))
        antes = consultas_da_pagina()
        for i in range(20):
            cliente = Cliente.objects.create(loja=self.loja1, nome=f"Cliente {i}")
            Venda.objects.create(loja=self.loja1, cliente=cliente, valor_total=Decimal('10.00'))

        self.assertEqual(consultas_da_pagina(), antes)
