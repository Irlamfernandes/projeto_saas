from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from infrastructure.models import Acao, RegistroDeAlteracao
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, ProdutoImagem, Variacao
from tests.apoio import URL_PUBLICA, StorageFalso, imagem_de_teste

User = get_user_model()
STORAGE = 'application.produtos.services.SupabaseStorage.from_settings'


class ProdutoEditarViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(deve_trocar_senha=False, username="admin", password="password")
        self.user_loja1 = User.objects.create_user(deve_trocar_senha=False, username="user_loja1", password="password", loja=self.loja1)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(deve_trocar_senha=False, username="user_sem_loja", password="password", loja=None)

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
        self.assertContains(response, "Cada produto pode ter até 5 fotos: dá para adicionar mais 5")
        self.assertContains(response, 'data-maximo-fotos="5"')

    def variacoes(self, *linhas):
        return dict(zip(('variacao_id', 'variacao_nome', 'variacao_acrescimo', 'variacao_quantidade'),
                        map(list, zip(*linhas, strict=True)), strict=True))

    def test_variacoes_vem_preenchidas_e_sao_salvas_com_historico(self):
        azul = Variacao.objects.create(produto=self.produto, nome="Azul P", quantidade_estoque=6)
        branca = Variacao.objects.create(produto=self.produto, nome="Branca P", quantidade_estoque=4, acrescimo=Decimal('2.5'))
        self.client.force_login(self.user_loja1)
        pagina = self.client.get(self.url)
        self.assertContains(pagina, f'name="variacao_id" value="{azul.pk}"')
        self.assertContains(pagina, 'value="Branca P"')
        self.assertContains(pagina, 'name="variacao_acrescimo" value="2.5"')
        self.assertContains(pagina, 'data-maximo="100" open')

        self._editar(**self.variacoes((str(azul.pk), 'Azul PP', '', '8'), ('', 'Verde M', '1,00', '3')))

        self.produto.refresh_from_db()
        self.assertEqual(
            [(v.nome, v.acrescimo, v.quantidade_estoque) for v in self.produto.variacoes.all()],
            [("Azul PP", Decimal('0.00'), Decimal('8')), ("Verde M", Decimal('1.00'), Decimal('3'))],
        )
        self.assertEqual(self.produto.variacoes.get(nome="Azul PP").pk, azul.pk)  # a mesma, renomeada
        self.assertFalse(Variacao.objects.filter(pk=branca.pk).exists())
        self.assertEqual(self.produto.quantidade_estoque, Decimal('11'))  # a soma, não os 15 digitados
        alteracoes = RegistroDeAlteracao.objects.get(acao=Acao.PRODUTO_EDITADO).detalhes['alteracoes']
        self.assertEqual(alteracoes['variacoes'][1], [
            {'nome': 'Azul PP', 'acrescimo': '0.00', 'quantidade_estoque': '8.00'},
            {'nome': 'Verde M', 'acrescimo': '1.00', 'quantidade_estoque': '3.00'},
        ])

    def test_trocar_os_nomes_entre_si_na_mesma_edicao(self):
        azul = Variacao.objects.create(produto=self.produto, nome="Azul")
        branca = Variacao.objects.create(produto=self.produto, nome="Branca")

        self._editar(**self.variacoes((str(azul.pk), 'Branca', '', '1'), (str(branca.pk), 'Azul', '', '2')))

        azul.refresh_from_db()
        branca.refresh_from_db()
        self.assertEqual((azul.nome, branca.nome), ("Branca", "Azul"))

    def test_variacao_invalida_mostra_o_erro_e_nao_salva(self):
        response = self._editar(**self.variacoes(('', '', '', '2')))

        self.assertIn("Dê um nome para cada variação (ex.: Azul P, Chocolate).", self._mensagens(response))
        self.assertFalse(self.produto.variacoes.exists())

    def test_variacao_de_outro_produto_e_recusada(self):
        de_fora = Variacao.objects.create(produto=self.produto_loja2, nome="Dela")

        response = self._editar(**self.variacoes((str(de_fora.pk), 'Minha', '', '1')))

        self.assertIn("Uma das variações não existe mais. Abra o produto de novo e refaça a alteração.",
                      self._mensagens(response))
        de_fora.refresh_from_db()
        self.assertEqual(de_fora.nome, "Dela")

    def test_produto_com_5_fotos_pede_para_remover_antes(self):
        for _ in range(5):
            ProdutoImagem.objects.create(produto=self.produto, imagem_url=f"{URL_PUBLICA}/1/f.webp")
        self.client.force_login(self.user_loja1)

        self.assertContains(self.client.get(self.url), "remova alguma para adicionar outra")

    def test_passar_do_limite_de_fotos_mostra_o_erro(self):
        response = self._editar(imagens=[imagem_de_teste() for _ in range(6)])

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertIn("Cada produto pode ter no máximo 5 fotos. Dá para adicionar mais 5.", self._mensagens(response))

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
            [f"{URL_PUBLICA}/{self.produto.pk}/nova.webp"],
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
