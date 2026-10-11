from django.test import SimpleTestCase
from interfaces.templatetags.auditoria import detalhes_legiveis

VENDA = {
    'cliente': None, 'total': '20.00', 'forma_pagamento': 'Pix', 'pago_no_ato': [],
    'itens': [{'produto': 'Pão', 'quantidade': 2, 'preco_unitario': '10.00'}],
}


class DetalhesLegiveisTest(SimpleTestCase):

    def test_alteracoes_de_campos_com_reais_e_vazios(self):
        detalhes = {'alteracoes': {'preco_venda': ['10.00', '12.50'], 'categoria': ['', 'Pães'], 'quantidade_estoque': [3, 5]}}
        self.assertEqual(detalhes_legiveis(detalhes), [
            "Preço de venda: R$ 10,00 → R$ 12,50", "Categoria: (vazio) → Pães", "Estoque: 3 → 5",
        ])

    def test_venda_registrada_e_cancelada(self):
        self.assertEqual(detalhes_legiveis({'venda': VENDA, 'motivo': 'erro'}), [
            "Balcão · 2× Pão (R$ 10,00) · total R$ 20,00 · Pix", "Motivo: erro",
        ])

    def test_venda_editada_mostra_antes_e_depois(self):
        depois = {**VENDA, 'cliente': 'Ana', 'forma_pagamento': '', 'pago_no_ato': ['5.00'], 'itens': [],
                  'vencimentos': ['2026-10-15']}
        self.assertEqual(detalhes_legiveis({'antes': VENDA, 'depois': depois}), [
            "Antes: Balcão · 2× Pão (R$ 10,00) · total R$ 20,00 · Pix",
            "Depois: Ana · sem itens · total R$ 20,00 · pago no ato R$ 5,00 · vence 15/10/2026",
        ])

    def test_campos_do_produto_legiveis(self):
        detalhes = {'alteracoes': {
            'unidade': ['un', 'kg'], 'controla_estoque': [True, False], 'quantidade_estoque': ['2.50', '0.125'],
        }}
        self.assertEqual(detalhes_legiveis(detalhes), [
            "Vendido por: Unidade → Quilo (kg)", "Controla estoque: sim → não", "Estoque: 2,5 → 0,125",
        ])

    def test_opcoes_do_produto_legiveis(self):
        tamanho = {'nome': 'Tamanho', 'valores': [{'nome': 'P', 'acrescimo': '0.00'}, {'nome': 'G', 'acrescimo': '5.00'}]}
        sabor = {'nome': 'Sabor', 'valores': [{'nome': 'Coco', 'acrescimo': '0.00'}]}
        self.assertEqual(detalhes_legiveis({'alteracoes': {'opcoes': [[], [tamanho, sabor]]}}), [
            "Opções: (vazio) → Tamanho: P, G (+R$ 5,00); Sabor: Coco",
        ])

    def test_variacoes_do_produto_legiveis(self):
        azul = {'nome': 'Azul P', 'acrescimo': '0.00', 'quantidade_estoque': '10.00'}
        branca = {'nome': 'Branca P', 'acrescimo': '2.50', 'quantidade_estoque': '5.00'}
        self.assertEqual(detalhes_legiveis({'alteracoes': {'variacoes': [[], [azul, branca]]}}), [
            "Variações: (vazio) → Azul P: 10; Branca P: 5 (+R$ 2,50)",
        ])

    def test_item_vendido_por_quilo_no_resumo(self):
        venda = {**VENDA, 'itens': [{'produto': 'Queijo', 'quantidade': '0.35', 'unidade': 'kg', 'preco_unitario': '39.90'}]}
        self.assertEqual(detalhes_legiveis({'venda': venda}), ["Balcão · 0,35 kg Queijo (R$ 39,90) · total R$ 20,00 · Pix"])

    def test_itens_da_compra(self):
        self.assertEqual(detalhes_legiveis({'itens': ["3× Bolo a R$ 12,00", "2,5 kg Queijo a R$ 39,90"]}),
                         ["Itens: 3× Bolo a R$ 12,00, 2,5 kg Queijo a R$ 39,90"])

    def test_fotos_e_observacao(self):
        self.assertEqual(detalhes_legiveis({'fotos': {'adicionadas': 2, 'removidas': 1}, 'observacao': 'acerto'}),
                         ["Fotos: 2 adicionada(s), 1 removida(s)", "Observação: acerto"])
        self.assertEqual(detalhes_legiveis({'fotos': 3}), ["Fotos: 3"])

    def test_campo_desconhecido_e_valor_estranho_nao_quebram(self):
        self.assertEqual(detalhes_legiveis({'alteracoes': {'outro': ['a', 'b'], 'preco_custo': ['x', None]}}),
                         ["outro: a → b", "Preço de custo: x → (vazio)"])
        self.assertEqual(detalhes_legiveis(None), [])


class IconeDaAcaoTest(SimpleTestCase):

    def test_icone_por_acao_e_por_assunto(self):
        from interfaces.templatetags.auditoria import icone_da_acao
        casos = {
            'venda_cancelada': 'i-x', 'venda_editada': 'i-venda', 'pagamento_registrado': 'i-carteira',
            'produto_cadastrado': 'i-produto', 'cliente_editado': 'i-clientes', 'marca_alterada': 'i-foto',
            'lembrete_enviado': 'i-mensagem', 'compra_excluida': 'i-produto', 'despesa_registrada': 'i-carteira',
            'perda_registrada': 'i-lixeira',
            'algo_novo': 'i-historico',
        }
        for acao, icone in casos.items():
            with self.subTest(acao=acao):
                self.assertEqual(icone_da_acao(acao), icone)


class RenovacaoDoPlanoLegivelTest(SimpleTestCase):

    def test_mostra_o_vencimento_antes_e_depois(self):
        linhas = detalhes_legiveis({'vencimento': ['2026-09-29', '2026-10-29'], 'pagamento_id': '123'})
        self.assertEqual(linhas, ["Vencimento: 29/09/2026 → 29/10/2026"])

    def test_data_estranha_aparece_como_veio(self):
        self.assertEqual(detalhes_legiveis({'vencimento': ['?', None]}), ["Vencimento: ? → None"])

    def test_icone(self):
        from interfaces.templatetags.auditoria import icone_da_acao
        self.assertEqual(icone_da_acao('plano_renovado'), 'i-calendario')
