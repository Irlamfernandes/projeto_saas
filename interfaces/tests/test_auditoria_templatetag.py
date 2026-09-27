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
        depois = {**VENDA, 'cliente': 'Ana', 'forma_pagamento': '', 'pago_no_ato': ['5.00'], 'itens': []}
        self.assertEqual(detalhes_legiveis({'antes': VENDA, 'depois': depois}), [
            "Antes: Balcão · 2× Pão (R$ 10,00) · total R$ 20,00 · Pix",
            "Depois: Ana · sem itens · total R$ 20,00 · pago no ato R$ 5,00",
        ])

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
            'algo_novo': 'i-historico',
        }
        for acao, icone in casos.items():
            with self.subTest(acao=acao):
                self.assertEqual(icone_da_acao(acao), icone)
