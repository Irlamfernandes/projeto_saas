import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from application.contas.services import trocar_tema
from infrastructure.models import LojaModel, Tema
from interfaces.context_processors import tema
from interfaces.templatetags.ajuda import AJUDA_POR_ROTA

User = get_user_model()
PASTA_DAS_AJUDAS = Path(settings.BASE_DIR) / 'interfaces' / 'templates' / 'interfaces' / 'ajuda'


class ComLojaTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria Pão de Mel")
        self.usuario = User.objects.create_user(username="Caixa 1", password="x", loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(self.usuario)


class TrocarTemaTest(ComLojaTestCase):

    def test_escolha_fica_salva_no_usuario(self):
        trocar_tema(self.usuario, Tema.ESCURO)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.tema, 'escuro')

    def test_usuario_novo_segue_o_aparelho(self):
        self.assertEqual(self.usuario.tema, Tema.AUTOMATICO)

    def test_tela_salva_e_volta_para_configuracoes(self):
        response = self.client.post(reverse('tema'), {'tema': 'escuro'})

        self.assertRedirects(response, reverse('configuracoes'))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.tema, 'escuro')
        self.assertIn("Aparência atualizada.", [str(m) for m in get_messages(response.wsgi_request)])

    def test_opcao_fora_da_lista_nao_salva(self):
        response = self.client.post(reverse('tema'), {'tema': 'rosa'})

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.tema, 'auto')
        self.assertIn("Escolha uma aparência da lista.", [str(m) for m in get_messages(response.wsgi_request)])

    def test_funciona_com_o_plano_vencido(self):
        self.loja.vencimento = timezone.localdate() - timedelta(days=1)
        self.loja.save()

        self.client.post(reverse('tema'), {'tema': 'claro'})

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.tema, 'claro')

    def test_so_aceita_envio_de_formulario(self):
        self.assertEqual(self.client.get(reverse('tema')).status_code, 405)

    def test_exige_login(self):
        self.client.logout()
        response = self.client.post(reverse('tema'), {'tema': 'escuro'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class TemaNaPaginaTest(ComLojaTestCase):

    def test_pagina_usa_o_tema_do_usuario(self):
        trocar_tema(self.usuario, Tema.ESCURO)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, '<html lang="pt-br" data-tema="escuro">')
        self.assertContains(response, '<meta name="theme-color" content="#0d1514">')

    def test_tema_claro_fixa_a_barra_do_navegador(self):
        trocar_tema(self.usuario, Tema.CLARO)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'data-tema="claro"')
        self.assertContains(response, '<meta name="theme-color" content="#0f766e">')

    def test_automatico_deixa_o_aparelho_decidir(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'data-tema="auto"')
        self.assertContains(response, 'media="(prefers-color-scheme: dark)"')

    def test_login_e_troca_de_senha_seguem_o_aparelho(self):
        self.client.logout()
        self.assertContains(self.client.get(reverse('login')), 'data-tema="auto"')

        self.usuario.deve_trocar_senha = True
        self.usuario.tema = Tema.ESCURO
        self.usuario.save()
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse('alterar_senha')), 'data-tema="escuro"')

    def test_configuracoes_mostra_as_tres_opcoes_com_a_atual_marcada(self):
        trocar_tema(self.usuario, Tema.ESCURO)
        response = self.client.get(reverse('configuracoes'))

        self.assertContains(response, 'data-enviar-ao-mudar')
        for valor in ('auto', 'claro', 'escuro'):
            self.assertContains(response, f'name="tema" value="{valor}"')
        self.assertContains(response, 'value="escuro" class="sr-only peer" checked')
        self.assertNotContains(response, 'value="claro" class="sr-only peer" checked')


class TemaContextProcessorTest(SimpleTestCase):

    def test_anonimo_ou_sem_usuario_segue_o_aparelho(self):
        self.assertEqual(tema(SimpleNamespace(user=AnonymousUser())), {'tema': 'auto'})
        self.assertEqual(tema(SimpleNamespace()), {'tema': 'auto'})

    def test_usuario_logado_usa_a_escolha_dele(self):
        usuario = SimpleNamespace(is_authenticated=True, tema='escuro')
        self.assertEqual(tema(SimpleNamespace(user=usuario)), {'tema': 'escuro'})


