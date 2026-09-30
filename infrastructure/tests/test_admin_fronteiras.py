"""Fronteiras e textos exatos do admin (achados pelo teste de mutação)."""
import json
import string
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.admin import site
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
import infrastructure
from infrastructure.admin.painel import (
    Cartao, cartoes, grafico_lojas_novas_por_mes, grafico_recebido_por_mes, grafico_situacao_dos_planos, tabela_ultimas_cobrancas,
    painel_do_admin, tabela_vencendo,
)
from infrastructure.models import (
    Backup, Cobranca, ConfiguracaoDeBackup, ErroDoSistema, LojaModel, Plano, RegistroDeAlteracao, UnidadeDoIntervalo,
    UsuarioModel,
)
from infrastructure.tests.test_backup_admin import CONFIGURACAO, LISTA, _backup
from infrastructure.utils.supabase_storage import StorageError
from infrastructure.tests.test_admin_painel import cobranca
from tests.apoio import ComPlanosIniciais, dataclasses_do_pacote

HOJE = timezone.localdate()


class DataclassesDaInfraestruturaTest(SimpleTestCase):

    def test_sao_congeladas(self):
        classes = dataclasses_do_pacote(infrastructure)
        self.assertGreaterEqual(len(classes), 4)  # inclusive as de utils/, pasta sem __init__.py
        for classe in classes:
            with self.subTest(classe.__qualname__):
                self.assertTrue(classe.__dataclass_params__.frozen)


