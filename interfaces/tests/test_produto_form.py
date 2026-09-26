from decimal import Decimal
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from infrastructure.models import LojaModel, Produto
from interfaces.forms import EditarProdutoForm, FiltroProdutosForm, ProdutoForm
from interfaces.views.comum import primeiro_erro
from tests.apoio import imagem_de_teste


class ProdutoFormTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")

    def _form(self, arquivos=None, **dados):
        base = {'nome': 'Bolo', 'preco_venda': '30.00', 'quantidade_estoque': '1'}
        return ProdutoForm({**base, **dados}, arquivos or {}, instance=Produto(loja=self.loja))

    def assertErro(self, form, mensagem):
        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), mensagem)

    def test_aceita_virgula_ou_ponto_como_separador_decimal(self):
        form = self._form(preco_venda='199,99', preco_custo='100.50')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.preco_venda, Decimal('199.99'))
        self.assertEqual(form.instance.preco_custo, Decimal('100.50'))

    def test_campos_opcionais_vazios_viram_zero(self):
        form = self._form(preco_custo='', margem_lucro='', quantidade_estoque='')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            (form.instance.preco_custo, form.instance.margem_lucro, form.instance.quantidade_estoque),
            (Decimal('0.00'), Decimal('0.00'), 0),
        )

    def test_mensagens_de_erro(self):
        casos = {
            'sem nome': ({'nome': ''}, "O nome do produto é obrigatório."),
            'nome longo': ({'nome': 'a' * 151}, "O nome pode ter no máximo 150 caracteres."),
            'código longo': ({'codigo_interno': '1' * 51}, "O código interno pode ter no máximo 50 caracteres."),
            'sem preço': ({'preco_venda': ''}, "Informe o preço de venda."),
            'preço texto': ({'preco_venda': 'abc'}, "Preço de venda inválido."),
            'preço zero': ({'preco_venda': '0'}, "O preço de venda deve ser maior que zero."),
            'custo negativo': ({'preco_custo': '-1'}, "O preço de custo não pode ser negativo."),
            'estoque texto': ({'quantidade_estoque': 'xyz'}, "Quantidade em estoque inválida."),
            'estoque negativo': ({'quantidade_estoque': '-1'}, "A quantidade em estoque não pode ser negativa."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                self.assertErro(self._form(**dados), mensagem)

    def test_aceita_varias_imagens(self):
        form = self._form(arquivos={'imagens': [imagem_de_teste('a.png'), imagem_de_teste('b.jpg', 'JPEG')]})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual([img.name for img in form.parametros()['imagens']], ['a.png', 'b.jpg'])

    def test_sem_imagens_retorna_lista_vazia(self):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {'produto': form.instance, 'imagens': []})

    def test_recusa_arquivo_que_nao_e_imagem(self):
        falso = SimpleUploadedFile('virus.png', b'<script>alert(1)</script>', content_type='image/png')
        self.assertErro(self._form(arquivos={'imagens': [falso]}), "Envie apenas imagens válidas (JPG, PNG ou WEBP).")

    def test_recusa_formato_fora_da_lista(self):
        gif = imagem_de_teste('anim.gif', 'GIF')
        self.assertErro(self._form(arquivos={'imagens': [gif]}), "Envie apenas imagens JPG, PNG ou WEBP.")

    def test_recusa_imagem_grande_demais(self):
        with patch('interfaces.forms.produto_form.TAMANHO_MAXIMO_IMAGEM', 10):
            self.assertErro(self._form(arquivos={'imagens': [imagem_de_teste('g.png')]}), "A imagem 'g.png' excede o limite de 5 MB.")


class EditarProdutoFormTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.produto = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('30.00'))

    def _form(self, remover):
        dados = {'nome': 'Bolo', 'preco_venda': '30', 'remover_imagens': remover}
        return EditarProdutoForm(dados, {}, instance=self.produto)

    def test_converte_ids_para_remover(self):
        form = self._form(" 3, 7 ,,")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {
            'produto': self.produto, 'imagens_novas': [], 'ids_imagens_remover': [3, 7],
        })

    def test_vazio_nao_remove_nada(self):
        form = self._form("")
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros()['ids_imagens_remover'], [])

    def test_ids_invalidos(self):
        form = self._form("3,abc")
        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), "Seleção de imagens para remover inválida.")


class FiltroProdutosFormTest(TestCase):

    def test_criterios(self):
        form = FiltroProdutosForm({'q': ' bolo ', 'categoria': 'Doces', 'ordem': 'nome', 'baixo_estoque': '1'})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.criterios(), {
            'busca': 'bolo', 'categoria': 'Doces', 'baixo_estoque': True, 'ordem': 'nome',
        })

    def test_ordem_desconhecida_usa_o_padrao(self):
        form = FiltroProdutosForm({'ordem': 'senha; DROP TABLE'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.criterios()['ordem'], '-data_criacao')

    def test_termos_longos_demais(self):
        for campo, mensagem in [('q', "O termo de busca é muito longo."), ('categoria', "O filtro de categoria é inválido.")]:
            with self.subTest(campo):
                form = FiltroProdutosForm({campo: 'a' * 101})
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), mensagem)
