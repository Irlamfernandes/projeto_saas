from types import SimpleNamespace
from django.template import Context, Template
from django.test import SimpleTestCase
from interfaces.templatetags.navegacao import iniciais


class MenuAtivoTest(SimpleTestCase):

    def _render(self, rota):
        request = SimpleNamespace(resolver_match=SimpleNamespace(url_name=rota) if rota else None)
        template = Template("{% load navegacao %}[{% menu_ativo 'vendas' 'venda_editar' %}]")
        return template.render(Context({'request': request}))

    def test_marca_a_rota_e_suas_subpaginas(self):
        self.assertEqual(self._render('vendas'), '[page]')
        self.assertEqual(self._render('venda_editar'), '[page]')

    def test_aceita_rotas_separadas_por_espaco(self):
        request = SimpleNamespace(resolver_match=SimpleNamespace(url_name='venda_editar'))
        template = Template("{% load navegacao %}[{% menu_ativo rotas %}]")
        self.assertEqual(template.render(Context({'request': request, 'rotas': 'vendas venda_editar'})), '[page]')

    def test_outras_rotas_e_sem_rota(self):
        self.assertEqual(self._render('produtos'), '[]')
        self.assertEqual(self._render(None), '[]')
        self.assertEqual(Template("{% load navegacao %}[{% menu_ativo 'x' %}]").render(Context({})), '[]')


class IniciaisTest(SimpleTestCase):

    def test_iniciais(self):
        self.assertEqual(iniciais("Padaria Pão de Mel"), "PP")
        self.assertEqual(iniciais("loja"), "L")
        self.assertEqual(iniciais("  - Mercadinho  "), "M")
        self.assertEqual(iniciais(""), "?")
        self.assertEqual(iniciais(None), "?")
