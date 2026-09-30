"""Contexto exato das telas (achado pelo teste de mutação): chaves que os templates usam, opções e tamanhos."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models import FormaDePagamento, LojaModel, PagamentoCliente
from interfaces.desenvolvedor import CORSARIOS_CODE
from interfaces.views.comum import redirecionar_apos_login
from interfaces.views.planos_view import _loja_do_usuario
from interfaces.views.produtos_view import MAXIMO_DE_FOTOS
from interfaces.views.relatorios_export_views import _exportar
from tests.apoio import CenarioDeLoja


class TelasDeRelatorioTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        usuario = get_user_model().objects.create_user(username="op", password="x", loja=self.c.loja, deve_trocar_senha=False)
        self.client.force_login(usuario)

    def contexto(self, rota, **parametros):
        resposta = self.client.get(reverse(rota), parametros)
        self.assertEqual(resposta.status_code, 200)
        return resposta.context

    def assertChaves(self, contexto, chaves):
        faltando = set(chaves) - set(contexto.keys())
        self.assertEqual(faltando, set())

    def test_vendas(self):
        ontem = timezone.now() - timedelta(days=1)
        for numero in range(11):
            self.c.venda(ontem, [(self.c.produto(f"P{numero:02d}"), numero + 1)])
        contexto = self.contexto('relatorios_vendas')
        self.assertChaves(contexto, ['aba', 'data_inicio', 'data_fim', 'dias', 'manter', 'grafico_diario', 'grafico_mensal',
                                     'mais_vendidos', 'grafico_mais_vendidos', 'mapa', 'formas_de_pagamento',
                                     'total_recebido', 'grafico_formas'])
        self.assertEqual((contexto['aba'], contexto['dias'], contexto['manter']), ('vendas', 30, {'dias': 30}))
        self.assertEqual(len(contexto['grafico_diario']['rotulos']), 30)
        self.assertEqual(len(contexto['grafico_mensal']['rotulos']), 12)
        self.assertEqual(len(contexto['mais_vendidos']), 10)
        self.assertEqual(contexto['grafico_mais_vendidos']['series'][0]['nome'], 'Quantidade')
        self.assertEqual(contexto['grafico_formas']['series'][0]['nome'], 'Recebido')
        self.assertEqual(self.contexto('relatorios_vendas', dias=90)['manter'], {'dias': 90})
        self.assertEqual(self.contexto('relatorios_vendas', dias=31)['dias'], 30)

    def test_produtos(self):
        contexto = self.contexto('relatorios_produtos')
        self.assertChaves(contexto, ['aba', 'lucro', 'grafico_lucro', 'curva_abc', 'resumo_abc', 'dias_parado', 'manter',
                                     'parados', 'reposicao'])
        self.assertEqual((contexto['aba'], contexto['dias_parado'], contexto['manter']), ('produtos', 60, {'parado': 60}))
        self.assertEqual(contexto['grafico_lucro']['series'][0]['nome'], 'Lucro')
        for pedido, esperado in {'30': 30, '61': 60, '90': 90, '91': 60}.items():
            with self.subTest(pedido):
                self.assertEqual(self.contexto('relatorios_produtos', parado=pedido)['dias_parado'], esperado)

    def test_clientes(self):
        contexto = self.contexto('relatorios_clientes')
        self.assertChaves(contexto, ['aba', 'dividas', 'grafico_dividas', 'grafico_fluxo', 'melhores', 'sumidos'])
        self.assertEqual(contexto['aba'], 'clientes')
        self.assertEqual([(s['nome'], s['cor']) for s in contexto['grafico_dividas']['series']], [('A receber', 'destaque')])
        self.assertEqual(len(contexto['grafico_fluxo']['rotulos']), 12)

    def test_alteracoes(self):
        contexto = self.contexto('relatorios_alteracoes', acao='venda_cancelada')
        self.assertChaves(contexto, ['aba', 'registros', 'page_obj', 'acoes', 'acao'])
        self.assertEqual((contexto['aba'], contexto['acao']), ('alteracoes', 'venda_cancelada'))
        self.assertIs(contexto['page_obj'], contexto['registros'])
        self.assertEqual(contexto['acoes'][0], ('venda_registrada', 'Venda registrada'))
        self.assertEqual(self.contexto('relatorios_alteracoes')['acao'], '')


class RedirecionarAposLoginTest(TestCase):

    def destino(self, usuario, next_url=None):
        return redirecionar_apos_login(RequestFactory().get('/'), usuario, next_url).url

    def test_next_de_outro_site_e_ignorado(self):
        usuario = SimpleNamespace(deve_trocar_senha=False, is_superuser=False, is_staff=False)
        self.assertEqual(self.destino(usuario, 'https://site-malicioso.com/'), reverse('dashboard'))
        self.assertEqual(self.destino(usuario, '/relatorios/'), '/relatorios/')

    def test_superusuario_ou_equipe_vao_para_o_admin(self):
        for superusuario, equipe in ((True, False), (False, True)):
            with self.subTest(superusuario=superusuario, equipe=equipe):
                usuario = SimpleNamespace(deve_trocar_senha=False, is_superuser=superusuario, is_staff=equipe)
                self.assertEqual(self.destino(usuario), '/admin/')


class ExportacaoInvalidaTest(TestCase):

    def test_mensagem_da_secao_invalida(self):
        with self.assertRaises(Http404) as erro:
            _exportar(RequestFactory().get('/'), 'inexistente', 'pdf')
        self.assertEqual(str(erro.exception), "Seção de relatório inválida.")


class TelasDaLojaTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.usuario = get_user_model().objects.create_user(username="op", password="senha-certa", loja=self.c.loja,
                                                            deve_trocar_senha=False)
        self.client.force_login(self.usuario)
        self.agora = timezone.now()

    def contexto(self, rota, **parametros):
        resposta = self.client.get(reverse(rota, kwargs=parametros.pop('argumentos', {})), parametros)
        self.assertEqual(resposta.status_code, 200)
        return resposta.context

    def mensagens(self, resposta):
        """As mensagens mostradas na página para onde o envio levou (siga o redirecionamento com follow=True)."""
        return [str(mensagem) for mensagem in resposta.context['messages']]

    def test_inicio(self):
        for numero in range(6):
            self.c.venda(self.agora, [(self.c.produto(f"P{numero}", estoque=100), 1)])
        contexto = self.contexto('dashboard')
        self.assertEqual(set(contexto.keys()) >= {
            'limite_estoque', 'opcoes_de_limite', 'hoje_por_extenso', 'grafico_faturamento', 'mais_vendidos',
            'grafico_mais_vendidos', 'grafico_fluxo', 'mapa', 'reposicao', 'cobrancas', 'mes_atual', 'resultado_do_mes',
        }, True)
        self.assertEqual(contexto['opcoes_de_limite'], (1, 2, 3, 5, 10, 20))
        self.assertEqual(len(contexto['grafico_faturamento']['rotulos']), 30)
        self.assertEqual(len(contexto['mais_vendidos']), 5)
        self.assertEqual(contexto['grafico_mais_vendidos']['series'][0]['nome'], 'Quantidade')
        self.assertEqual(len(contexto['grafico_fluxo']['rotulos']), 6)

    def test_inicio_ranking_dos_ultimos_30_dias_e_reposicao_de_7(self):
        dentro, fora = self.c.produto("Dentro"), self.c.produto("Fora")
        self.c.venda(self.agora - timedelta(days=29), [(dentro, 1)])
        self.c.venda(self.agora - timedelta(days=30), [(fora, 1)])
        self.assertEqual([p.nome for p in self.contexto('dashboard')['mais_vendidos']], ["Dentro"])
        sete, oito = self.c.produto("Sete", estoque=7), self.c.produto("Oito", estoque=8)
        self.c.venda(self.agora - timedelta(days=1), [(sete, 30), (oito, 30)])
        self.assertEqual([r.nome for r in self.contexto('dashboard')['reposicao']], ["Sete"])

    def test_gastos(self):
        contexto = self.contexto('gastos')
        self.assertEqual(set(contexto.keys()) >= {
            'mes', 'meses', 'aba', 'abas', 'hoje', 'resultado', 'despesas', 'compras', 'perdas', 'produtos', 'categorias',
            'motivos'}, True)
        self.assertEqual(contexto['abas'], (('despesa', 'Despesa'), ('compra', 'Compra'), ('perda', 'Perda')))
        self.assertEqual(contexto['mes'].chave, f"{timezone.localdate():%Y-%m}")

    def test_mensagens_de_excluir_compra_e_perda(self):
        from application.gastos.services import registrar_compra, registrar_perda
        produto = self.c.produto("Farinha", estoque=10)
        hoje = timezone.localdate()
        compra = registrar_compra(loja=self.c.loja, itens=[(produto.pk, Decimal('1'), Decimal('1'))], data=hoje, usuario=self.usuario)
        perda = registrar_perda(loja=self.c.loja, produto_id=produto.pk, quantidade=Decimal('1'), data=hoje, motivo='x',
                                usuario=self.usuario)
        for tipo, registro, mensagem in (('compra', compra, "Compra excluída. O estoque foi corrigido."),
                                         ('perda', perda, "Perda excluída. O estoque foi devolvido.")):
            with self.subTest(tipo):
                resposta = self.client.post(reverse('excluir_gasto', kwargs={'tipo': tipo, 'pk': registro.pk}), follow=True)
                self.assertEqual(self.mensagens(resposta), [mensagem])

    def test_editar_venda(self):
        cliente = self.c.cliente("Ana")
        venda = self.c.venda(self.agora, [(self.c.produto("Pão"), 1)], cliente=cliente)
        contexto = self.contexto('venda_editar', argumentos={'venda_id': venda.pk})
        self.assertEqual((list(contexto['clientes']), contexto['formas_de_pagamento'], contexto['forma_obrigatoria']),
                         ([cliente], FormaDePagamento.choices, False))
        PagamentoCliente.objects.create(loja=self.c.loja, cliente=cliente, venda=venda, valor=Decimal('0.50'))
        self.assertTrue(self.contexto('venda_editar', argumentos={'venda_id': venda.pk})['forma_obrigatoria'])
        produto = venda.itens.get().produto
        resposta = self.client.post(reverse('venda_editar', kwargs={'venda_id': venda.pk}), {
            'cliente': cliente.pk, 'item_produto': produto.pk, 'item_quantidade': '1', 'forma_pagamento': 'pix'}, follow=True)
        self.assertEqual(self.mensagens(resposta), ["Venda atualizada com sucesso!"])

    def test_outras_telas(self):
        cliente = self.c.cliente("Ana Maria")
        self.assertEqual(self.contexto('vendas')['formas_de_pagamento'], FormaDePagamento.choices)
        self.assertEqual(self.contexto('clientes', q='Ana')['filtro_busca'], 'Ana')
        self.assertEqual(self.contexto('produtos')['maximo_de_fotos'], MAXIMO_DE_FOTOS)
        self.assertEqual(self.contexto('extrato_cliente', argumentos={'cliente_id': cliente.pk})['formas_de_pagamento'],
                         FormaDePagamento.choices)
        self.assertEqual(self.contexto('configuracoes')['tamanho_maximo_mb'], 15)
        geral = self.contexto('relatorios', data_inicio='2026-01-01', data_fim='2026-01-31')
        self.assertEqual((geral['aba'], geral['data_inicio'], geral['data_fim']), ('geral', date(2026, 1, 1), date(2026, 1, 31)))

    def test_pdf_do_extrato(self):
        cliente = self.c.cliente("Ana Maria")
        resposta = self.client.get(reverse('extrato_pdf', kwargs={'cliente_id': cliente.pk}))
        self.assertTrue(b''.join(resposta.streaming_content).startswith(b'%PDF'))
        self.assertEqual(resposta['Content-Disposition'], 'attachment; filename="extrato_Ana_Maria.pdf"')

    def test_mensagens_de_sucesso(self):
        cliente = self.c.cliente("Ana")
        produto = self.c.produto("Pão")
        casos = [
            ('editar_produto', {'pk': produto.pk}, {'nome': 'Pão', 'preco_venda': '1'}, "Produto atualizado com sucesso!"),
            ('extrato_cliente', {'cliente_id': cliente.pk}, {'valor': '1', 'forma_pagamento': 'pix'},
             "Pagamento registrado com sucesso!"),
            ('cliente_apagar_dados', {'cliente_id': self.c.cliente("Bia").pk}, {'senha': 'senha-certa'},
             "Dados pessoais apagados. As compras e os pagamentos continuam nos relatórios, sem o nome."),
        ]
        for rota, argumentos, dados, mensagem in casos:
            with self.subTest(rota):
                resposta = self.client.post(reverse(rota, kwargs=argumentos), dados, follow=True)
                self.assertEqual(self.mensagens(resposta), [mensagem])


class ConfiguracoesDoDonoTest(TestCase):

    def test_suporte_do_painel_global_e_sem_plano(self):
        dono = get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.force_login(dono)
        self.assertEqual(self.client.get(reverse('configuracoes')).context['link_suporte'],
                         CORSARIOS_CODE.link_suporte('Painel global'))
        pedido = RequestFactory().get('/')
        pedido.user = dono
        with self.assertRaises(Http404) as erro:
            _loja_do_usuario(pedido)
        self.assertEqual(str(erro.exception), "Só lojas têm plano.")


class LoginTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        get_user_model().objects.create_user(username="ana", password="certa", loja=self.loja, deve_trocar_senha=False)

    def erros(self, resposta):
        return resposta.context['form'].non_field_errors()

    def test_mensagens(self):
        self.assertEqual(self.erros(self.client.post(reverse('login'), {'username': 'ana', 'password': 'errada'})),
                         ['Usuário ou senha inválidos.'])
        LojaModel.objects.filter(pk=self.loja.pk).update(ativo=False)
        self.assertEqual(self.erros(self.client.post(reverse('login'), {'username': 'ana', 'password': 'certa'})),
                         ['Esta loja está desativada. Procure o administrador.'])
        with patch('interfaces.views.login_view.minutos_bloqueado', return_value=1):
            self.assertEqual(self.erros(self.client.post(reverse('login'), {'username': 'ana', 'password': 'x'})),
                             ['Muitas tentativas com senha errada. Por segurança, tente de novo daqui a 1 minuto.'])

    def test_next_vem_do_endereco_ou_do_formulario(self):
        self.assertEqual(self.client.get(reverse('login')).context['next'], '')
        self.assertEqual(self.client.get(reverse('login'), {'next': '/gastos/'}).context['next'], '/gastos/')
        resposta = self.client.post(reverse('login'), {'username': 'ana', 'password': 'certa', 'next': '/gastos/'})
        self.assertEqual(resposta['Location'], '/gastos/')
