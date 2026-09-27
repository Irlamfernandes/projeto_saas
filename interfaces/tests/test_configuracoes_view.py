from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from infrastructure.models import LojaModel, RegistroDeAlteracao
from tests.apoio import URL_PUBLICA, StorageFalso, imagem_de_teste

User = get_user_model()
LOGO = f"{URL_PUBLICA}/lojas/logo.webp"


class ConfiguracoesTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria Pão de Mel")
        self.usuario = User.objects.create_user(username="Caixa 1", password="x", loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(self.usuario)
        self.storage = StorageFalso()
        fabrica = patch('application.lojas.services.SupabaseStorage.from_settings', return_value=self.storage)
        fabrica.start()
        self.addCleanup(fabrica.stop)

    def mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class TelaDeConfiguracoesTest(ConfiguracoesTestCase):

    def test_mostra_usuario_e_loja_travados_sem_campos_editaveis(self):
        response = self.client.get(reverse('configuracoes'))

        self.assertContains(response, "Caixa 1")
        self.assertContains(response, "Padaria Pão de Mel")
        self.assertNotContains(response, 'name="username"')
        self.assertNotContains(response, 'name="nome_loja"')
        self.assertContains(response, "Aparece no topo do sistema e nos PDFs")

    def test_sem_marca_mostra_as_iniciais_e_nao_oferece_remover(self):
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, ">PP</span>")
        self.assertNotContains(response, "Remover marca")

    def test_com_marca_mostra_a_imagem_no_topo_e_oferece_remover(self):
        self.loja.logo_url = LOGO
        self.loja.save()

        response = self.client.get(reverse('configuracoes'))

        self.assertContains(response, f'src="{LOGO}"', count=3)  # menu lateral, topo do celular e a prévia
        # Se a imagem não carregar, as iniciais (escondidas) assumem o lugar
        self.assertContains(response, "onerror=", count=3)
        self.assertContains(response, 'class="hidden grid place-items-center', count=3)
        self.assertContains(response, "Remover marca")

    def test_menu_leva_para_configuracoes_no_celular_e_no_computador(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, f'href="{reverse("configuracoes")}"', count=2)

    def test_superusuario_sem_loja_nao_ve_a_marca(self):
        admin = User.objects.create_superuser(username="admin", password="x", deve_trocar_senha=False)
        self.client.force_login(admin)
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, "Painel global")
        self.assertNotContains(response, "Marca da loja")

    def test_exige_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse('configuracoes')), f"{reverse('login')}?next={reverse('configuracoes')}")


class EnviarMarcaTest(ConfiguracoesTestCase):

    def test_qualquer_usuario_da_loja_troca_a_marca(self):
        response = self.client.post(reverse('marca_enviar'), {'marca': imagem_de_teste('logo.png')})

        self.assertRedirects(response, reverse('configuracoes'))
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.logo_url, LOGO)
        self.assertEqual(self.mensagens(response), ["Marca atualizada! Ela já aparece no topo e nos PDFs."])
        self.assertEqual(RegistroDeAlteracao.objects.get().usuario, self.usuario)

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        casos = {
            'sem arquivo': {},
            'extensão': {'marca': SimpleUploadedFile('logo.gif', imagem_de_teste().read())},
            'conteúdo': {'marca': SimpleUploadedFile('logo.png', b'texto')},
        }
        for caso, dados in casos.items():
            with self.subTest(caso):
                response = self.client.post(reverse('marca_enviar'), dados)
                self.assertRedirects(response, reverse('configuracoes'))
                self.assertEqual(len(self.mensagens(response)), 1)
        self.assertEqual(self.storage.enviados, [])

    def test_so_aceita_post(self):
        self.assertEqual(self.client.get(reverse('marca_enviar')).status_code, 405)


class RemoverMarcaTest(ConfiguracoesTestCase):

    def test_remove_a_marca(self):
        self.loja.logo_url = LOGO
        self.loja.save()

        response = self.client.post(reverse('marca_remover'))

        self.loja.refresh_from_db()
        self.assertEqual(self.loja.logo_url, '')
        self.assertEqual(self.mensagens(response), ["Marca removida."])

    def test_superusuario_sem_loja_recebe_aviso(self):
        admin = User.objects.create_superuser(username="admin", password="x", deve_trocar_senha=False)
        self.client.force_login(admin)
        response = self.client.post(reverse('marca_remover'))
        self.assertEqual(self.mensagens(response), ["Este usuário não está ligado a nenhuma loja."])

    def test_so_aceita_post(self):
        self.assertEqual(self.client.get(reverse('marca_remover')).status_code, 405)
