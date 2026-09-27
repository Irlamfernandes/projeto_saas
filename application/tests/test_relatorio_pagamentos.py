from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.relatorios.pagamentos import NAO_INFORMADA, LinhaDeForma, recebido_por_forma
from infrastructure.models import Cliente, LojaModel, PagamentoCliente, Venda


class RecebidoPorFormaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        outra = LojaModel.objects.create(nome_loja="Loja B")
        ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        Venda.objects.create(loja=self.loja, valor_total=Decimal('30'), forma_pagamento='pix')          # balcão
        Venda.objects.create(loja=self.loja, valor_total=Decimal('10'), forma_pagamento='dinheiro')     # balcão
        fiado = Venda.objects.create(loja=self.loja, cliente=ana, valor_total=Decimal('100'), forma_pagamento='pix')
        PagamentoCliente.objects.create(loja=self.loja, cliente=ana, venda=fiado, valor=Decimal('20'), forma_pagamento='pix')
        PagamentoCliente.objects.create(loja=self.loja, cliente=ana, valor=Decimal('40'), forma_pagamento='dinheiro')
        PagamentoCliente.objects.create(loja=self.loja, cliente=ana, valor=Decimal('5'))                 # antigo
        Venda.objects.create(loja=outra, valor_total=Decimal('999'), forma_pagamento='pix')
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)

    def test_soma_balcao_mais_pagamentos_sem_contar_o_fiado_duas_vezes(self):
        linhas, total = recebido_por_forma(self.usuario)

        self.assertEqual(total, Decimal('105'))
        self.assertEqual(linhas, [
            LinhaDeForma('Dinheiro', Decimal('50'), Decimal('47.6')),
            LinhaDeForma('Pix', Decimal('50'), Decimal('47.6')),
            LinhaDeForma(NAO_INFORMADA, Decimal('5'), Decimal('4.8')),
        ])

    def test_respeita_o_periodo(self):
        linhas, total = recebido_por_forma(self.usuario, date(2000, 1, 1), date(2000, 1, 2))
        self.assertEqual((linhas, total), ([], Decimal('0')))
