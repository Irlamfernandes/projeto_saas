"""Fronteiras e textos exatos das peças de apoio das telas (achados pelo teste de mutação)."""
from types import SimpleNamespace
from django.template import Context
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.urls import get_resolver, reverse
import interfaces
from interfaces.decorators import AVISO_PLANO_VENCIDO
from interfaces.desenvolvedor import CORSARIOS_CODE
from interfaces.templatetags.ajuda import AJUDA_POR_ROTA, link_suporte
from interfaces.templatetags.auditoria import detalhes_legiveis
from interfaces.templatetags.navegacao import iniciais
from tests.apoio import dataclasses_do_pacote


class RegrasDasTelasTest(SimpleTestCase):

    def test_toda_dataclass_das_telas_e_congelada(self):
        classes = dataclasses_do_pacote(interfaces)
        self.assertGreaterEqual(len(classes), 3)
        for classe in classes:
            with self.subTest(classe.__qualname__):
                self.assertTrue(classe.__dataclass_params__.frozen)


class CabecalhosDeSegurancaTest(TestCase):

    def test_nomes_e_permissoes_negadas(self):
        response = self.client.get(reverse('login'))
        self.assertIn("default-src 'self'", response['Content-Security-Policy'])
        self.assertEqual(response['Permissions-Policy'], (
            'camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), bluetooth=(), hid=(), midi=(), '
            'magnetometer=(), gyroscope=(), accelerometer=(), display-capture=(), browsing-topics=()'
        ))


class AjudaTest(SimpleTestCase):

    def test_cada_rota_existe_e_tem_seu_texto(self):
        rotas = {nome for nome in get_resolver().reverse_dict if isinstance(nome, str)}
        for rota, arquivo in AJUDA_POR_ROTA.items():
            with self.subTest(rota):
                self.assertIn(rota, rotas)
                get_template(f'interfaces/ajuda/{arquivo}.html')

    def test_suporte_sem_loja_e_o_painel_global(self):
        contexto = Context({'request': SimpleNamespace(user=SimpleNamespace(loja=None))})
        self.assertEqual(link_suporte(contexto), CORSARIOS_CODE.link_suporte('Painel global'))
        self.assertIn('Painel%20global', link_suporte(contexto))


class TextosFixosTest(SimpleTestCase):

    def test_iniciais_contam_palavra_que_comeca_com_letra(self):
        self.assertEqual((iniciais('Pão D-Mel'), iniciais('- Mel')), ('PD', 'M'))

    def test_frase_do_desenvolvedor_e_aviso_do_plano(self):
        self.assertEqual(CORSARIOS_CODE.frase, 'Desenvolvimento de software')
        self.assertEqual(AVISO_PLANO_VENCIDO, "Seu plano venceu e nada foi salvo. Renove em Configurações para voltar a "
                                              "registrar vendas e fazer alterações.")


class DetalhesDoHistoricoTest(SimpleTestCase):

    def test_rotulo_de_cada_campo(self):
        campos = ['nome', 'codigo_interno', 'categoria', 'preco_custo', 'preco_venda', 'quantidade_estoque', 'descricao',
                  'telefone', 'email', 'endereco', 'unidade', 'controla_estoque']
        linhas = detalhes_legiveis({'alteracoes': {campo: ['x', 'y'] for campo in campos}})
        self.assertEqual([linha.split(':')[0] for linha in linhas], [
            'Nome', 'Código', 'Categoria', 'Preço de custo', 'Preço de venda', 'Estoque', 'Descrição',
            'Telefone', 'E-mail', 'Endereço', 'Vendido por', 'Controla estoque',
        ])

    def test_preco_de_custo_em_reais(self):
        self.assertEqual(detalhes_legiveis({'alteracoes': {'preco_custo': ['10', '12.5']}}),
                         ["Preço de custo: R$ 10,00 → R$ 12,50"])

    def test_edicao_de_venda_mantem_as_alteracoes_e_junta_as_listas(self):
        venda = {
            'itens': [
                {'quantidade': '1', 'unidade': 'un', 'produto': 'Pão', 'preco_unitario': '2'},
                {'quantidade': '2', 'unidade': 'un', 'produto': 'Bolo', 'preco_unitario': '5'},
            ],
            'total': '12', 'pago_no_ato': ['1', '2'], 'vencimentos': ['2026-04-01', '2026-05-01'],
        }
        self.assertEqual(detalhes_legiveis({'alteracoes': {'nome': ['a', 'b']}, 'antes': venda, 'depois': venda}), [
            "Nome: a → b",
            "Antes: Balcão · 1× Pão (R$ 2,00), 2× Bolo (R$ 5,00) · total R$ 12,00 · pago no ato R$ 1,00, R$ 2,00 · "
            "vence 01/04/2026, 01/05/2026",
            "Depois: Balcão · 1× Pão (R$ 2,00), 2× Bolo (R$ 5,00) · total R$ 12,00 · pago no ato R$ 1,00, R$ 2,00 · "
            "vence 01/04/2026, 01/05/2026",
        ])

    def test_fotos_sem_uma_das_contas_vira_zero(self):
        self.assertEqual(detalhes_legiveis({'fotos': {'removidas': 2}}), ["Fotos: 0 adicionada(s), 2 removida(s)"])
        self.assertEqual(detalhes_legiveis({'fotos': {'adicionadas': 1}}), ["Fotos: 1 adicionada(s), 0 removida(s)"])