class CoresDoTemaTest(SimpleTestCase):
    """O modo escuro aparece em dois blocos (escolhido e automático): os dois precisam ter as mesmas cores."""

    def _bloco(self, css, seletor):
        inicio = css.index(seletor)
        return css[css.index('{', inicio) + 1:css.index('}', inicio)].split()

    def test_blocos_do_modo_escuro_sao_iguais(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'input.css').read_text()
        escolhido = self._bloco(css, ':root[data-tema="escuro"]')
        automatico = self._bloco(css, ':root[data-tema="auto"]')
        self.assertEqual(escolhido, automatico)

    def test_modo_escuro_troca_todas_as_cores_do_claro(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'input.css').read_text()
        nomes = lambda bloco: set(re.findall(r'(--[\w-]+):', ' '.join(bloco)))  # noqa: E731
        claro = nomes(self._bloco(css, ':root {'))
        escuro = nomes(self._bloco(css, ':root[data-tema="escuro"]'))
        self.assertEqual(claro, escuro)


class AjudaDaTelaTagTest(SimpleTestCase):

    def _render(self, texto, **contexto):
        return Template("{% load ajuda %}" + texto).render(Context(contexto))

    def _rota(self, nome):
        return SimpleNamespace(resolver_match=SimpleNamespace(url_name=nome) if nome else None)

    def test_escolhe_o_texto_pela_rota(self):
        texto = "{% ajuda_da_tela as a %}[{{ a }}]"
        self.assertEqual(self._render(texto, request=self._rota('extrato_cliente')), '[interfaces/ajuda/caderneta.html]')

    def test_tela_sem_ajuda_ou_sem_rota_fica_vazia(self):
        texto = "{% ajuda_da_tela as a %}[{{ a }}]"
        self.assertEqual(self._render(texto, request=self._rota('login')), '[]')
        self.assertEqual(self._render(texto, request=self._rota(None)), '[]')
        self.assertEqual(self._render(texto), '[]')

    def test_todo_texto_mapeado_existe_e_todo_arquivo_esta_mapeado(self):
        for nome in AJUDA_POR_ROTA.values():
            get_template(f'interfaces/ajuda/{nome}.html')
        arquivos = {arquivo.stem for arquivo in PASTA_DAS_AJUDAS.glob('*.html')}
        self.assertEqual(arquivos, set(AJUDA_POR_ROTA.values()))

    def test_link_de_suporte_diz_a_loja(self):
        loja = SimpleNamespace(nome_loja="Padaria Pão de Mel")
        link = self._render("{% link_suporte %}", request=SimpleNamespace(user=SimpleNamespace(loja=loja)))
        self.assertIn("Padaria%20P%C3%A3o%20de%20Mel", link)
        self.assertIn("Painel%20global", self._render("{% link_suporte %}"))


class AjudaNasTelasTest(ComLojaTestCase):

    def test_cada_tela_principal_tem_o_botao_e_o_texto(self):
        for rota, trecho in [
            ('dashboard', 'Números do topo'),
            ('vendas', 'Como registrar uma venda'),
            ('produtos', 'Cadastrar um produto'),
            ('clientes', 'Novo cliente:'),
            ('relatorios', 'Nesta aba'),
            ('relatorios_vendas', 'Melhores dias e horários:'),
            ('relatorios_produtos', 'Curva ABC:'),
            ('relatorios_clientes', 'Idade das dívidas:'),
            ('relatorios_alteracoes', 'Nada aqui pode ser editado'),
            ('configuracoes', 'Aparência:'),
            ('planos', 'Gerar Pix'),
        ]:
            with self.subTest(rota=rota):
                response = self.client.get(reverse(rota))
                self.assertContains(response, 'data-abrir-dialogo="ajuda-da-tela"')
                self.assertContains(response, '<dialog id="ajuda-da-tela"')
                self.assertContains(response, trecho)
                self.assertContains(response, 'Falar com o suporte')

    def test_filtro_de_periodo_nao_confunde_a_ajuda_da_tela_com_a_dica_das_datas(self):
        response = self.client.get(reverse('relatorios_vendas'))
        self.assertNotContains(response, '>interfaces/ajuda/')
