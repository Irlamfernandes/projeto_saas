from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, ProdutoImagem
from tests.apoio import StorageFalso, foto_heic_de_teste, imagem_de_teste

User = get_user_model()
STORAGE = 'application.produtos.services.SupabaseStorage.from_settings'


class ProdutosViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(deve_trocar_senha=False, username="admin", password="password")
        self.user_loja1 = User.objects.create_user(deve_trocar_senha=False, username="user_loja1", password="password", loja=self.loja1)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(deve_trocar_senha=False, username="user_sem_loja", password="password", loja=None)

        self.produto_l1 = Produto.objects.create(
            loja=self.loja1, codigo_interno="COD01", nome="Camiseta Polo", categoria="Vestuário",
            preco_venda=Decimal('50.00'), quantidade_estoque=2,
        )
        self.produto_l2 = Produto.objects.create(
            loja=self.loja2, codigo_interno="COD02", nome="Calça Jeans", categoria="Vestuário",
            preco_venda=Decimal('100.00'), quantidade_estoque=20,
        )
        self.url = reverse('produtos')
        self.storage = StorageFalso()

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _cadastrar(self, usuario=None, **dados):
        self.client.force_login(usuario or self.user_loja1)
        with patch(STORAGE, return_value=self.storage):
            return self.client.post(self.url, {'nome': 'Tênis', 'preco_venda': '199,99', **dados})

    # --- listagem ---------------------------------------------------------

    def test_usuario_sem_loja_recebe_permission_denied(self):
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_usuario_comum_ve_apenas_produtos_da_sua_loja(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url)

        self.assertContains(response, "Camiseta Polo")
        self.assertNotContains(response, "Calça Jeans")

    def test_superuser_ve_todos_os_produtos(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url)

        self.assertContains(response, "Camiseta Polo")
        self.assertContains(response, "Calça Jeans")

    def test_filtros_sao_aplicados_e_devolvidos_ao_template(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url, {'q': 'COD01', 'categoria': 'Vestuário', 'baixo_estoque': '1', 'ordem': 'nome'})

        self.assertEqual(list(response.context['produtos']), [self.produto_l1])
        self.assertEqual(response.context['filtro_busca'], 'COD01')
        self.assertEqual(response.context['filtro_categoria'], 'Vestuário')
        self.assertEqual(response.context['filtro_ordem'], 'nome')
        self.assertTrue(response.context['filtro_baixo_estoque'])
        self.assertEqual(response.context['categorias_existentes'], ['Vestuário'])

    def test_ordenacao_invalida_usa_o_padrao(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.url, {'ordem': 'coluna_proibida'})
        self.assertEqual(response.context['filtro_ordem'], '-data_criacao')

    def test_filtro_invalido_redireciona_com_erro(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url, {'q': 'a' * 101})

        self.assertRedirects(response, self.url)
        self.assertEqual(self._mensagens(response), ["O termo de busca é muito longo."])

    def test_url_de_imagem_e_escapada_no_javascript_da_galeria(self):
        """Regressão: aspas na URL da imagem permitiam injetar JavaScript no onclick (XSS).

        Hoje a lista vai num atributo data-* (escapado pelo Django) e não há onclick; a CSP também barraria.
        """
        ProdutoImagem.objects.create(produto=self.produto_l1, imagem_url="https://x.co/a.png');alert(1);//")
        self.client.force_login(self.user_loja1)

        response = self.client.get(self.url)

        self.assertNotContains(response, 'onclick')
        self.assertContains(response, 'data-galeria="https://x.co/a.png&#x27;);alert(1);//')

    # --- cadastro ---------------------------------------------------------

    def test_cadastra_produto_na_loja_do_usuario(self):
        response = self._cadastrar(preco_custo='100,00', quantidade_estoque='10', categoria='Calçados')

        self.assertRedirects(response, self.url)
        produto = Produto.objects.get(nome='Tênis')
        self.assertEqual(produto.loja, self.loja1)
        self.assertEqual(produto.preco_venda, Decimal('199.99'))
        self.assertEqual(self._mensagens(response), ["Produto e imagens cadastrados com sucesso!"])

    def test_cadastra_produto_com_varias_imagens(self):
        self._cadastrar(imagens=[imagem_de_teste('f1.png'), imagem_de_teste('f2.png')])

        produto = Produto.objects.get(nome='Tênis')
        self.assertEqual(produto.imagens.count(), 2)
        self.assertEqual(len(self.storage.enviados), 2)

    def test_foto_heic_do_celular_e_aceita_e_vira_webp(self):
        self._cadastrar(imagens=[foto_heic_de_teste('IMG_0001.HEIC')])

        produto = Produto.objects.get(nome='Tênis')
        self.assertEqual(produto.imagens.count(), 1)
        self.assertTrue(self.storage.enviados[0].endswith('/IMG_0001.webp'))

    def test_campo_de_fotos_deixa_escolher_qualquer_foto_do_celular(self):
        self.client.force_login(self.user_loja1)
        self.assertContains(self.client.get(self.url), 'accept="image/*,.heic,.heif"')

    def test_cadastra_por_quilo_e_sem_controle_de_estoque(self):
        self._cadastrar(nome='Queijo', unidade='kg', quantidade_estoque='2.5')
        self._cadastrar(nome='Bolo', sem_controle_de_estoque='1')

        queijo, bolo = Produto.objects.get(nome='Queijo'), Produto.objects.get(nome='Bolo')
        self.assertEqual((queijo.unidade, queijo.quantidade_estoque), ('kg', Decimal('2.500')))
        self.assertFalse(bolo.controla_estoque)

        response = self.client.get(self.url)
        self.assertContains(response, '2,5 kg')
        self.assertContains(response, 'Sem controle de estoque')
        self.assertContains(response, 'data-estoque-produto')
        self.assertContains(response, 'value="kg" data-sigla="kg" data-casas="3"')

    def test_dados_invalidos_nao_cadastram(self):
        response = self._cadastrar(nome='')

        self.assertRedirects(response, self.url)
        self.assertEqual(self._mensagens(response), ["O nome do produto é obrigatório."])
        self.assertFalse(Produto.objects.filter(loja=self.loja1, nome='').exists())

    def test_arquivo_que_nao_e_imagem_e_recusado_antes_do_envio(self):
        falso = imagem_de_teste('ok.png')
        falso.file.write(b'lixo')
        falso.file.seek(0)
        falso.file.truncate(4)

        response = self._cadastrar(imagens=[falso])

        self.assertEqual(self._mensagens(response), ["Envie apenas imagens válidas (JPG, PNG, WEBP ou HEIC)."])
        self.assertEqual(self.storage.enviados, [])

    def test_superuser_sem_loja_nao_cadastra(self):
        response = self._cadastrar(usuario=self.superuser)

        self.assertEqual(self._mensagens(response), ["Superusuários devem associar o produto a uma loja específica."])
        self.assertFalse(Produto.objects.filter(nome='Tênis').exists())

    def test_falha_no_storage_mostra_mensagem_amigavel_e_nao_salva(self):
        """Antes o erro interno (str(e)) era exibido ao usuário e o produto ficava salvo sem imagens."""
        self.storage = StorageFalso(falhar_no_envio=0)

        with self.assertLogs('application.produtos.services', 'ERROR'):
            response = self._cadastrar(imagens=[imagem_de_teste()])

        self.assertEqual(
            self._mensagens(response),
            ["Não foi possível enviar as imagens agora. Nada foi salvo; tente novamente."],
        )
        self.assertFalse(Produto.objects.filter(nome='Tênis').exists())
