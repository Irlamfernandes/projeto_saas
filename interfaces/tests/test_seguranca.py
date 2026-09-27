import re
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from infrastructure.models import LojaModel
from interfaces.seguranca import CABECALHO, PoliticaDeSegurancaMiddleware, origem_do_storage, politica_do_site

User = get_user_model()
PASTAS_DE_TEMPLATES = [Path(settings.BASE_DIR) / 'interfaces' / 'templates' / 'interfaces']
CODIGO_INLINE = re.compile(r'\son[a-z]+=|<script>|javascript:')


def _diretivas(politica):
    return dict(parte.split(' ', 1) for parte in politica.split('; '))


class PoliticaDoSiteTest(SimpleTestCase):

    @override_settings(SUPABASE_URL='https://abc.supabase.co')
    def test_so_roda_script_do_proprio_site(self):
        politica = _diretivas(politica_do_site())
        self.assertEqual(politica['script-src'], "'self'")
        self.assertNotIn('unsafe', politica['script-src'])
        self.assertEqual(politica['frame-ancestors'], "'none'")
        self.assertEqual(politica['object-src'], "'none'")
        self.assertEqual(politica['img-src'], "'self' data: https://abc.supabase.co")

    @override_settings(SUPABASE_URL='https://abc.supabase.co/storage/v1')
    def test_storage_entra_so_pela_origem(self):
        self.assertEqual(origem_do_storage(), 'https://abc.supabase.co')

    @override_settings(SUPABASE_URL='')
    def test_sem_storage_configurado_so_o_proprio_site(self):
        self.assertEqual(origem_do_storage(), '')
        self.assertEqual(_diretivas(politica_do_site())['img-src'], "'self' data:")


class MiddlewareTest(SimpleTestCase):

    def _resposta(self, caminho, resposta=None):
        middleware = PoliticaDeSegurancaMiddleware(lambda request: resposta or HttpResponse())
        return middleware(RequestFactory().get(caminho))

    def test_telas_do_sistema_recebem_a_politica_estrita(self):
        self.assertEqual(_diretivas(self._resposta('/dashboard/')[CABECALHO])['script-src'], "'self'")

    def test_admin_recebe_a_politica_do_unfold(self):
        script = _diretivas(self._resposta('/admin/')[CABECALHO])['script-src']
        self.assertIn("'unsafe-eval'", script)

    def test_nao_sobrescreve_politica_definida_pela_view(self):
        propria = HttpResponse()
        propria[CABECALHO] = "default-src 'none'"
        self.assertEqual(self._resposta('/dashboard/', propria)[CABECALHO], "default-src 'none'")


class TemplatesSemCodigoInlineTest(SimpleTestCase):
    """A política bloqueia onclick, <script> inline e javascript:. Um template com isso quebraria em produção."""

    def test_nenhum_template_do_sistema_tem_codigo_inline(self):
        for pasta in PASTAS_DE_TEMPLATES:
            for arquivo in pasta.rglob('*.html'):
                with self.subTest(arquivo=arquivo.name):
                    self.assertIsNone(CODIGO_INLINE.search(arquivo.read_text()))


class PaginasTest(TestCase):

    def test_pagina_real_sai_com_a_politica_e_sem_fontes_do_google(self):
        response = self.client.get(reverse('login'))
        self.assertIn("script-src 'self'", response[CABECALHO])
        self.assertNotContains(response, 'fonts.googleapis.com')
        self.assertContains(response, 'fonts/figtree-latin.woff2')
        self.assertContains(response, 'js/registrar-sw.js')

    def test_telas_logadas_usam_data_atributos(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        self.client.force_login(User.objects.create_user(username="u", password="x", loja=loja, deve_trocar_senha=False))
        self.assertContains(self.client.get(reverse('dashboard')), 'data-enviar-ao-mudar')
