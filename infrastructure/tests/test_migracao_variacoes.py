from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [('infrastructure', '0028_cpf_do_cliente')]
DEPOIS = [('infrastructure', '0029_variacoes_do_produto')]
TAMANHO_E_COR = [
    {'nome': 'Tamanho', 'valores': [{'nome': 'P', 'acrescimo': '0.00'}, {'nome': 'G', 'acrescimo': '5.00'}]},
    {'nome': 'Cor', 'valores': [{'nome': 'Azul', 'acrescimo': '0.00'}, {'nome': 'Ouro', 'acrescimo': '2.50'}]},
]


class OpcoesViramVariacoesTest(TransactionTestCase):
    """As opções antigas (só anotavam a escolha) viram variações, uma por combinação."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def tearDown(self):
        self.migrar(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_combinacoes_viram_variacoes_e_as_vendas_ficam_ligadas(self):
        apps = self.migrar(ANTES)
        loja = apps.get_model('infrastructure', 'LojaModel').objects.create(nome_loja="A")
        Produto = apps.get_model('infrastructure', 'Produto')
        camiseta = Produto.objects.create(loja=loja, nome="Camiseta", preco_venda=40, quantidade_estoque=7, opcoes=TAMANHO_E_COR)
        bolo = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=30, quantidade_estoque=0, controla_estoque=False,
                                      opcoes=[{'nome': 'Sabor', 'valores': [{'nome': 'Coco', 'acrescimo': '0'}] * 2}])
        Produto.objects.create(loja=loja, nome="Arroz", preco_venda=20, quantidade_estoque=3)
        venda = apps.get_model('infrastructure', 'Venda').objects.create(loja=loja)
        Item = apps.get_model('infrastructure', 'ItemVenda')
        item = Item.objects.create(venda=venda, produto=camiseta, quantidade=1, preco_unitario=45,
                                   opcoes=[{'nome': 'Tamanho', 'valor': 'G'}, {'nome': 'Cor', 'valor': 'Azul'}])
        sumida = Item.objects.create(venda=venda, produto=camiseta, quantidade=1, preco_unitario=40,
                                     opcoes=[{'nome': 'Tamanho', 'valor': 'GG'}, {'nome': 'Cor', 'valor': 'Azul'}])

        apps = self.migrar(DEPOIS)

        Variacao = apps.get_model('infrastructure', 'Variacao')
        self.assertEqual(
            list(Variacao.objects.filter(produto=camiseta.pk).values_list('nome', 'acrescimo', 'quantidade_estoque')),
            [("P, Azul", Decimal('0.00'), Decimal('7')), ("P, Ouro", Decimal('2.50'), Decimal('0')),
             ("G, Azul", Decimal('5.00'), Decimal('0')), ("G, Ouro", Decimal('7.50'), Decimal('0'))],
        )
        # Sem controle de estoque, nada fica com quantidade; valor repetido vira uma variação só.
        self.assertEqual(list(Variacao.objects.filter(produto=bolo.pk).values_list('nome', 'quantidade_estoque')),
                         [("Coco", Decimal('0'))])
        self.assertEqual(Variacao.objects.count(), 5)
        Item = apps.get_model('infrastructure', 'ItemVenda')
        self.assertEqual(Item.objects.get(pk=item.pk).variacao.nome, "G, Azul")
        self.assertIsNone(Item.objects.get(pk=sumida.pk).variacao)

    def test_voltar_atras_vira_uma_opcao_variacao(self):
        apps = self.migrar(DEPOIS)
        loja = apps.get_model('infrastructure', 'LojaModel').objects.create(nome_loja="A")
        blusa = apps.get_model('infrastructure', 'Produto').objects.create(loja=loja, nome="Blusa", preco_venda=40,
                                                                           quantidade_estoque=15)
        Variacao = apps.get_model('infrastructure', 'Variacao')
        Variacao.objects.create(produto=blusa, nome="Azul P", quantidade_estoque=10)
        Variacao.objects.create(produto=blusa, nome="Branca P", quantidade_estoque=5, acrescimo=Decimal('2.5'))

        apps = self.migrar(ANTES)

        produto = apps.get_model('infrastructure', 'Produto').objects.get(pk=blusa.pk)
        self.assertEqual(produto.opcoes, [{'nome': 'Variação', 'valores': [
            {'nome': 'Azul P', 'acrescimo': '0.00'}, {'nome': 'Branca P', 'acrescimo': '2.50'},
        ]}])
        self.assertEqual(produto.quantidade_estoque, 15)
