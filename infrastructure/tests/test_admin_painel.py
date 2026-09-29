import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from infrastructure.admin.painel import (
    _ultimos_meses, cartoes, erros_em_aberto, grafico_lojas_novas_por_mes, grafico_recebido_por_mes, grafico_situacao_dos_planos,
    painel_do_admin, tabela_ultimas_cobrancas, tabela_vencendo,
)
from infrastructure.admin.tema import favicons, menu_lateral
from infrastructure.models import Cobranca, ErroDoSistema, LojaModel, Plano, StatusDaCobranca
from tests.apoio import ComPlanosIniciais

HOJE = timezone.localdate()


def cobranca(loja, valor='10.00', status=StatusDaCobranca.PAGA, paga_em=None):
    plano = Plano.objects.get(nome="30 dias")
    return Cobranca.objects.create(
        loja=loja, plano=plano, plano_nome=plano.nome, quantidade=30, unidade='dias', valor=Decimal(valor),
        email_pagador='a@b.com', expira_em=timezone.now(), status=status, paga_em=paga_em,
    )


class PainelTest(ComPlanosIniciais, TestCase):

    def setUp(self):
        self.em_dia = LojaModel.objects.create(nome_loja="Em dia", vencimento=HOJE + timedelta(days=30))
        self.vencendo = LojaModel.objects.create(nome_loja="Vencendo", vencimento=HOJE + timedelta(days=1))
        self.vencida = LojaModel.objects.create(nome_loja="Vencida", vencimento=HOJE - timedelta(days=3))
        LojaModel.objects.create(nome_loja="Fora do ar", ativo=False, vencimento=HOJE - timedelta(days=90))
        cobranca(self.em_dia, '30.00', paga_em=timezone.now())
        cobranca(self.vencendo, '99.00', status=StatusDaCobranca.PENDENTE)

    def ativas(self):
        return LojaModel.objects.filter(ativo=True)

    def test_cartoes(self):
        valores = {c.titulo: (c.valor, c.detalhe) for c in cartoes(self.ativas(), HOJE)}
        self.assertEqual(valores["Lojas ativas"], ("3", "2 em teste grátis"))
        self.assertEqual(valores["Vencem em até 7 dias"][0], "1")
        self.assertEqual(valores["Planos vencidos"][0], "1")
        self.assertEqual(valores["Recebido no mês"][0], "R$ 30,00")  # a pendente não conta

    def test_situacao_dos_planos(self):
        dados = grafico_situacao_dos_planos(self.ativas(), HOJE)
        self.assertEqual(dados['labels'], ["Em dia", "Vencendo", "Vencidas"])
        self.assertEqual(dados['datasets'][0]['data'], [1, 1, 1])

    def test_recebido_e_lojas_novas_nos_ultimos_seis_meses(self):
        recebido = grafico_recebido_por_mes(HOJE)
        novas = grafico_lojas_novas_por_mes(HOJE)
        self.assertEqual(len(recebido['labels']), 6)
        self.assertEqual(recebido['datasets'][0]['data'][-1], 30.0)
        self.assertEqual(sum(recebido['datasets'][0]['data']), 30.0)
        self.assertEqual(novas['datasets'][0]['data'][-1], 4)

    def test_tabelas(self):
        vencendo = tabela_vencendo(self.ativas(), HOJE)
        self.assertEqual(len(vencendo['rows']), 1)
        self.assertIn("Vencendo", vencendo['rows'][0][0])
        self.assertEqual(vencendo['rows'][0][2], "1 dia")
        ultimas = tabela_ultimas_cobrancas()
        self.assertEqual([linha[4] for linha in ultimas['rows']], ["Aguardando pagamento", "Paga"])

    def test_dias_que_faltam(self):
        LojaModel.objects.filter(pk=self.vencendo.pk).update(vencimento=HOJE)
        LojaModel.objects.create(nome_loja="Cinco", vencimento=HOJE + timedelta(days=5))
        faltam = [linha[2] for linha in tabela_vencendo(self.ativas(), HOJE)['rows']]
        self.assertEqual(faltam, ["vence hoje", "5 dias"])

    def test_meses_viram_o_ano(self):
        self.assertEqual(_ultimos_meses(date(2026, 2, 15)),
                         [date(2025, 9, 1), date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)])

    def test_so_o_superusuario_ve_o_painel(self):
        request = SimpleNamespace(user=SimpleNamespace(is_superuser=False))
        self.assertEqual(painel_do_admin(request, {'x': 1}), {'x': 1})

        request.user.is_superuser = True
        contexto = painel_do_admin(request, {'x': 1})
        self.assertEqual(contexto['x'], 1)
        self.assertEqual(json.loads(contexto['painel']['grafico_situacao'])['datasets'][0]['data'], [1, 1, 1])

    def test_erros_em_aberto(self):
        ErroDoSistema.objects.create(assinatura='a', tipo='ValueError')
        ErroDoSistema.objects.create(assinatura='b', tipo='KeyError', resolvido=True)
        self.assertEqual(erros_em_aberto(), {
            'quantidade': 1, 'link': '/admin/infrastructure/errodosistema/?resolvido__exact=0',
        })


