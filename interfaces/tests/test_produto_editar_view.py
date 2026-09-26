from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, ProdutoImagem
from tests.apoio import URL_PUBLICA, StorageFalso, imagem_de_teste

User = get_user_model()
STORAGE = 'application.produtos.services.SupabaseStorage.from_settings'


class ProdutoEditarViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(username="admin", password="password")
        self.user_loja1 = User.objects.create_user(username="user_loja1", password="password", loja=self.loja1)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(username="user_sem_loja", password="password", loja=None)

        self.produto = Produto.objects.create(
            loja=self.loja1, nome="Produto Antigo", preco_custo=Decimal('10.00'),
            preco_venda=Decimal('20.00'), quantidade_estoque=10,
        )
        self.produto_loja2 = Produto.objects.create(
            loja=self.loja2, nome="Produto Outra Loja", preco_venda=Decimal('30.00'), quantidade_estoque=5,
        )
        self.url = reverse('editar_produto', args=[self.produto.pk])
        self.url_produtos = reverse('produtos')
        self.storage = StorageFalso()

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _editar(self, usuario=None, url=None, **dados):
        self.client.force_login(usuario or self.user_loja1)
        base = {'nome': 'Produto Atualizado', 'preco_venda': '25,50', 'preco_custo': '12.00', 'quantidade_estoque': '15'}
        with patch(STORAGE, return_value=self.storage), self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url or self.url, {**base, **dados})

    def test_usuario_sem_loja_recebe_permission_denied(self):
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_get_exibe_formulario(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url)

        self.assertTemplateUsed(response, 'interfaces/produto_editar.html')
        self.assertEqual(response.context['produto'], self.produto)

    def test_edita_produto_da_propria_loja(self):
        response = self._editar()

        self.assertRedirects(response, self.url_produtos)
        self.produto.refresh_from_db()
        self.assertEqual(
            (self.produto.nome, self.produto.preco_venda, self.produto.quantidade_estoque),
            ('Produto Atualizado', Decimal('25.50'), 15),
        )

    def test_nao_edita_produto_de_outra_loja(self):
        url = reverse('editar_produto', args=[self.produto_loja2.pk])
        self.assertEqual(self._editar(url=url).status_code, 404)

    def test_superuser_edita_produto_de_qualquer_loja(self):
        url = reverse('editar_produto', args=[self.produto_loja2.pk])
        self.assertRedirects(self._editar(usuario=self.superuser, url=url), self.url_produtos)
        self.produto_loja2.refresh_from_db()
        self.assertEqual(self.produto_loja2.nome, 'Produto Atualizado')

    def test_dados_invalidos_voltam_para_a_edicao_sem_alterar(self):
        response = self._editar(nome='', preco_venda='abc')

        self.assertRedirects(response, self.url)
        self.assertEqual(self._mensagens(response), ["O nome do produto é obrigatório."])
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, 'Produto Antigo')

    def test_troca_imagens(self):
        antiga = ProdutoImagem.objects.create(produto=self.produto, imagem_url=f"{URL_PUBLICA}/1/antiga.png")

        response = self._editar(remover_imagens=str(antiga.pk), imagens=[imagem_de_teste('nova.png')])

        self.assertRedirects(response, self.url_produtos)
        self.assertEqual(
            list(self.produto.imagens.values_list('imagem_url', flat=True)),
            [f"{URL_PUBLICA}/{self.produto.pk}/nova.png"],
        )
        self.assertEqual(self.storage.removidos, [antiga.imagem_url])

    def test_selecao_de_remocao_invalida(self):
        response = self._editar(remover_imagens='1,abc')
        self.assertEqual(self._mensagens(response), ["Seleção de imagens para remover inválida."])

    def test_falha_no_storage_nao_altera_o_produto(self):
        self.storage = StorageFalso(falhar_no_envio=0)

        with self.assertLogs('application.produtos.services', 'ERROR'):
            response = self._editar(imagens=[imagem_de_teste()])

        self.assertRedirects(response, self.url)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, 'Produto Antigo')
