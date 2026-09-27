from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from infrastructure.admin.registro_de_alteracao_admin import RegistroDeAlteracaoAdmin
from infrastructure.models import RegistroDeAlteracao


class RegistroDeAlteracaoAdminTest(SimpleTestCase):

    def setUp(self):
        self.admin = RegistroDeAlteracaoAdmin(RegistroDeAlteracao, AdminSite())
        self.request = RequestFactory().get('/admin/')

    def test_historico_e_somente_leitura(self):
        self.assertFalse(self.admin.has_add_permission(self.request))
        self.assertFalse(self.admin.has_change_permission(self.request))
        self.assertFalse(self.admin.has_delete_permission(self.request))


class CobrancaAdminTest(SimpleTestCase):

    def test_cobranca_e_somente_leitura(self):
        from infrastructure.admin.assinatura_admin import CobrancaAdmin
        from infrastructure.models import Cobranca
        admin = CobrancaAdmin(Cobranca, AdminSite())
        request = RequestFactory().get('/admin/')
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))