class PainelFronteirasTest(ComPlanosIniciais, TestCase):

    def test_avisa_quem_vence_em_ate_7_dias(self):
        LojaModel.objects.create(nome_loja="Sete", vencimento=HOJE + timedelta(days=7))
        LojaModel.objects.create(nome_loja="Oito", vencimento=HOJE + timedelta(days=8))
        ativas = LojaModel.objects.filter(ativo=True)
        self.assertEqual([linha[2] for linha in tabela_vencendo(ativas, HOJE)['rows']], ["7 dias"])
        self.assertEqual(grafico_situacao_dos_planos(ativas, HOJE)['datasets'][0]['data'], [1, 1, 0])

    def test_mostra_as_5_ultimas_cobrancas(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        for _ in range(6):
            cobranca(loja)
        self.assertEqual(len(tabela_ultimas_cobrancas()['rows']), 5)

    def test_nomes_dos_meses_e_cores(self):
        rotulos = [*grafico_lojas_novas_por_mes(date(2026, 6, 15))['labels'],
                   *grafico_lojas_novas_por_mes(date(2026, 12, 15))['labels']]
        self.assertEqual(rotulos, ['jan/26', 'fev/26', 'mar/26', 'abr/26', 'mai/26', 'jun/26',
                                   'jul/26', 'ago/26', 'set/26', 'out/26', 'nov/26', 'dez/26'])
        self.assertEqual(grafico_recebido_por_mes(HOJE)['datasets'][0]['backgroundColor'], 'var(--color-primary-600)')
        self.assertEqual(grafico_situacao_dos_planos(LojaModel.objects.none(), HOJE)['datasets'][0]['backgroundColor'],
                         ['var(--color-primary-600)', '#c96a05', '#d03b3b'])


def _mensagens(resposta):
    return [str(mensagem) for mensagem in get_messages(resposta.wsgi_request)]


class BackupAdminDetalhesTest(TestCase):

    def setUp(self):
        self.config_admin = site._registry[ConfiguracaoDeBackup]
        self.backup_admin = site._registry[Backup]
        self.dono = get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.force_login(self.dono)

    def test_datas_da_configuracao(self):
        config = ConfiguracaoDeBackup(ativo=False, a_cada=1, unidade=UnidadeDoIntervalo.DIAS)
        self.assertEqual((self.config_admin.ultimo(config), self.config_admin.proximo(config)), ('—', 'Desligado'))
        config.ativo = True
        self.assertEqual(self.config_admin.proximo(config), 'Na próxima chamada do agendador')
        config.ultimo_em = timezone.make_aware(datetime(2026, 3, 1, 10, 5))
        self.assertEqual((self.config_admin.ultimo(config), self.config_admin.proximo(config)),
                         ('01/03/2026 10:05', '02/03/2026 10:05'))

    def test_colunas_da_lista(self):
        guardado = _backup()
        falhou = _backup(sucesso=False, erro='e' * 130)
        admin = self.backup_admin
        self.assertEqual((admin.situacao(guardado), admin.situacao(falhou)), ('Guardado', 'Falhou'))
        self.assertEqual((admin.tamanho_legivel(guardado), admin.tamanho_legivel(falhou)), ('1,5\xa0KB', '—'))
        self.assertEqual(admin.baixar(falhou), 'e' * 120)
        self.assertEqual(admin.baixar(guardado),
                         f'<a class="text-primary-600" href="/admin/infrastructure/backup/{guardado.pk}/baixar/">Baixar</a>')

    def test_permissoes_do_dono(self):
        pedido = SimpleNamespace(user=self.dono)
        self.assertEqual(
            [self.backup_admin.has_add_permission(pedido), self.backup_admin.has_change_permission(pedido),
             self.backup_admin.has_delete_permission(pedido), self.backup_admin.has_view_permission(pedido),
             self.backup_admin.has_module_permission(pedido)],
            [False, False, False, True, True],
        )
        self.assertEqual(
            [self.config_admin.has_add_permission(pedido), self.config_admin.has_change_permission(pedido),
             self.config_admin.has_delete_permission(pedido)],
            [False, True, False],
        )

    def test_mensagens(self):
        ConfiguracaoDeBackup.atual()
        resposta = self.client.post(f'{CONFIGURACAO}1/change/', {'ativo': 'on', 'a_cada': 6, 'unidade': 'horas', 'manter': 10})
        self.assertEqual(_mensagens(resposta), ["Configuração de backup salva."])

    def test_mensagem_de_fazer_agora(self):
        with patch('infrastructure.admin.backup_admin.pedir_backup', return_value=(True, '')):
            resposta = self.client.get(f'{LISTA}fazer-agora/')
        self.assertEqual(_mensagens(resposta), ["Backup iniciado. Em instantes ele aparece aqui (atualize a página)."])

    def test_mensagem_de_falha_ao_baixar(self):
        backup = _backup()
        with patch('infrastructure.admin.backup_admin.BackupsNoSupabase.from_settings') as fonte:
            fonte.return_value.baixar.side_effect = StorageError("Supabase fora do ar")
            resposta = self.client.get(f'{LISTA}{backup.pk}/baixar/')
        self.assertEqual(_mensagens(resposta), ["Não deu para baixar o backup: Supabase fora do ar"])

    def test_arquivo_baixado_e_binario(self):
        backup = _backup()
        with patch('infrastructure.admin.backup_admin.BackupsNoSupabase.from_settings'):
            resposta = self.client.get(f'{LISTA}{backup.pk}/baixar/')
        self.assertEqual(resposta['Content-Type'], 'application/octet-stream')


class ErrosEAssinaturasNoAdminTest(ComPlanosIniciais, TestCase):

    def setUp(self):
        self.erros = site._registry[ErroDoSistema]
        self.client.force_login(
            get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False))

    def test_colunas_do_erro(self):
        self.assertEqual((self.erros.situacao(ErroDoSistema(resolvido=True)), self.erros.situacao(ErroDoSistema())),
                         ('Resolvido', 'Em aberto'))
        self.assertEqual(self.erros.caminho_do_erro(ErroDoSistema(detalhes='<b>linha</b>')),
                         '<pre class="whitespace-pre-wrap text-xs">&lt;b&gt;linha&lt;/b&gt;</pre>')
        self.assertEqual(self.erros.caminho_do_erro(ErroDoSistema()), '<pre class="whitespace-pre-wrap text-xs">—</pre>')

    def test_acoes_do_erro(self):
        erros = [ErroDoSistema.objects.create(assinatura=letra, tipo='ValueError') for letra in 'ab']
        lista = '/admin/infrastructure/errodosistema/'
        selecionados = [erro.pk for erro in erros]
        resposta = self.client.post(lista, {'action': 'marcar_resolvidos', '_selected_action': selecionados})
        self.assertEqual(_mensagens(resposta), ["2 erro(s) marcado(s) como resolvido(s)."])
        self.assertEqual(ErroDoSistema.objects.filter(resolvido=True).count(), 2)

    def test_reabrir(self):
        erro = ErroDoSistema.objects.create(assinatura='a', tipo='ValueError', resolvido=True)
        resposta = self.client.post('/admin/infrastructure/errodosistema/', {'action': 'reabrir', '_selected_action': [erro.pk]})
        self.assertEqual(_mensagens(resposta), ["1 erro(s) reaberto(s)."])
        erro.refresh_from_db()
        self.assertFalse(erro.resolvido)

    def test_plano_e_cobranca(self):
        planos = site._registry[Plano]
        self.assertEqual(planos.duracao(Plano(quantidade=30, unidade='dias')), '30 dias')
        cobrancas = site._registry[Cobranca]
        paga = cobranca(LojaModel.objects.create(nome_loja="Loja"), '49.90')
        self.assertEqual(cobrancas.valor_em_reais(paga), 'R$ 49,90')
        self.assertEqual(cobrancas.situacao(paga), ('paga', 'Paga'))


