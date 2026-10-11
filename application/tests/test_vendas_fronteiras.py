"""Fronteiras e detalhes das vendas e da caderneta (achados pelo teste de mutação)."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from django.utils import timezone
from application.a_receber.selectors import clientes_a_cobrar, cobranca_do_cliente
from application.a_receber.services import registrar_lembrete
from application.tests.test_vendas_services import DIA_15, ServicoDeVendaTestCase, vencimentos
from application.vendas.exceptions import (
    EstoqueInsuficiente, ProdutoNaoEncontrado, QuantidadeFracionada, SenhaIncorreta, VendaSemItens, VendaSemLoja,
)
from application.vendas.pendencias import Pendencia, Situacao, pendencias_do_cliente
from application.vendas.selectors import produtos_em_estoque_do_usuario
from application.vendas.services import cancelar_venda, editar_venda, registrar_venda
from infrastructure.models import Acao, LembreteDePagamento, Produto, RegistroDeAlteracao, Unidade, Venda
from infrastructure.utils.formatacao import reais

HOJE = timezone.localdate()


class HistoricoDaVendaTest(ServicoDeVendaTestCase):

    def test_balcao_registrado_e_cancelado_com_descricao_e_foto(self):
        venda = registrar_venda(itens=[(self.arroz.pk, 1)], loja=self.loja, usuario=self.usuario)
        registro = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_REGISTRADA)
        self.assertEqual(registro.descricao, f"Venda #{venda.pk} · Balcão · {reais(Decimal('20'))}")
        foto = registro.detalhes['venda']
        self.assertEqual((foto['data'], foto['observacoes'], foto['forma_pagamento']), (venda.data_venda.isoformat(), '', ''))

        cancelar_venda(venda, usuario=self.usuario, senha='senha-certa', motivo='Lançou errado')
        cancelada = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_CANCELADA)
        self.assertEqual(cancelada.descricao, f"Venda #{foto['id']} · Balcão · {reais(Decimal('20'))} · motivo: Lançou errado")

    def test_venda_que_troca_de_cliente_fica_no_historico_dos_dois(self):
        venda = registrar_venda(itens=[(self.arroz.pk, 1)], cliente=self.ana)
        editar_venda(venda, itens=[(self.arroz.pk, 1)], cliente=self.bia)
        edicao = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_EDITADA)
        self.assertEqual(set(edicao.clientes.all()), {self.ana, self.bia})  # a LGPD acha pelos dois

    def test_sem_observacoes_a_venda_fica_sem_texto_ao_registrar_e_ao_editar(self):
        venda = registrar_venda(itens=[(self.arroz.pk, 1)], cliente=self.ana)
        self.assertEqual(venda.observacoes, '')
        venda.observacoes = 'antes'
        venda.save()
        editar_venda(venda, itens=[(self.arroz.pk, 1)], cliente=self.ana)
        venda.refresh_from_db()
        self.assertEqual(venda.observacoes, '')

    def test_cancelamento_que_falha_no_meio_desfaz_tudo(self):
        venda = registrar_venda(itens=[(self.arroz.pk, 2)], cliente=self.ana)
        with patch.object(Venda, 'delete', side_effect=RuntimeError("falhou")), self.assertRaises(RuntimeError):
            cancelar_venda(venda, usuario=self.usuario, senha='senha-certa', motivo='x')
        self.assertEstoque(self.arroz, 8)
        self.assertFalse(RegistroDeAlteracao.objects.filter(acao=Acao.VENDA_CANCELADA).exists())


class CentavosNaCadernetaTest(ServicoDeVendaTestCase):
    """Cinquenta centavos que ficam devendo ainda são dívida: vencem, aparecem na cobrança e não contam como pagos."""

    def setUp(self):
        super().setUp()
        self.venda = registrar_venda(
            itens=[(self.arroz.pk, 1)], cliente=self.ana, valor_pago=Decimal('19.50'), vencimentos=[HOJE],
        )

    def test_a_venda_guarda_o_vencimento(self):
        self.assertEqual(vencimentos(self.venda), [HOJE])

    def test_a_pendencia_e_de_50_centavos_e_vence_hoje(self):
        [pendencia] = pendencias_do_cliente(self.ana)
        self.assertEqual((pendencia.pendente, pendencia.situacao(HOJE)), (Decimal('0.50'), Situacao.VENCE_HOJE))

    def test_entra_na_lista_de_cobranca(self):
        [cobranca] = clientes_a_cobrar(SimpleNamespace(is_superuser=False, loja=self.loja), HOJE)
        self.assertEqual((cobranca.cliente, cobranca.total, cobranca.lembrado_hoje), (self.ana, Decimal('0.50'), False))

    def test_cobranca_de_um_cliente_so_nao_vem_marcada_como_lembrada(self):
        self.assertFalse(cobranca_do_cliente(self.ana, HOJE).lembrado_hoje)

    def test_venda_paga_por_completo_no_ato_nao_guarda_vencimento(self):
        paga = registrar_venda(itens=[(self.arroz.pk, 1)], cliente=self.bia, valor_pago=Decimal('20'), vencimentos=[DIA_15])
        self.assertEqual(vencimentos(paga), [])


class LembreteTest(ServicoDeVendaTestCase):

    def test_se_o_historico_falhar_o_lembrete_nao_fica_anotado(self):
        with patch('application.a_receber.services.registrar_alteracao', side_effect=RuntimeError), \
                self.assertRaises(RuntimeError):
            registrar_lembrete(self.ana, valor=Decimal('10'))
        self.assertFalse(LembreteDePagamento.objects.exists())


class EstoqueFracionadoTest(ServicoDeVendaTestCase):

    def test_meio_quilo_ainda_esta_a_venda(self):
        queijo = Produto.objects.create(loja=self.loja, nome="Queijo", preco_venda=Decimal('40'), unidade=Unidade.QUILO,
                                        quantidade_estoque=Decimal('0.5'))
        usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        self.assertIn(queijo, produtos_em_estoque_do_usuario(usuario))


class PendenciaTest(SimpleTestCase):

    def test_sem_informar_e_parcela_unica(self):
        pendencia = Pendencia(venda=None, vencimento=None, valor=Decimal('5'), pendente=Decimal('5'))
        self.assertEqual((pendencia.numero, pendencia.de, pendencia.parcelada), (1, 1, False))

    def test_centavos_pendentes_nao_contam_como_pago(self):
        pendencia = Pendencia(venda=None, vencimento=None, valor=Decimal('5'), pendente=Decimal('0.50'))
        self.assertEqual(pendencia.situacao(HOJE), Situacao.SEM_PRAZO)

    def test_nomes_das_situacoes_sao_os_que_os_templates_comparam(self):
        self.assertEqual(
            [Situacao.PAGA, Situacao.ATRASADA, Situacao.VENCE_HOJE, Situacao.A_VENCER, Situacao.SEM_PRAZO],
            ['paga', 'atrasada', 'vence_hoje', 'a_vencer', 'sem_prazo'],
        )


class MensagensDeErroDaVendaTest(SimpleTestCase):
    """O texto é o que aparece para quem está no caixa: confere palavra por palavra."""

    def test_mensagens(self):
        queijo = Produto(nome="Queijo", unidade=Unidade.QUILO, quantidade_estoque=Decimal('1.5'))
        bolo = Produto(nome="Bolo", unidade=Unidade.UNIDADE)
        casos = {
            ProdutoNaoEncontrado(): "Um dos produtos escolhidos não foi encontrado nesta loja. Busque de novo e tente outra vez.",
            EstoqueInsuficiente(queijo): "Estoque insuficiente para 'Queijo'. Disponível: 1,5 kg",
            QuantidadeFracionada(queijo): "'Queijo' é vendido por quilo (kg): use no máximo 3 casas depois da vírgula.",
            QuantidadeFracionada(bolo): "'Bolo' é vendido por unidade: use só números inteiros.",
            VendaSemItens(): "Adicione pelo menos um produto à venda.",
            VendaSemLoja(): "Venda de balcão precisa de uma loja: entre com um usuário de loja ou escolha um cliente.",
            SenhaIncorreta(): "Senha incorreta. A venda não foi cancelada.",
            EstoqueInsuficiente(queijo, SimpleNamespace(nome="Meia cura", quantidade_estoque=Decimal('0.2'))):
                "Estoque insuficiente para 'Queijo (Meia cura)'. Disponível: 0,2 kg",
        }
        for erro, mensagem in casos.items():
            with self.subTest(type(erro).__name__):
                self.assertEqual(str(erro), mensagem)
