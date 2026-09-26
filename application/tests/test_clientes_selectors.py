from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from django.utils import timezone
from application.clientes.selectors import (
    Movimento, buscar_clientes, clientes_da_loja, clientes_do_usuario, linha_do_tempo,
)
from infrastructure.models import Cliente, ItemVenda, LojaModel, PagamentoCliente, Produto, Venda


class ConsultasDeClientesTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.zeca = Cliente.objects.create(loja=self.loja, nome="Zeca", telefone="2499990000")
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana", telefone="2188881111")
        Cliente.objects.create(loja=self.outra_loja, nome="Bia")

    def test_clientes_do_usuario_filtra_pela_loja_em_ordem_alfabetica(self):
        usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        superusuario = SimpleNamespace(is_superuser=True, loja=None)

        self.assertEqual(list(clientes_do_usuario(usuario)), [self.ana, self.zeca])
        self.assertEqual(clientes_do_usuario(superusuario).count(), 3)

    def test_clientes_da_loja(self):
        self.assertEqual(list(clientes_da_loja(self.loja)), [self.ana, self.zeca])

    def test_buscar_por_nome_ou_telefone_mais_recentes_primeiro(self):
        clientes = clientes_da_loja(self.loja)

        self.assertEqual(list(buscar_clientes(clientes)), [self.ana, self.zeca])
        self.assertEqual(list(buscar_clientes(clientes, "zec")), [self.zeca])
        self.assertEqual(list(buscar_clientes(clientes, "2188")), [self.ana])


class LinhaDoTempoTest(TestCase):

    def test_intercala_compras_e_pagamentos_do_mais_recente_ao_mais_antigo(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        cliente = Cliente.objects.create(loja=loja, nome="Ana")
        produto = Produto.objects.create(loja=loja, nome="Arroz", preco_venda=Decimal('10.00'))
        agora = timezone.now()
        antiga = Venda.objects.create(loja=loja, cliente=cliente, valor_total=Decimal('20.00'),
                                      data_venda=agora - timedelta(days=2), observacoes="fiado")
        item = ItemVenda.objects.create(venda=antiga, produto=produto, quantidade=2, preco_unitario=Decimal('10.00'))
        pagamento = PagamentoCliente.objects.create(loja=loja, cliente=cliente, valor=Decimal('5.00'), observacao="")
        recente = Venda.objects.create(loja=loja, cliente=cliente, valor_total=Decimal('7.00'),
                                       data_venda=pagamento.data_pagamento + timedelta(hours=1))

        movimentos = linha_do_tempo(cliente)

        self.assertEqual([m.tipo for m in movimentos], ['compra', 'pagamento', 'compra'])
        self.assertEqual(movimentos[0].descricao, f"Compra de Produtos (Venda #{recente.pk})")
        self.assertEqual(movimentos[1], Movimento(
            tipo='pagamento', data=pagamento.data_pagamento,
            descricao="Pagamento Recebido (Caderneta)", valor=Decimal('5.00'),
        ))
        self.assertEqual(movimentos[2].itens, (item,))
        self.assertEqual(movimentos[2].observacao, "fiado")

    def test_cliente_sem_movimentos(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.assertEqual(linha_do_tempo(Cliente.objects.create(loja=loja, nome="Ana")), [])
