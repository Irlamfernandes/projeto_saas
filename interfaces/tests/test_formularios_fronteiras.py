"""Fronteiras e mensagens exatas dos formulários (achados pelo teste de mutação)."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from django.utils.datastructures import MultiValueDict
from infrastructure.models import Cliente, LojaModel, Produto
from interfaces.forms import (
    ApagarDadosDoClienteForm, CancelarVendaForm, CompraForm, DespesaForm, LoginForm, NovaVendaForm, PagamentoForm, PerdaForm,
    ProdutoForm, RenovarPlanoForm, TemaForm,
)
from interfaces.forms.configuracoes_form import MarcaForm
from interfaces.forms.gastos_form import MOTIVOS_SUGERIDOS
from interfaces.forms.produto_form import TAMANHO_MAXIMO_IMAGEM
from interfaces.forms.relatorio_form import LimiteEstoqueForm, PeriodoForm
from interfaces.forms.senha_form import NovaSenhaForm
from interfaces.tests.test_produto_form import como_post
from interfaces.views.comum import primeiro_erro
from tests.apoio import CenarioDeLoja, foto_heic_de_teste, imagem_de_teste

SENHA_FORTE = 'Caju-Verde-2026'


class MarcaFormTest(SimpleTestCase):

    def erros(self, arquivos):
        form = MarcaForm({}, arquivos)
        self.assertFalse(form.is_valid())
        return form.errors['marca']

    def test_mensagens(self):
        self.assertEqual(self.erros({}), ["Escolha a imagem da marca."])
        self.assertEqual(self.erros({'marca': SimpleUploadedFile('logo.png', b'texto')}),
                         ["Envie uma imagem válida (JPG, PNG, WEBP ou HEIC)."])
        self.assertEqual(self.erros({'marca': imagem_de_teste('logo.gif', 'GIF')}), ["Envie uma imagem JPG, PNG, WEBP ou HEIC."])


class ProdutoFormFronteirasTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")

    def _form(self, arquivos=None, **dados):
        base = {'nome': 'Bolo', 'preco_venda': '30.00', 'quantidade_estoque': '1'}
        return ProdutoForm(como_post({**base, **dados}), arquivos or {}, instance=Produto(loja=self.loja))

    def valido(self, **dados):
        form = self._form(**dados)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def assertErro(self, form, mensagem):
        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), mensagem)

    def test_aceita_heic_e_heif(self):
        imagens = MultiValueDict({'imagens': [foto_heic_de_teste('a.heic'), foto_heic_de_teste('b.HEIF')]})
        self.assertEqual(len(self.valido(arquivos=imagens).parametros()['imagens']), 2)

    def test_aceita_jpeg_e_webp(self):
        imagens = MultiValueDict({'imagens': [imagem_de_teste('a.jpeg', 'JPEG'), imagem_de_teste('b.webp', 'WEBP')]})
        self.assertEqual(len(self.valido(arquivos=imagens).parametros()['imagens']), 2)

    def test_limite_da_imagem_e_de_25_mb_e_o_proprio_limite_passa(self):
        self.assertEqual(TAMANHO_MAXIMO_IMAGEM, 26_214_400)
        imagem = imagem_de_teste('g.png')
        with patch('interfaces.forms.produto_form.TAMANHO_MAXIMO_IMAGEM', imagem.size):
            self.valido(arquivos={'imagens': [imagem]})
        with patch('interfaces.forms.produto_form.TAMANHO_MAXIMO_IMAGEM', imagem.size - 1):
            self.assertErro(self._form(arquivos={'imagens': [imagem]}), "A imagem 'g.png' excede o limite de 25 MB.")

    def test_campos_que_viram_zero_nao_sao_obrigatorios_nem_marcados_no_html(self):
        form = self._form()
        for campo in ('imagens', 'preco_custo', 'margem_lucro', 'quantidade_estoque', 'unidade'):
            with self.subTest(campo):
                self.assertIs(form.fields[campo].required, False)

    def test_unidade_em_branco_vira_unidade(self):
        self.assertEqual(self.valido(unidade='').instance.unidade, 'un')

    def test_estoque_fica_com_tres_casas_como_no_banco(self):
        self.assertEqual(str(self.valido(quantidade_estoque='5').cleaned_data['quantidade_estoque']), '5.000')

    def test_custo_e_margem_aceitam_virgula(self):
        form = self.valido(preco_custo='7,25', margem_lucro='12,5')
        self.assertEqual((form.instance.preco_custo, form.instance.margem_lucro), (Decimal('7.25'), Decimal('12.5')))

    def test_mensagens_de_erro(self):
        casos = {
            'categoria longa': ({'categoria': 'c' * 101}, "A categoria pode ter no máximo 100 caracteres."),
            'custo texto': ({'preco_custo': 'abc'}, "Preço de custo inválido."),
            'margem texto': ({'margem_lucro': 'abc'}, "Margem de lucro inválida."),
            'margem negativa': ({'margem_lucro': '-1'}, "A margem de lucro não pode ser negativa."),
            'estoque com dígitos demais': ({'quantidade_estoque': '1234567890.123'}, "Quantidade em estoque grande demais."),
            'estoque inteiro grande demais': ({'quantidade_estoque': '1234567890'}, "Quantidade em estoque grande demais."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                self.assertErro(self._form(**dados), mensagem)

    def test_opcoes_no_limite_passam(self):
        self.valido(opcao_nome=[f'Opção {i}' for i in range(5)], opcao_valores=['A'] * 5)
        self.assertErro(self._form(opcao_nome=[f'Opção {i}' for i in range(6)], opcao_valores=['A'] * 6),
                        "Cada produto pode ter até 5 opções.")
        self.valido(opcao_nome=['Sabor'], opcao_valores=['\n'.join(f'S{i}' for i in range(30))])
        self.valido(opcao_nome=['o' * 40], opcao_valores=['v' * 40])

    def test_bloco_vazio_no_meio_nao_esconde_os_seguintes(self):
        opcoes = self.valido(opcao_nome=['', 'Cor'], opcao_valores=['', 'Azul']).instance.opcoes
        self.assertEqual([opcao['nome'] for opcao in opcoes], ['Cor'])

    def test_nome_de_opcao_a_mais_no_post_e_ignorado(self):
        opcoes = self.valido(opcao_nome=['Cor', 'Adulterado'], opcao_valores=['Azul']).instance.opcoes
        self.assertEqual([opcao['nome'] for opcao in opcoes], ['Cor'])


class NovaSenhaFormTest(TestCase):

    def setUp(self):
        self.usuario = get_user_model()(username='ana')

    def erros(self, **dados):
        form = NovaSenhaForm(self.usuario, dados)
        form.is_valid()
        return form.lista_de_erros()

    def test_mensagens(self):
        self.assertEqual(self.erros(), ["Os campos de senha não podem estar vazios."])
        self.assertEqual(self.erros(confirmacao_senha=SENHA_FORTE), ["Os campos de senha não podem estar vazios."])
        self.assertEqual(self.erros(nova_senha=SENHA_FORTE, confirmacao_senha=SENHA_FORTE + 'x'), ["As senhas não coincidem."])
        longa = 'Aa1-' * 32 + 'x'
        form = NovaSenhaForm(self.usuario, {'nova_senha': longa, 'confirmacao_senha': longa})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {
            'nova_senha': ["A senha excede o limite máximo de caracteres permitido."],
            'confirmacao_senha': ["A senha excede o limite máximo de caracteres permitido."],
        })

    def test_128_caracteres_passam_e_espacos_contam(self):
        for senha in ('Aa1-' * 32, f' {SENHA_FORTE} '):
            with self.subTest(len(senha)):
                form = NovaSenhaForm(self.usuario, {'nova_senha': senha, 'confirmacao_senha': senha})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['nova_senha'], senha)


class RelatorioFormsTest(SimpleTestCase):

    def test_sem_datas_e_valido_e_o_padrao_sao_30_dias(self):
        form = PeriodoForm({})
        self.assertTrue(form.is_valid())
        agora = CenarioDeLoja.quando(2026, 3, 20, 12, 0)
        self.assertEqual(form.intervalo_ou_ultimos(agora=agora), (date(2026, 2, 19), date(2026, 3, 20)))

    def test_limite_de_estoque_vai_ate_100_mil_e_e_opcional(self):
        self.assertTrue(LimiteEstoqueForm({}).is_valid())
        self.assertEqual(LimiteEstoqueForm({'limite_estoque': '100000'}).limite(), 100_000)
        self.assertEqual(LimiteEstoqueForm({'limite_estoque': '100001'}).limite(), 5)


class LoginFormTest(SimpleTestCase):

    def test_rotulos(self):
        form = LoginForm()
        self.assertEqual((form['username'].label, form['password'].label), ('Usuário', 'Senha'))


def lista(**campos):
    """POST com campos repetidos (listas) como o navegador envia."""
    post = QueryDict(mutable=True)
    for campo, valor in campos.items():
        post.setlist(campo, valor if isinstance(valor, list) else [valor])
    return post


class ErrosMixin:

    def erros(self, form):
        self.assertFalse(form.is_valid())
        return {campo: list(mensagens) for campo, mensagens in form.errors.items()}


class GastosFormsTest(ErrosMixin, TestCase):

    def compra(self, itens=(('1', '2', '3,50'),), **campos):
        colunas = dict(zip(('item_produto', 'item_quantidade', 'item_custo'), map(list, zip(*itens, strict=True)), strict=True))
        return CompraForm(lista(data='2026-03-01', **colunas, **campos))

    def test_motivos_sugeridos(self):
        self.assertEqual(MOTIVOS_SUGERIDOS, ('Venceu', 'Quebrou ou estragou', 'Consumo próprio', 'Brinde ou amostra', 'Sumiu'))

    def test_compra_aceita_30_itens_e_recusa_31(self):
        self.assertTrue(self.compra([('1', '1', '1')] * 30).is_valid())
        self.assertEqual(self.erros(self.compra([('1', '1', '1')] * 31)),
                         {'__all__': ["Um dos produtos da compra está incompleto. Confira produto, quantidade e custo."]})

    def test_compra_recusa_um_milhao(self):
        self.assertTrue(self.compra([('1', '999999,999', '1')]).is_valid())
        self.assertEqual(self.erros(self.compra([('1', '1000000', '1')])),
                         {'__all__': ["Um dos produtos da compra está incompleto. Confira produto, quantidade e custo."]})

    def test_compra_limites_de_texto(self):
        self.assertTrue(self.compra(fornecedor='f' * 120, observacao='o' * 255).is_valid())
        self.assertEqual(self.erros(self.compra(fornecedor='f' * 121, observacao='o' * 256)), {
            'fornecedor': ["O fornecedor pode ter no máximo 120 caracteres."],
            'observacao': ["A observação pode ter no máximo 255 caracteres."],
        })

    def test_despesa(self):
        base = {'data': '2026-03-01', 'categoria': 'c' * 60, 'descricao': 'd' * 255, 'valor': '12345678,90'}
        form = DespesaForm(base)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros()['descricao'], 'd' * 255)
        self.assertEqual(self.erros(DespesaForm({'data': 'ontem', 'categoria': 'c' * 61, 'descricao': 'd' * 256})), {
            'data': ["Data inválida."],
            'categoria': ["A categoria pode ter no máximo 60 caracteres."],
            'descricao': ["A descrição pode ter no máximo 255 caracteres."],
            'valor': ["Informe o valor da despesa."],
        })
        valores = {
            'abc': "Valor inválido.",
            '1234567890123': "Valor grande demais.",
            '12345678901': "Valor grande demais.",
            '1,234': "Use no máximo 2 casas depois da vírgula.",
        }
        for valor, mensagem in valores.items():
            with self.subTest(valor):
                self.assertEqual(self.erros(DespesaForm({**base, 'valor': valor})), {'valor': [mensagem]})

    def test_perda(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        produto = Produto.objects.create(loja=loja, nome="Pão", preco_venda=Decimal('1'))
        produtos = Produto.objects.filter(loja=loja)
        base = {'data': '2026-03-01', 'produto': produto.pk, 'quantidade': '123456789,123', 'motivo': 'm' * 120}
        self.assertTrue(PerdaForm(base, produtos=produtos).is_valid())
        self.assertEqual(self.erros(PerdaForm({'data': '2026-03-01'}, produtos=produtos)), {
            'produto': ["Escolha o produto que se perdeu."],
            'quantidade': ["Informe a quantidade perdida."],
            'motivo': ["Conte o motivo da perda."],
        })
        self.assertEqual(self.erros(PerdaForm({**base, 'motivo': 'm' * 121}, produtos=produtos)),
                         {'motivo': ["O motivo pode ter no máximo 120 caracteres."]})
        quantidades = {
            'abc': "Quantidade inválida.",
            '0': "A quantidade deve ser maior que zero.",
            '1234567890123': "Quantidade grande demais.",
            '1234567890': "Quantidade grande demais.",
            '1,2345': "Use no máximo 3 casas depois da vírgula.",
        }
        for quantidade, mensagem in quantidades.items():
            with self.subTest(quantidade):
                self.assertEqual(self.erros(PerdaForm({**base, 'quantidade': quantidade}, produtos=produtos)),
                                 {'quantidade': [mensagem]})


class VendaFormsTest(ErrosMixin, TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.clientes = Cliente.objects.filter(loja=self.loja)
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Ana")

    def venda(self, produtos=('1',), **campos):
        dados = {'item_produto': list(produtos), 'item_quantidade': ['1'] * len(produtos), 'forma_pagamento': 'pix', **campos}
        return NovaVendaForm(lista(**dados), clientes=self.clientes)

    def test_primeira_escolha_da_forma_e_em_branco(self):
        self.assertEqual(self.venda().fields['forma_pagamento'].choices[0], ('', '---'))

    def test_limites(self):
        self.assertTrue(self.venda([str(i) for i in range(50)], observacoes='o' * 500).is_valid())
        self.assertEqual(self.erros(self.venda([str(i) for i in range(51)])),
                         {'__all__': ["Um dos itens da venda é inválido. Remova-o e adicione de novo."]})
        self.assertEqual(self.erros(self.venda(observacoes='o' * 501)),
                         {'observacoes': ["As observações podem ter no máximo 500 caracteres."]})
        vencimentos = [f'2026-04-{dia:02d}' for dia in range(1, 14)]
        self.assertTrue(self.venda(cliente=str(self.cliente.pk), vencimento=vencimentos[:12]).is_valid())
        self.assertEqual(self.erros(self.venda(cliente=str(self.cliente.pk), vencimento=vencimentos)),
                         {'__all__': ["Divida em no máximo 12 parcelas."]})

    def test_valor_pago(self):
        for valor in ('0', '0.50', '12345678.99'):
            with self.subTest(valor):
                self.assertTrue(self.venda(cliente=str(self.cliente.pk), valor_pago=valor).is_valid())
        for valor in ('123456789', '1.234'):
            with self.subTest(valor):
                self.assertIn('valor_pago', self.erros(self.venda(cliente=str(self.cliente.pk), valor_pago=valor)))

    def test_cancelar(self):
        form = CancelarVendaForm({'senha': ' com espaços ', 'motivo': 'm' * 200})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros()['senha'], ' com espaços ')
        self.assertEqual(self.erros(CancelarVendaForm({'senha': 'x', 'motivo': 'm' * 201})),
                         {'motivo': ["O motivo pode ter no máximo 200 caracteres."]})


class CadastroFormsTest(ErrosMixin, TestCase):

    def test_pagamento_sem_observacao(self):
        self.assertTrue(PagamentoForm({'valor': '10', 'forma_pagamento': 'pix'}).is_valid())

    def test_apagar_dados_do_cliente(self):
        self.assertEqual(self.erros(ApagarDadosDoClienteForm({})), {'senha': ["Digite sua senha para confirmar."]})
        form = ApagarDadosDoClienteForm({'senha': ' x '})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros(), {'senha': ' x '})

    def test_plano(self):
        self.assertEqual(self.erros(RenovarPlanoForm({'email': 'a@exemplo.com'})), {'plano': ["Escolha um plano."]})
        email = f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 57}.com"
        self.assertEqual(len(email), 254)
        self.assertNotIn('email', RenovarPlanoForm({'email': email}).errors)
        self.assertEqual(RenovarPlanoForm({'email': email.replace('.com', 'x.com')}).errors['email'],
                         ["O e-mail pode ter no máximo 254 caracteres."])

    def test_tema(self):
        self.assertEqual(self.erros(TemaForm({'tema': 'roxo'})), {'tema': ["Escolha uma aparência da lista."]})
        self.assertEqual(self.erros(TemaForm({})), {'tema': ["Este campo é obrigatório."]})
