from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from infrastructure.models import Cliente, LojaModel, Produto, Venda
from interfaces.views.comum import ITENS_POR_PAGINA, paginar


class PaginarTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        Cliente.objects.bulk_create([Cliente(loja=loja, nome=f"C{i:03d}") for i in range(ITENS_POR_PAGINA + 10)])
        self.clientes = Cliente.objects.order_by('nome')

    def _pagina(self, valor):
        return paginar(RequestFactory().get('/', {'pagina': valor} if valor is not None else {}), self.clientes)

    def test_primeira_e_segunda_pagina(self):
        self.assertEqual(len(self._pagina(None)), ITENS_POR_PAGINA)
        self.assertEqual([c.nome for c in self._pagina('2')], [f"C{i:03d}" for i in range(50, 60)])

    def test_pagina_invalida_ou_fora_do_intervalo(self):
        self.assertEqual(self._pagina('abc').number, 1)
        self.assertEqual(self._pagina('999').number, 2)


class PaginacaoNasTelasTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.user = get_user_model().objects.create_user(
            username="op", password="x", loja=self.loja, deve_trocar_senha=False,
        )
        self.client.force_login(self.user)

    def test_vendas_paginadas(self):
        Venda.objects.bulk_create([Venda(loja=self.loja, valor_total=Decimal('1.00')) for _ in range(ITENS_POR_PAGINA + 5)])

        pagina1 = self.client.get(reverse('vendas'))
        pagina2 = self.client.get(reverse('vendas'), {'pagina': 2})

        self.assertEqual(len(pagina1.context['vendas']), ITENS_POR_PAGINA)
        self.assertContains(pagina1, "Página 1 de 2")
        self.assertContains(pagina1, 'href="?pagina=2"')
        self.assertEqual(len(pagina2.context['vendas']), 5)

    def test_troca_de_pagina_preserva_os_filtros(self):
        Produto.objects.bulk_create([
            Produto(loja=self.loja, nome=f"Bolo {i}", categoria="Doces", preco_venda=Decimal('1')) for i in range(ITENS_POR_PAGINA + 1)
        ])

        response = self.client.get(reverse('produtos'), {'q': 'Bolo', 'categoria': 'Doces'})

        self.assertContains(response, 'href="?q=Bolo&amp;categoria=Doces&amp;pagina=2"')

    def test_clientes_paginados(self):
        Cliente.objects.bulk_create([Cliente(loja=self.loja, nome=f"C{i}") for i in range(ITENS_POR_PAGINA + 1)])
        self.assertContains(self.client.get(reverse('clientes')), "Página 1 de 2")

    def test_sem_navegacao_quando_cabe_numa_pagina(self):
        self.assertNotContains(self.client.get(reverse('clientes')), 'aria-label="Paginação"')
