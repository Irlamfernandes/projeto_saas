from django.test import SimpleTestCase
from infrastructure.models import ItemCompra, ItemVenda, ProdutoImagem


class OrdemDosItensTest(SimpleTestCase):
    """Itens aparecem na ordem em que foram lançados (mensagem de cobrança, extrato, PDF, compras) e a primeira foto
    é a capa do produto. Sem ordem no modelo o Postgres devolve em qualquer ordem; o SQLite dos testes locais, não."""

    def test_na_ordem_em_que_foram_lancados(self):
        for modelo in (ItemVenda, ItemCompra, ProdutoImagem):
            with self.subTest(modelo.__name__):
                self.assertEqual(modelo._meta.ordering, ['pk'])