DESTAQUE = "<strong style='background: #fff; color: #000; padding: 2px 6px; border-radius: 4px;'>{}</strong>"


class UsuariosNoAdmin(TestCase):
    """Cenário: dono, caixa da Loja A e as duas lojas."""

    def setUp(self):
        self.usuarios = site._registry[UsuarioModel]
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.outra = LojaModel.objects.create(nome_loja="Loja B")
        self.dono = UsuarioModel.objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.caixa = UsuarioModel.objects.create_user(username="caixa", password="x", loja=self.loja)

    def pedido(self, usuario, metodo='post'):
        pedido = getattr(RequestFactory(), metodo)('/admin/')
        pedido.user = usuario
        SessionMiddleware(lambda req: None).process_request(pedido)
        MessageMiddleware(lambda req: None).process_request(pedido)
        return pedido


class UsuarioAdminDetalhesTest(UsuariosNoAdmin):

    def test_resetar_senha_mostra_a_senha_nova_de_8_letras_ou_numeros(self):
        pedido = self.pedido(self.dono)
        with patch('infrastructure.admin.usuario_admin.secrets') as sorteio:
            sorteio.choice.return_value = 'k'
            self.usuarios.reset_password_view(pedido, self.caixa.pk)
        self.assertEqual(sorteio.choice.call_count, 8)
        sorteio.choice.assert_called_with(string.ascii_letters + string.digits)
        self.assertEqual([str(m) for m in get_messages(pedido)], [
            "Senha do usuário <b>caixa</b> resetada com sucesso! Nova senha temporária: " + DESTAQUE.format('kkkkkkkk'),
        ])
        self.caixa.refresh_from_db()
        self.assertTrue(self.caixa.check_password('kkkkkkkk'))

    def test_criar_usuario_mostra_a_senha_temporaria(self):
        pedido = self.pedido(self.dono)
        novo = UsuarioModel(username="novo", loja=self.loja)
        with patch('infrastructure.admin.usuario_admin.secrets') as sorteio:
            sorteio.choice.return_value = '7'
            self.usuarios.save_model(pedido, novo, form=None, change=False)
        self.assertEqual(sorteio.choice.call_count, 8)
        sorteio.choice.assert_called_with(string.ascii_letters + string.digits)
        self.assertEqual([str(m) for m in get_messages(pedido)], [
            "Usuário <b>novo</b> criado com sucesso! Senha temporária gerada: " + DESTAQUE.format('77777777'),
        ])

    def test_mensagens_de_acesso_negado(self):
        gerente = UsuarioModel.objects.create_user(username="gerente", password="x", loja=self.loja, is_staff=True)
        de_fora = UsuarioModel.objects.create_user(username="de_fora", password="x", loja=self.outra)
        casos = [
            (lambda: self.usuarios.reset_password_view(self.pedido(self.dono, 'get'), self.caixa.pk),
             "Método não permitido para esta operação."),
            (lambda: self.usuarios.reset_password_view(self.pedido(gerente), self.dono.pk),
             "Você não tem permissão para alterar as credenciais de um superusuário."),
            (lambda: self.usuarios.reset_password_view(self.pedido(gerente), de_fora.pk),
             "Acesso negado: Este usuário pertence a outra loja."),
            (lambda: self.usuarios.save_model(self.pedido(gerente), UsuarioModel(username="x", is_staff=True), None, False),
             "Você não tem permissão para criar usuários com privilégios administrativos."),
        ]
        for chamada, mensagem in casos:
            with self.subTest(mensagem), self.assertRaises(PermissionDenied) as erro:
                chamada()
            self.assertEqual(str(erro.exception), mensagem)

    def test_colunas(self):
        self.assertEqual(
            [self.usuarios.tipo_de_acesso(u) for u in (self.dono, UsuarioModel(is_staff=True), self.caixa)],
            [('superusuario', "Superusuário"), ('equipe', "Equipe"), ('loja', "Loja")],
        )
        self.assertEqual([self.usuarios.senha(UsuarioModel(deve_trocar_senha=valor)) for valor in (True, False)],
                         [('trocar', "Precisa trocar"), ('ok', "Definida")])


