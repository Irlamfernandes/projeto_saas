"""Todo campo obrigatório mostra um * vermelho ao lado do nome, em todas as telas."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from application.vendas.services import registrar_venda
from infrastructure.models import Cliente, LojaModel, Produto

MARCA = '<span class="obrigatorio" aria-hidden="true">*</span>'
MARCA_ESCONDIDA = '<span class="obrigatorio hidden" aria-hidden="true">*</span>'


class CamposObrigatoriosTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.usuario = get_user_model().objects.create_user(
            username="caixa", password="senha-certa", loja=self.loja, deve_trocar_senha=False,
        )
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        self.arroz = Produto.objects.create(loja=self.loja, nome="Arroz", preco_venda=Decimal('20'), quantidade_estoque=10)

    def assertMarcas(self, url, quantidade, escondidas=0):
        html = self.client.get(url).content.decode()
        self.assertEqual(html.count(MARCA), quantidade, url)
        self.assertEqual(html.count(MARCA_ESCONDIDA), escondidas, url)

    def test_login(self):
        self.assertMarcas(reverse('login'), 2)

    def test_telas_de_cadastro_e_pagamento(self):
        self.client.force_login(self.usuario)
        casos = [
            (reverse('produtos'), 3),               # nome, preço de venda, estoque
            (reverse('editar_produto', args=[self.arroz.pk]), 3),
            (reverse('clientes'), 2),               # nome no cadastro e no modal de edição
            (reverse('extrato_cliente', args=[self.ana.pk]), 3),  # valor, forma de pagamento e senha para apagar os dados
            (reverse('vendas'), 2),                 # produtos e forma de pagamento (balcão)
        ]
        for url, quantidade in casos:
            with self.subTest(url=url):
                self.assertMarcas(url, quantidade)

    def test_troca_de_senha(self):
        self.usuario.deve_trocar_senha = True
        self.usuario.save()
        self.client.force_login(self.usuario)
        self.assertMarcas(reverse('alterar_senha'), 2)

    def test_editar_venda_fiado_sem_pagamento_esconde_o_asterisco_da_forma(self):
        self.client.force_login(self.usuario)
        venda = registrar_venda(cliente=self.ana, itens=[(self.arroz.pk, 1)])
        # produtos + motivo e senha do cancelamento; a forma de pagamento começa opcional
        self.assertMarcas(reverse('venda_editar', args=[venda.pk]), 3, escondidas=1)

    def test_editar_venda_com_pagamento_no_ato_exige_a_forma(self):
        self.client.force_login(self.usuario)
        venda = registrar_venda(cliente=self.ana, itens=[(self.arroz.pk, 1)], valor_pago=Decimal('5'), forma_pagamento='pix')
        response = self.client.get(reverse('venda_editar', args=[venda.pk]))
        self.assertContains(response, 'data-pagou-no-ato')
        self.assertEqual(response.content.decode().count(MARCA), 4)

    def test_editar_venda_de_balcao_exige_a_forma(self):
        self.client.force_login(self.usuario)
        venda = registrar_venda(loja=self.loja, itens=[(self.arroz.pk, 1)], forma_pagamento='pix')
        self.assertMarcas(reverse('venda_editar', args=[venda.pk]), 4)
