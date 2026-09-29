from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [('infrastructure', '0025_backup')]
DEPOIS = [('infrastructure', '0026_clientes_no_historico')]


class ClientesNoHistoricoAntigoTest(TransactionTestCase):
    """Os registros de antes da ligação com o cliente são ligados pelo formato exato da descrição."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def tearDown(self):
        self.migrar(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_liga_so_o_que_cita_o_cliente(self):
        apps = self.migrar(ANTES)
        Loja = apps.get_model('infrastructure', 'LojaModel')
        Cliente = apps.get_model('infrastructure', 'Cliente')
        Registro = apps.get_model('infrastructure', 'RegistroDeAlteracao')
        loja, outra_loja = Loja.objects.create(nome_loja="A"), Loja.objects.create(nome_loja="B")
        ana = Cliente.objects.create(loja=loja, nome="Ana")
        Cliente.objects.create(loja=loja, nome="")
        registros = {
            'cadastro': Registro.objects.create(loja=loja, acao='cliente_cadastrado', descricao="Ana"),
            'pagamento': Registro.objects.create(loja=loja, acao='pagamento_registrado', descricao="Ana · R$ 10,00 · Pix"),
            'venda': Registro.objects.create(loja=loja, acao='venda_registrada', descricao="Venda #3 · Ana · R$ 10,00"),
            'outra pessoa': Registro.objects.create(loja=loja, acao='cliente_cadastrado', descricao="Banana"),
            'produto': Registro.objects.create(loja=loja, acao='produto_cadastrado', descricao="Ana"),
            'outra loja': Registro.objects.create(loja=outra_loja, acao='cliente_cadastrado', descricao="Ana"),
        }

        apps = self.migrar(DEPOIS)

        ligados = apps.get_model('infrastructure', 'RegistroDeAlteracao').objects.filter(clientes=ana.pk)
        self.assertEqual(set(ligados.values_list('pk', flat=True)),
                         {registros[nome].pk for nome in ('cadastro', 'pagamento', 'venda')})
