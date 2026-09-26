from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from application.produtos.exceptions import FalhaNoEnvioDeImagem, ProdutoSemLoja
from application.produtos.services import atualizar_produto, cadastrar_produto
from infrastructure.models import LojaModel, Produto
from infrastructure.models.produto import ProdutoImagem
from tests.apoio import URL_PUBLICA, StorageFalso, imagem_de_teste


class CadastrarProdutoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.storage = StorageFalso()

    def _novo(self, loja=None):
        return Produto(loja=loja, nome="Bolo", preco_venda=Decimal('30.00'))

    def test_salva_produto_e_anexa_imagens_na_pasta_do_produto(self):
        produto = cadastrar_produto(
            self._novo(self.loja), [imagem_de_teste('a.png'), imagem_de_teste('b.png')], storage=self.storage,
        )

        self.assertEqual(
            sorted(produto.imagens.values_list('imagem_url', flat=True)),
            [f"{URL_PUBLICA}/{produto.pk}/a.png", f"{URL_PUBLICA}/{produto.pk}/b.png"],
        )

    def test_sem_imagens_nao_usa_o_storage(self):
        with patch('application.produtos.services.SupabaseStorage.from_settings') as fabrica:
            cadastrar_produto(self._novo(self.loja))
        fabrica.return_value.enviar.assert_not_called()
        self.assertEqual(Produto.objects.count(), 1)

    def test_produto_sem_loja_e_recusado(self):
        with self.assertRaises(ProdutoSemLoja):
            cadastrar_produto(self._novo(), storage=self.storage)
        self.assertFalse(Produto.objects.exists())

    def test_falha_no_envio_desfaz_o_cadastro(self):
        storage = StorageFalso(falhar_no_envio=1)

        with self.assertLogs('application.produtos.services', 'ERROR'), self.assertRaises(FalhaNoEnvioDeImagem):
            cadastrar_produto(self._novo(self.loja), [imagem_de_teste(), imagem_de_teste()], storage=storage)

        self.assertFalse(Produto.objects.exists())
        self.assertFalse(ProdutoImagem.objects.exists())
        self.assertEqual(storage.removidos, storage.enviados, "arquivo já enviado não pode ficar órfão no bucket")
        self.assertEqual(len(storage.removidos), 1)

    def test_erro_no_banco_apos_envio_tambem_apaga_o_arquivo(self):
        with patch('application.produtos.services.ProdutoImagem.objects.create', side_effect=RuntimeError("banco caiu")):
            with self.assertRaises(RuntimeError):
                cadastrar_produto(self._novo(self.loja), [imagem_de_teste()], storage=self.storage)

        self.assertEqual(self.storage.removidos, self.storage.enviados)
        self.assertEqual(len(self.storage.removidos), 1)


class AtualizarProdutoTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.produto = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('30.00'))
        self.outro = Produto.objects.create(loja=loja, nome="Torta", preco_venda=Decimal('40.00'))
        self.foto_antiga = ProdutoImagem.objects.create(produto=self.produto, imagem_url=f"{URL_PUBLICA}/1/antiga.png")
        self.foto_mantida = ProdutoImagem.objects.create(produto=self.produto, imagem_url=f"{URL_PUBLICA}/1/mantida.png")
        self.foto_do_outro = ProdutoImagem.objects.create(produto=self.outro, imagem_url=f"{URL_PUBLICA}/2/outro.png")
        self.storage = StorageFalso()

    def test_salva_campos_remove_marcadas_e_anexa_novas(self):
        self.produto.nome = "Bolo de Cenoura"

        with self.captureOnCommitCallbacks(execute=True):
            atualizar_produto(
                self.produto, [imagem_de_teste('nova.png')], [self.foto_antiga.pk], storage=self.storage,
            )

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, "Bolo de Cenoura")
        self.assertEqual(
            sorted(self.produto.imagens.values_list('imagem_url', flat=True)),
            [f"{URL_PUBLICA}/1/mantida.png", f"{URL_PUBLICA}/{self.produto.pk}/nova.png"],
        )
        self.assertEqual(self.storage.removidos, [self.foto_antiga.imagem_url])

    def test_arquivo_so_e_apagado_do_storage_apos_o_commit(self):
        with self.captureOnCommitCallbacks() as callbacks:
            atualizar_produto(self.produto, ids_imagens_remover=[self.foto_antiga.pk], storage=self.storage)

        self.assertEqual(self.storage.removidos, [])
        self.assertEqual(len(callbacks), 1)

    def test_ignora_imagens_de_outro_produto(self):
        with self.captureOnCommitCallbacks(execute=True):
            atualizar_produto(self.produto, ids_imagens_remover=[self.foto_do_outro.pk], storage=self.storage)

        self.assertTrue(ProdutoImagem.objects.filter(pk=self.foto_do_outro.pk).exists())
        self.assertEqual(self.storage.removidos, [])

    def test_falha_no_envio_desfaz_tudo_e_nao_apaga_arquivos(self):
        self.produto.nome = "Não deve salvar"
        storage = StorageFalso(falhar_no_envio=0)

        with self.captureOnCommitCallbacks(execute=True), self.assertLogs('application.produtos.services', 'ERROR'):
            with self.assertRaises(FalhaNoEnvioDeImagem):
                atualizar_produto(self.produto, [imagem_de_teste()], [self.foto_antiga.pk], storage=storage)

        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, "Bolo")
        self.assertTrue(ProdutoImagem.objects.filter(pk=self.foto_antiga.pk).exists())
        self.assertEqual(storage.removidos, [])
