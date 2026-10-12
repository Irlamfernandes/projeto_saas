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
    """Como o navegador envia: listas para os campos repetidos (variacao_nome, variacao_quantidade...)."""
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
        self.assertEqual(form.parametros(), {'produto': form.instance, 'variacoes': [], 'imagens': []})

    def test_recusa_arquivo_que_nao_e_imagem(self):
        falso = SimpleUploadedFile('virus.png', b'<script>alert(1)</script>', content_type='image/png')
        self.assertErro(self._form(arquivos={'imagens': [falso]}), "Envie apenas imagens válidas (JPG, PNG, WEBP ou HEIC).")

    def test_recusa_formato_fora_da_lista(self):
        gif = imagem_de_teste('anim.gif', 'GIF')
        self.assertErro(self._form(arquivos={'imagens': [gif]}), "Envie apenas imagens JPG, PNG, WEBP ou HEIC.")

    def test_recusa_imagem_grande_demais(self):
        with patch('interfaces.forms.produto_form.TAMANHO_MAXIMO_IMAGEM', 10):
            self.assertErro(self._form(arquivos={'imagens': [imagem_de_teste('g.png')]}), "A imagem 'g.png' excede o limite de 25 MB.")


def linhas(*variacoes):
    """[(id, nome, acréscimo, quantidade), ...] -> campos repetidos do POST."""
    colunas = list(zip(*variacoes, strict=True)) if variacoes else [[], [], [], []]
    return dict(zip(('variacao_id', 'variacao_nome', 'variacao_acrescimo', 'variacao_quantidade'), map(list, colunas),
                    strict=True))


class VariacoesDoProdutoTest(ProdutoFormTest):
    """Uma linha por variação: nome, acréscimo (opcional) e quantidade (só com controle de estoque)."""

    def variacoes(self, *linhas_do_post, **dados):
        form = self._form(**linhas(*linhas_do_post), **dados)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_blusa_com_tres_variacoes_e_o_estoque_vira_a_soma(self):
        form = self.variacoes(
            ('', ' Azul P ', '', '10'), ('', 'Azul M', '', '5'), ('4', 'Branca P', 'R$ 2,50', '5'),
            quantidade_estoque='999',
        )

        self.assertEqual(form.parametros()['variacoes'], [
            {'id': None, 'nome': 'Azul P', 'acrescimo': Decimal('0.00'), 'quantidade': Decimal('10.000')},
            {'id': None, 'nome': 'Azul M', 'acrescimo': Decimal('0.00'), 'quantidade': Decimal('5.000')},
            {'id': 4, 'nome': 'Branca P', 'acrescimo': Decimal('2.50'), 'quantidade': Decimal('5.000')},
        ])
        self.assertEqual(form.cleaned_data['quantidade_estoque'], Decimal('20'))

    def test_linhas_em_branco_sao_ignoradas_e_sem_variacoes_o_estoque_e_o_digitado(self):
        form = self.variacoes(('', ' ', ' ', ''), quantidade_estoque='3')
        self.assertEqual(form.parametros()['variacoes'], [])
        self.assertEqual(form.cleaned_data['quantidade_estoque'], Decimal('3'))

    def test_aceita_ponto_virgula_e_vazio(self):
        form = self.variacoes(('', 'A', '1.5', '2,5'), ('', 'B', '', ''), unidade='kg')
        [a, b] = form.parametros()['variacoes']
        self.assertEqual((a['acrescimo'], a['quantidade']), (Decimal('1.50'), Decimal('2.500')))
        self.assertEqual((b['acrescimo'], b['quantidade']), (Decimal('0.00'), Decimal('0')))

    def test_sem_controle_de_estoque_a_quantidade_nem_e_lida(self):
        form = self.variacoes(('', 'Chocolate', '', 'abc'), sem_controle_de_estoque='1')
        self.assertEqual(form.parametros()['variacoes'][0]['quantidade'], Decimal('0'))
        self.assertEqual(form.cleaned_data['quantidade_estoque'], Decimal('0'))

    def test_mensagens_de_erro_das_variacoes(self):
        casos = {
            'sem nome': [('', '', '2', '')], 'id inválido': [('x', 'A', '', '')],
            'acréscimo inválido': [('', 'A', 'dois', '')], 'acréscimo negativo': [('', 'A', '-1', '')],
            'acréscimo enorme': [('', 'A', '100000000', '')], 'acréscimo infinito': [('', 'A', 'Infinity', '')],
            'quantidade inválida': [('', 'A', '', '1,2,3')], 'quantidade negativa': [('', 'A', '', '-1')],
            'quantidade enorme': [('', 'A', '', '1000000000')], 'fração por unidade': [('', 'A', '', '1,5')],
            'repetida': [('', 'Azul', '', ''), ('', 'azul', '', '')], 'longa': [('', 'N' * 41, '', '')],
            'demais': [('', f'V{numero}', '', '') for numero in range(101)],
        }
        mensagens = {
            'sem nome': "Dê um nome para cada variação (ex.: Azul P, Chocolate).", 'id inválido': "Variação inválida.",
            'acréscimo inválido': 'Acréscimo inválido em "A".', 'acréscimo negativo': 'Acréscimo inválido em "A".',
            'acréscimo enorme': 'Acréscimo inválido em "A".', 'acréscimo infinito': 'Acréscimo inválido em "A".',
            'quantidade inválida': 'Quantidade inválida em "A".', 'quantidade negativa': 'Quantidade inválida em "A".',
            'quantidade enorme': 'Quantidade inválida em "A".',
            'fração por unidade': 'Esta unidade só aceita números inteiros: confira a quantidade de "A".',
            'repetida': 'Há duas variações chamadas "azul".',
            'longa': f'"{"N" * 20}…" é longo demais: use até 40 letras no nome da variação.',
            'demais': "Cada produto pode ter até 100 variações.",
        }
        for caso, linhas_do_post in casos.items():
            with self.subTest(caso):
                self.assertErro(self._form(**linhas(*linhas_do_post)), mensagens[caso])

    def test_no_limite_passa(self):
        form = self.variacoes(*[('', f'V{numero}', '99999999,99', '1') for numero in range(100)])
        self.assertEqual(len(form.parametros()['variacoes']), 100)
        self.assertEqual(self.variacoes(('', 'N' * 40, '', '999999999,999'), unidade='kg').cleaned_data['quantidade_estoque'],
                         Decimal('999999999.999'))

    def test_soma_maior_que_o_estoque_comporta(self):
        self.assertErro(self._form(**linhas(('', 'A', '', '999999999'), ('', 'B', '', '999999999'))),
                        "Quantidade em estoque grande demais.")


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
            'produto': self.produto, 'variacoes': [], 'imagens_novas': [], 'ids_imagens_remover': [3, 7],
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