class RegistroDeAlteracaoAdminDetalhesTest(SimpleTestCase):

    def test_detalhes_sem_contatos_legiveis(self):
        registros = site._registry[RegistroDeAlteracao]
        registro = RegistroDeAlteracao(acao='venda_cancelada', detalhes={'nome': 'João', 'telefone': '24 99999-0000'})
        self.assertEqual(registros.detalhes_sem_contatos(registro), (
            '<pre class="whitespace-pre-wrap text-xs">{\n  &quot;nome&quot;: &quot;João&quot;,\n'
            '  &quot;telefone&quot;: &quot;(oculto)&quot;\n}</pre>'
        ))
        self.assertEqual(registros.tipo(registro), ('venda_cancelada', 'Venda cancelada'))


def _momento(*partes):
    return timezone.make_aware(datetime(*partes))


class PainelCompletoTest(ComPlanosIniciais, TestCase):
    """Dia fixo (15/03/2026) para conferir cada número, texto e fronteira de data do painel."""

    DIA = date(2026, 3, 15)

    def test_cartoes(self):
        vazia = LojaModel.objects.create(nome_loja="Vazia", vencimento=self.DIA - timedelta(days=1))
        self.assertEqual(cartoes(LojaModel.objects.filter(ativo=True), self.DIA)[3].valor, 'R$ 0,00')
        paga_no_dia_1 = cobranca(vazia, '20.00', paga_em=_momento(2026, 3, 1, 0, 30))
        cobranca(vazia, '7.00', paga_em=_momento(2026, 2, 28, 23, 30))
        self.assertEqual(paga_no_dia_1.loja, vazia)
        self.assertEqual(cartoes(LojaModel.objects.filter(ativo=True), self.DIA), [
            Cartao("Lojas ativas", "1", "0 em teste grátis", "/admin/infrastructure/lojamodel/?ativo__exact=1"),
            Cartao("Vencem em até 7 dias", "0", "Hora de lembrar de renovar", "/admin/infrastructure/lojamodel/"),
            Cartao("Planos vencidos", "1", "Em modo só consulta", "/admin/infrastructure/lojamodel/"),
            Cartao("Recebido no mês", "R$ 20,00", "Planos pagos por Pix", "/admin/infrastructure/cobranca/"),
        ])

    def test_graficos_de_barras(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        LojaModel.objects.filter(pk=loja.pk).update(criado_em=_momento(2025, 10, 1, 0, 30))
        cobranca(loja, '12.50', paga_em=_momento(2025, 10, 1, 0, 30))
        meses = ['out/25', 'nov/25', 'dez/25', 'jan/26', 'fev/26', 'mar/26']
        self.assertEqual(grafico_recebido_por_mes(self.DIA), {
            'labels': meses,
            'datasets': [{'label': "Recebido (R$)", 'data': [12.5, 0.0, 0.0, 0.0, 0.0, 0.0],
                          'backgroundColor': 'var(--color-primary-600)'}],
        })
        self.assertEqual(grafico_lojas_novas_por_mes(self.DIA), {
            'labels': meses,
            'datasets': [{'label': "Lojas novas", 'data': [1, 0, 0, 0, 0, 0], 'backgroundColor': 'var(--color-primary-600)'}],
        })

    def test_situacao_dos_planos(self):
        self.assertEqual(grafico_situacao_dos_planos(LojaModel.objects.none(), self.DIA), {
            'labels': ["Em dia", "Vencendo", "Vencidas"],
            'datasets': [{'label': "Lojas", 'data': [0, 0, 0],
                          'backgroundColor': ['var(--color-primary-600)', '#c96a05', '#d03b3b']}],
        })

    def test_tabelas(self):
        lojas = [LojaModel.objects.create(nome_loja=f"L{i:02d}", vencimento=self.DIA + timedelta(days=1)) for i in range(11)]
        vencendo = tabela_vencendo(LojaModel.objects.filter(ativo=True).order_by('pk'), self.DIA)
        self.assertEqual(vencendo['headers'], ["Loja", "Vencimento", "Faltam"])
        self.assertEqual(len(vencendo['rows']), 10)
        self.assertEqual(vencendo['rows'][0], [
            f'<a href="/admin/infrastructure/lojamodel/{lojas[0].pk}/change/" class="text-primary-600 font-semibold">L00</a>',
            '16/03/2026', '1 dia',
        ])
        paga = cobranca(lojas[0], '9.90', paga_em=_momento(2026, 3, 2, 9, 5))
        Cobranca.objects.filter(pk=paga.pk).update(criada_em=_momento(2026, 3, 2, 9, 5))
        self.assertEqual(tabela_ultimas_cobrancas(), {
            'headers': ["Data", "Loja", "Plano", "Valor", "Situação"],
            'rows': [['02/03 09:05', 'L00', '30 dias', 'R$ 9,90', 'Paga']],
        })

    def test_painel_completo_para_o_dono(self):
        contexto = painel_do_admin(SimpleNamespace(user=SimpleNamespace(is_superuser=True)), {})
        self.assertEqual(sorted(contexto['painel']), [
            'cartoes', 'erros', 'grafico_lojas_novas', 'grafico_recebido', 'grafico_situacao', 'ultimas_cobrancas',
            'vencendo',
        ])
        self.assertEqual(json.loads(contexto['painel']['grafico_recebido'])['datasets'][0]['label'], "Recebido (R$)")
        self.assertEqual(json.loads(contexto['painel']['grafico_lojas_novas'])['datasets'][0]['label'], "Lojas novas")


class UsuarioAdminPermissoesTest(UsuariosNoAdmin):

    def test_dono_reseta_outro_superusuario_e_gerente_reseta_a_propria_loja(self):
        outro_dono = UsuarioModel.objects.create_superuser(username="socio", password="x")
        gerente = UsuarioModel.objects.create_user(username="gerente", password="x", loja=self.loja, is_staff=True)
        self.assertEqual(self.usuarios.reset_password_view(self.pedido(self.dono), outro_dono.pk).status_code, 302)
        self.assertEqual(self.usuarios.reset_password_view(self.pedido(gerente), self.caixa.pk).status_code, 302)

    def test_editar_usuario_sem_senha_gera_uma(self):
        self.caixa.set_unusable_password()
        self.caixa.save()
        pedido = self.pedido(self.dono)
        self.usuarios.save_model(pedido, self.caixa, form=None, change=True)
        self.assertTrue(self.caixa.has_usable_password())
        self.assertEqual(len(list(get_messages(pedido))), 1)


class LojaAdminDetalhesTest(TestCase):

    def setUp(self):
        self.lojas = site._registry[LojaModel]

    def test_situacao_do_plano_nas_fronteiras(self):
        hoje = timezone.localdate()
        casos = {-91: ('vencido', "Vencido há +90 dias: apagar"), -90: ('vencido', "Vencido"), -1: ('vencido', "Vencido"),
                 0: ('vencendo', "Vence em breve"), 7: ('vencendo', "Vence em breve"), 8: ('em_dia', "Em dia")}
        for dias, esperado in casos.items():
            with self.subTest(dias):
                self.assertEqual(self.lojas.situacao_do_plano(LojaModel(vencimento=hoje + timedelta(days=dias))), esperado)
        self.assertEqual(self.lojas.situacao_do_plano(LojaModel(ativo=False)), ('inativa', "Fora do ar"))

    def test_usuarios_usa_a_contagem_da_lista(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        self.assertEqual(self.lojas.usuarios(loja), 0)
        loja.total_de_usuarios = 12
        self.assertEqual(self.lojas.usuarios(loja), 12)

    def test_so_salva_a_propria_loja(self):
        minha, outra = LojaModel.objects.create(nome_loja="Minha"), LojaModel.objects.create(nome_loja="Outra")
        pedido = SimpleNamespace(user=SimpleNamespace(is_superuser=False, loja=minha))
        with self.assertRaises(PermissionDenied) as erro:
            self.lojas.save_model(pedido, outra, None, True)
        self.assertEqual(str(erro.exception), "Acesso negado: Você não tem permissão para alterar esta loja.")

    def test_endereco_da_marca_sem_esquema_vira_https(self):
        campo = self.lojas.formfield_for_dbfield(LojaModel._meta.get_field('logo_url'), SimpleNamespace(user=None))
        self.assertEqual(campo.clean('exemplo.com/logo.png'), 'https://exemplo.com/logo.png')