class TemaTest(TestCase):

    def test_menu_mostra_so_o_que_o_usuario_pode_ver(self):
        grupos = menu_lateral(None)
        self.assertEqual([g.get('title') for g in grupos], [None, "Lojas", "Assinaturas", "Auditoria", "Sistema"])
        self.assertEqual([i['title'] for i in grupos[4]['items']], ["Erros do sistema", "Backups", "Tentativas de login"])
        lojas = grupos[1]['items'][0]
        self.assertEqual((lojas['title'], str(lojas['link'])), ("Lojas", "/admin/infrastructure/lojamodel/"))

        pode = SimpleNamespace(user=SimpleNamespace(has_perm=lambda perm: perm == 'infrastructure.view_lojamodel'))
        self.assertTrue(lojas['permission'](pode))
        self.assertFalse(grupos[1]['items'][1]['permission'](pode))
        self.assertNotIn('permission', grupos[0]['items'][0])  # o Painel aparece para todos

    def test_favicon_do_sistema(self):
        self.assertTrue(favicons(None)[0]['href'].endswith('images/icon-192.png'))


class TelasDoAdminTest(ComPlanosIniciais, TestCase):
    """Abre de verdade cada tela do admin com o tema: nada pode quebrar na troca de visual."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.force_login(self.admin)
        self.loja = LojaModel.objects.create(nome_loja="Padaria", logo_url="https://exemplo.com/logo.webp",
                                             vencimento=HOJE + timedelta(days=2))
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja)
        cobranca(self.loja, paga_em=timezone.now())

    def test_painel_com_graficos(self):
        response = self.client.get('/admin/')
        self.assertContains(response, "Recebido por mês")
        self.assertContains(response, 'data-type="bar"', count=3)
        self.assertContains(response, "Padaria")  # vence em 2 dias
        self.assertNotContains(response, "em aberto</strong>")

    def test_painel_avisa_dos_erros_em_aberto(self):
        ErroDoSistema.objects.create(assinatura='a', tipo='ValueError')
        ErroDoSistema.objects.create(assinatura='b', tipo='KeyError')
        response = self.client.get('/admin/')
        self.assertContains(response, "<strong>2 erros em aberto</strong>")
        self.assertContains(response, 'href="/admin/infrastructure/errodosistema/?resolvido__exact=0"')

    def test_erros_do_sistema(self):
        erro = ErroDoSistema.objects.create(
            assinatura='a', tipo='ValueError', mensagem="valor ruim", local="application/x.py:3 em f",
            caminho='/vendas/', metodo='POST', loja=self.loja, detalhes="Traceback <linha>\nValueError: valor ruim",
        )
        lista = self.client.get('/admin/infrastructure/errodosistema/')
        self.assertContains(lista, "Em aberto")
        self.assertContains(lista, "application/x.py:3 em f")
        tela = self.client.get(f'/admin/infrastructure/errodosistema/{erro.pk}/change/')
        self.assertContains(tela, "Traceback &lt;linha&gt;")  # o traceback aparece escapado, nunca como HTML
        self.assertEqual(self.client.get('/admin/infrastructure/errodosistema/add/').status_code, 403)

        url = '/admin/infrastructure/errodosistema/'
        self.client.post(url, {'action': 'marcar_resolvidos', '_selected_action': [erro.pk]})
        erro.refresh_from_db()
        self.assertTrue(erro.resolvido)
        self.assertContains(self.client.get(url), "Resolvido")
        self.client.post(url, {'action': 'reabrir', '_selected_action': [erro.pk]})
        erro.refresh_from_db()
        self.assertFalse(erro.resolvido)

    def test_erro_sem_traceback(self):
        erro = ErroDoSistema.objects.create(assinatura='a', tipo='application.produtos.services')
        self.assertContains(self.client.get(f'/admin/infrastructure/errodosistema/{erro.pk}/change/'), "—")

    def test_listas_e_formularios_abrem(self):
        from infrastructure.models import RegistroDeAlteracao
        registro = RegistroDeAlteracao.objects.create(loja=self.loja, acao='venda_cancelada', descricao="Venda #1")
        from application.contas.tentativas import registrar_falha
        from infrastructure.models import TentativasDeLogin
        registrar_falha('caixa')
        paginas = [
            '/admin/infrastructure/lojamodel/', f'/admin/infrastructure/lojamodel/{self.loja.pk}/change/',
            '/admin/infrastructure/lojamodel/add/',
            '/admin/infrastructure/usuariomodel/', f'/admin/infrastructure/usuariomodel/{self.usuario.pk}/change/',
            '/admin/infrastructure/usuariomodel/add/',
            '/admin/infrastructure/plano/', '/admin/infrastructure/plano/add/',
            '/admin/infrastructure/cobranca/', f'/admin/infrastructure/cobranca/{Cobranca.objects.get().pk}/change/',
            '/admin/infrastructure/registrodealteracao/',
            f'/admin/infrastructure/registrodealteracao/{registro.pk}/change/',
            '/admin/infrastructure/tentativasdelogin/',
            f'/admin/infrastructure/tentativasdelogin/{TentativasDeLogin.objects.get().pk}/change/',
        ]
        for pagina in paginas:
            with self.subTest(pagina):
                self.assertEqual(self.client.get(pagina).status_code, 200)
        self.assertEqual(self.client.get('/admin/infrastructure/tentativasdelogin/add/').status_code, 403)

    def test_pilulas_de_situacao(self):
        lojas = self.client.get('/admin/infrastructure/lojamodel/')
        self.assertContains(lojas, "Vence em breve")
        self.assertContains(self.client.get('/admin/infrastructure/cobranca/'), "Paga")
        usuarios = self.client.get('/admin/infrastructure/usuariomodel/')
        self.assertContains(usuarios, "Superusuário")
        self.assertContains(usuarios, "Precisa trocar")

    def test_resetar_senha_fica_num_formulario_proprio(self):
        response = self.client.get(f'/admin/infrastructure/usuariomodel/{self.usuario.pk}/change/')
        self.assertContains(response, f'action="/admin/infrastructure/usuariomodel/{self.usuario.pk}/resetar-senha/"')
        self.assertContains(response, "Gerar nova senha temporária")


class PilulasTest(TestCase):

    def test_situacao_do_plano_da_loja(self):
        from django.contrib.admin.sites import AdminSite
        from infrastructure.admin.loja_admin import LojaAdmin
        admin = LojaAdmin(LojaModel, AdminSite())
        casos = {
            'em dia': (LojaModel(ativo=True, vencimento=HOJE + timedelta(days=8)), ('em_dia', "Em dia")),
            'vencendo': (LojaModel(ativo=True, vencimento=HOJE + timedelta(days=7)), ('vencendo', "Vence em breve")),
            'vencido': (LojaModel(ativo=True, vencimento=HOJE - timedelta(days=1)), ('vencido', "Vencido")),
            'fora do ar': (LojaModel(ativo=False, vencimento=HOJE + timedelta(days=30)), ('inativa', "Fora do ar")),
        }
        for caso, (loja, esperado) in casos.items():
            with self.subTest(caso):
                self.assertEqual(admin.situacao_do_plano(loja), esperado)

    def test_marca_e_usuarios_da_loja(self):
        from django.contrib.admin.sites import AdminSite
        from infrastructure.admin.loja_admin import LojaAdmin
        admin = LojaAdmin(LojaModel, AdminSite())
        loja = LojaModel.objects.create(nome_loja="Sem marca")
        self.assertIsNone(admin.marca(loja))
        self.assertEqual(admin.usuarios(loja), 0)  # sem a contagem do queryset, conta direto

    def test_tipo_de_acesso_do_usuario(self):
        from django.contrib.admin.sites import AdminSite
        from infrastructure.admin.usuario_admin import CustomUserAdmin
        from infrastructure.models import UsuarioModel
        admin = CustomUserAdmin(UsuarioModel, AdminSite())
        self.assertEqual(admin.tipo_de_acesso(UsuarioModel(is_staff=True)), ('equipe', "Equipe"))
        self.assertEqual(admin.tipo_de_acesso(UsuarioModel()), ('loja', "Loja"))
        self.assertEqual(admin.senha(UsuarioModel(deve_trocar_senha=False)), ('ok', "Definida"))

    def test_endereco_da_marca_sem_esquema_vira_https(self):
        from django.contrib.admin.sites import AdminSite
        from infrastructure.admin.loja_admin import LojaAdmin
        campo = LojaAdmin(LojaModel, AdminSite()).formfield_for_dbfield(LojaModel._meta.get_field('logo_url'), None)
        self.assertEqual(campo.clean('exemplo.com/logo.webp'), 'https://exemplo.com/logo.webp')


class LoginDoAdminTest(TestCase):

    def test_login_direto_no_admin_vai_para_o_painel(self):
        """Regressão: o login do tema não manda ?next= e caía em /accounts/profile/ (404)."""
        get_user_model().objects.create_superuser(username="dono", password="senha-forte-1", deve_trocar_senha=False)
        response = self.client.post('/admin/login/', {'username': 'dono', 'password': 'senha-forte-1'})
        self.assertRedirects(response, '/admin/')


class TraducaoDoTemaTest(TestCase):

    def test_textos_do_tema_em_portugues(self):
        from django.utils import translation
        with translation.override('pt-br'):
            self.assertEqual(translation.gettext("Filters"), "Filtros")
            self.assertEqual(translation.gettext("Type to search"), "Digite para buscar")
            self.assertEqual(translation.ngettext("%(counter)s result", "%(counter)s results", 2) % {'counter': 2},
                             "2 resultados")

    def test_tela_de_lista_sem_ingles(self):
        get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.login(username="dono", password="x")
        response = self.client.get('/admin/infrastructure/lojamodel/')
        for texto in ("Filters", "Type to search", "Search apps and models"):
            with self.subTest(texto):
                self.assertNotContains(response, texto)
        self.assertContains(response, "Filtros")
