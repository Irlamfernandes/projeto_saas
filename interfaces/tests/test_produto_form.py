from decimal import Decimal
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.test import TestCase
from infrastructure.models import LojaModel, Produto
from interfaces.forms import EditarProdutoForm, FiltroProdutosForm, ProdutoForm
from interfaces.views.comum import primeiro_erro
from tests.apoio import imagem_de_teste


def como_post(dados):
    """Como o navegador envia: listas para os campos repetidos (opcao_nome, opcao_valores)."""
    post = QueryDict(mutable=True)
    for campo, valor in dados.items():
        post.setlist(campo, valor if isinstance(valor, list) else [valor])
    return post


class ProdutoFormTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")

    def _form(self, arquivos=None, **dados):
        base = {'nome': 'Bolo', 'preco_venda': '30.00', 'quantidade_estoque': '1'}
        return ProdutoForm(como_post({**base, **dados}), arquivos or {}, instance=Produto(loja=self.loja))

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

    def test_unidade_padrao_e_estoque_com_fracao_so_nas_unidades_que_aceitam(self):
        padrao = self._form()
        self.assertTrue(padrao.is_valid(), padrao.errors)
        self.assertEqual((padrao.instance.unidade, padrao.instance.controla_estoque), ('un', True))

        por_quilo = self._form(unidade='kg', quantidade_estoque='2.350')
        self.assertTrue(por_quilo.is_valid(), por_quilo.errors)
        self.assertEqual(por_quilo.instance.quantidade_estoque, Decimal('2.350'))

        self.assertErro(self._form(unidade='un', quantidade_estoque='2.5'), "Esta unidade só aceita números inteiros no estoque.")
        self.assertErro(self._form(unidade='kg', quantidade_estoque='2.3456'),
                        "Use no máximo 3 casas depois da vírgula na quantidade em estoque.")
        self.assertErro(self._form(unidade='tonelada'), "Unidade de medida inválida.")

    def test_sem_controle_de_estoque_zera_a_quantidade(self):
        form = self._form(sem_controle_de_estoque='1', quantidade_estoque='7')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.instance.controla_estoque)
        self.assertEqual(form.instance.quantidade_estoque, Decimal('0'))

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
        self.assertErro(self._form(arquivos={'imagens': [falso]}), "Envie apenas imagens válidas (JPG, PNG, WEBP ou HEIC).")

    def test_recusa_formato_fora_da_lista(self):
        gif = imagem_de_teste('anim.gif', 'GIF')
        self.assertErro(self._form(arquivos={'imagens': [gif]}), "Envie apenas imagens JPG, PNG, WEBP ou HEIC.")

    def test_recusa_imagem_grande_demais(self):
        with patch('interfaces.forms.produto_form.TAMANHO_MAXIMO_IMAGEM', 10):
            self.assertErro(self._form(arquivos={'imagens': [imagem_de_teste('g.png')]}), "A imagem 'g.png' excede o limite de 25 MB.")


class OpcoesDoProdutoTest(ProdutoFormTest):
    """Nome da opção + valores um por linha; 'G + 5,00' cobra R$ 5 a mais."""

    def opcoes(self, nomes, valores):
        form = self._form(opcao_nome=nomes, opcao_valores=valores)
        self.assertTrue(form.is_valid(), form.errors)
        return form.instance.opcoes

    def test_le_nomes_valores_e_acrescimos(self):
        opcoes = self.opcoes([' Tamanho ', 'Cor'], ['P\r\n M \n\nG + 5,00\nGG +R$ 7.5', 'Azul'])

        self.assertEqual(opcoes, [
            {'nome': 'Tamanho', 'valores': [
                {'nome': 'P', 'acrescimo': '0.00'}, {'nome': 'M', 'acrescimo': '0.00'},
                {'nome': 'G', 'acrescimo': '5.00'}, {'nome': 'GG', 'acrescimo': '7.50'},
            ]},
            {'nome': 'Cor', 'valores': [{'nome': 'Azul', 'acrescimo': '0.00'}]},
        ])

    def test_blocos_vazios_sao_ignorados_e_sem_opcoes_fica_lista_vazia(self):
        self.assertEqual(self.opcoes(['', ' '], ['', '  ']), [])
        self.assertEqual(self._form().is_valid() and self._form().instance.opcoes, [])

    def test_mais_sem_nome_antes_e_parte_do_valor(self):
        self.assertEqual(self.opcoes(['Brinde'], ['+1'])[0]['valores'], [{'nome': '+1', 'acrescimo': '0.00'}])
        self.assertEqual(
            [valor['nome'] for valor in self.opcoes(['Tipo'], ['Tam + grande\nC++\nKit+2'])[0]['valores']],
            ['Tam + grande', 'C++', 'Kit'],
        )

    def test_mensagens_de_erro_das_opcoes(self):
        casos = {
            'sem nome': ([''], ['P'], "Dê um nome para cada opção (ex.: Tamanho, Sabor, Cor)."),
            'sem valores': (['Tamanho'], [''], 'Escreva os valores da opção "Tamanho", um por linha.'),
            'opções demais': (['A', 'B', 'C', 'D', 'E', 'F'], ['1'] * 6, "Cada produto pode ter até 5 opções."),
            'opção repetida': (['Cor', 'cor'], ['Azul', 'Preto'], 'Há duas opções chamadas "cor".'),
            'valores demais': (['Número'], ['\n'.join(map(str, range(31)))], 'A opção "Número" pode ter até 30 valores.'),
            'valor repetido': (['Tamanho'], ['P\nM\np + 2'], 'O valor "p" aparece duas vezes em "Tamanho".'),
            'nome longo': (['N' * 41], ['P'], f'"{"N" * 20}…" é longo demais: use até 40 letras em cada opção e valor.'),
            'valor longo': (['Tamanho'], ['V' * 41], f'"{"V" * 20}…" é longo demais: use até 40 letras em cada opção e valor.'),
        }
        for caso, (nomes, valores, mensagem) in casos.items():
            with self.subTest(caso):
                self.assertErro(self._form(opcao_nome=nomes, opcao_valores=valores), mensagem)


class EditarProdutoFormTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.produto = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('30.00'))

    def _form(self, remover):
        dados = {'nome': 'Bolo', 'preco_venda': '30', 'remover_imagens': remover}
        return EditarProdutoForm(como_post(dados), {}, instance=self.produto)

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

    def test_cada_ordem_da_tela_de_produtos_e_aceita(self):
        for ordem in ('nome', '-nome', 'preco_venda', '-preco_venda', 'quantidade_estoque', '-quantidade_estoque',
                      'data_criacao', '-data_criacao'):
            with self.subTest(ordem):
                form = FiltroProdutosForm({'ordem': ordem})
                self.assertTrue(form.is_valid())
                self.assertEqual(form.criterios()['ordem'], ordem)

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
