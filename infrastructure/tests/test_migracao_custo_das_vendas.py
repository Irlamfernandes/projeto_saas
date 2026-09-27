from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [('infrastructure', '0020_unidades_e_controle_de_estoque')]
DEPOIS = [('infrastructure', '0021_compras_despesas_e_perdas')]


class CustoDasVendasAntigasTest(TransactionTestCase):
    """As vendas de antes do custo guardado ficam com o custo atual do produto (o lucro do passado não muda)."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def tearDown(self):
        self.migrar(executor_final())

    def test_itens_antigos_recebem_o_custo_atual_do_produto(self):
        apps = self.migrar(ANTES)
        loja = apps.get_model('infrastructure', 'LojaModel').objects.create(nome_loja="Loja")
        produto = apps.get_model('infrastructure', 'Produto').objects.create(
            loja=loja, nome="Bolo", preco_venda=Decimal('20'), preco_custo=Decimal('8.50'),
        )
        venda = apps.get_model('infrastructure', 'Venda').objects.create(loja=loja, valor_total=Decimal('40'))
        apps.get_model('infrastructure', 'ItemVenda').objects.create(
            venda=venda, produto=produto, quantidade=2, preco_unitario=Decimal('20'),
        )

        apps = self.migrar(DEPOIS)

        self.assertEqual(apps.get_model('infrastructure', 'ItemVenda').objects.get().custo_unitario, Decimal('8.50'))


def executor_final():
    executor = MigrationExecutor(connection)
    return executor.loader.graph.leaf_nodes()
