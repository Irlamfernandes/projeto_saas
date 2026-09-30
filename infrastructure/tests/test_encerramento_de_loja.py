from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from application.lojas.encerramento import apagar_loja, lojas_para_apagar
from infrastructure.models import (
    Cliente, Compra, Despesa, ItemCompra, ItemVenda, LojaModel, Perda, Produto, ProdutoImagem, RegistroDeAlteracao, Venda,
)
from tests.apoio import StorageFalso

HOJE = timezone.localdate()
User = get_user_model()


def loja_completa(nome, vencimento=HOJE):
    """Uma loja com tudo o que pode ter: produto com foto, venda, compra, perda, despesa, cliente, usuário e marca."""
    loja = LojaModel.objects.create(nome_loja=nome, vencimento=vencimento, logo_url=f'https://x/storage/{nome}/marca.webp')
    produto = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('10'), quantidade_estoque=5)
    ProdutoImagem.objects.create(produto=produto, imagem_url=f'https://x/storage/{nome}/foto.webp')
    cliente = Cliente.objects.create(loja=loja, nome="Maria")
    venda = Venda.objects.create(loja=loja, cliente=cliente, valor_total=Decimal('10'))
    ItemVenda.objects.create(venda=venda, produto=produto, quantidade=1, preco_unitario=Decimal('10'))
    compra = Compra.objects.create(loja=loja)
    ItemCompra.objects.create(compra=compra, produto=produto, quantidade=1, custo_unitario=Decimal('4'))
    Perda.objects.create(loja=loja, produto=produto, quantidade=1, motivo="Venceu")
    Despesa.objects.create(loja=loja, categoria="Luz", valor=Decimal('50'))
    RegistroDeAlteracao.objects.create(loja=loja, acao='cliente_cadastrado', descricao="Maria")
    User.objects.create_user(username=f"caixa-{nome}", password="x", loja=loja)
    return loja


class ApagarLojaTest(TestCase):

    def test_apaga_tudo_da_loja_e_os_arquivos_e_nada_das_outras(self):
        loja, outra = loja_completa("a"), loja_completa("b")
        storage = StorageFalso()

        apagar_loja(loja, storage)

        self.assertFalse(LojaModel.objects.filter(pk=loja.pk).exists())
        for modelo in (Produto, ProdutoImagem, Cliente, Venda, ItemVenda, Compra, ItemCompra, Perda, Despesa, RegistroDeAlteracao):
            with self.subTest(modelo.__name__):
                self.assertEqual(modelo.objects.count(), 1)  # só o da outra loja
        self.assertEqual(list(User.objects.values_list('username', flat=True)), ["caixa-b"])
        self.assertEqual(sorted(storage.removidos), ['https://x/storage/a/foto.webp', 'https://x/storage/a/marca.webp'])
        self.assertTrue(LojaModel.objects.filter(pk=outra.pk).exists())

    def test_loja_sem_marca(self):
        loja = LojaModel.objects.create(nome_loja="Sem marca")
        with patch('application.lojas.encerramento.SupabaseStorage.from_settings', return_value=StorageFalso()) as fonte:
            apagar_loja(loja)
        self.assertEqual(fonte.return_value.removidos, [])

    def test_quais_passaram_dos_90_dias(self):
        LojaModel.objects.create(nome_loja="Em dia", vencimento=HOJE + timedelta(days=10))
        LojaModel.objects.create(nome_loja="Vencida há 90", vencimento=HOJE - timedelta(days=90))
        LojaModel.objects.create(nome_loja="Vencida há 91", vencimento=HOJE - timedelta(days=91))
        self.assertEqual(list(lojas_para_apagar(LojaModel.objects.all()).values_list('nome_loja', flat=True)),
                         ["Vencida há 91"])


class ApagarLojaPeloAdminTest(TestCase):

    def setUp(self):
        self.dono = User.objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.force_login(self.dono)
        self.loja = loja_completa("velha", vencimento=HOJE - timedelta(days=120))
        self.storage = patch('application.lojas.encerramento.SupabaseStorage.from_settings', return_value=StorageFalso())
        self.storage.start()
        self.addCleanup(self.storage.stop)

    def test_lista_mostra_e_filtra_quem_passou_do_prazo(self):
        LojaModel.objects.create(nome_loja="Nova", vencimento=HOJE + timedelta(days=30))
        lista = self.client.get('/admin/infrastructure/lojamodel/')
        self.assertContains(lista, "Vencido há +90 dias: apagar")
        filtrada = self.client.get('/admin/infrastructure/lojamodel/?dados=apagar')
        self.assertContains(filtrada, "velha")
        self.assertNotContains(filtrada, "Nova")

    def test_confirmacao_nao_trava_nas_vendas_e_apaga_tudo(self):
        url = f'/admin/infrastructure/lojamodel/{self.loja.pk}/delete/'
        confirmacao = self.client.get(url)
        self.assertContains(confirmacao, 'name="post"')  # dá para confirmar (não há "objetos protegidos")
        self.client.post(url, {'post': 'yes'})
        self.assertFalse(LojaModel.objects.exists())
        self.assertFalse(ItemVenda.objects.exists())

    def test_apagar_varias_pela_acao_da_lista(self):
        segunda = loja_completa("outra", vencimento=HOJE - timedelta(days=200))
        self.client.post('/admin/infrastructure/lojamodel/', {
            'action': 'delete_selected', '_selected_action': [self.loja.pk, segunda.pk], 'post': 'yes',
        })
        self.assertFalse(LojaModel.objects.exists())
