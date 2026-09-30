"""Quem entra em cada tela: visitante vai para o login, o plano vencido não trava o que precisa funcionar
e as telas só aceitam o método certo (achado pelo teste de mutação)."""
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import URLPattern, reverse
from django.utils import timezone
from config import urls
from infrastructure.models import Cliente, LojaModel
from interfaces.decorators import AVISO_PLANO_VENCIDO

# Rotas abertas a quem não entrou: todas as outras exigem login (a tela nova já nasce conferida).
PUBLICAS = {'login', 'logout', 'termos', 'privacidade', 'backup_agendado'}


def telas_da_loja():
    """Nome e endereço de cada rota com nome (fora o admin), com 1 no lugar de cada parâmetro."""
    for rota in urls.urlpatterns:
        if isinstance(rota, URLPattern) and rota.name and rota.name not in PUBLICAS:
            yield rota.name, reverse(rota.name, kwargs=dict.fromkeys(rota.pattern.converters, 1))


class VisitanteTest(TestCase):

    def test_vai_para_o_login(self):
        telas = dict(telas_da_loja())
        self.assertGreaterEqual(len(telas), 30)
        for rota, endereco in telas.items():
            with self.subTest(rota):
                resposta = self.client.get(endereco)
                if resposta.status_code == 405:  # tela só de envio: o método é conferido antes do login
                    resposta = self.client.post(endereco)
                self.assertEqual((resposta.status_code, resposta['Location']), (302, f"{reverse('login')}?next={endereco}"))


class LojaLogadaTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria")
        usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja, deve_trocar_senha=False)
        self.client.force_login(usuario)

    def mensagens(self, resposta):
        return [str(mensagem) for mensagem in get_messages(resposta.wsgi_request)]


class MetodoCertoTest(LojaLogadaTestCase):

    def test_telas_so_de_leitura_recusam_envio(self):
        for rota, argumentos in (('configuracoes', {}), ('cobranca', {'pk': 1}), ('cobranca_situacao', {'pk': 1})):
            with self.subTest(rota):
                self.assertEqual(self.client.post(reverse(rota, kwargs=argumentos)).status_code, 405)

    def test_excluir_gasto_so_por_envio(self):
        self.assertEqual(self.client.get(reverse('excluir_gasto', kwargs={'tipo': 'despesa', 'pk': 1})).status_code, 405)


class PlanoVencidoNaoTravaTest(LojaLogadaTestCase):
    """Renovar o plano, cuidar da marca e apagar dados de cliente (LGPD) valem mesmo com o plano vencido."""

    def setUp(self):
        super().setUp()
        self.loja.vencimento = timezone.localdate() - timedelta(days=1)
        self.loja.save()

    def test_envios_liberados(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        casos = {
            'planos': ({}, "Escolha um plano."),
            'marca_enviar': ({}, "Escolha a imagem da marca."),
            'marca_remover': ({}, "Marca removida."),
            'cliente_apagar_dados': ({'cliente_id': cliente.pk}, "Digite sua senha para confirmar."),
        }
        for rota, (argumentos, mensagem) in casos.items():
            with self.subTest(rota):
                resposta = self.client.post(reverse(rota, kwargs=argumentos))
                self.assertNotIn(AVISO_PLANO_VENCIDO, self.mensagens(resposta))
                self.assertIn(mensagem, self.mensagens(resposta))


@override_settings(BACKUP_TOKEN='segredo')
class BackupAgendadoTest(TestCase):

    def test_agendador_chama_sem_cookie_de_formulario(self):
        agendador = Client(enforce_csrf_checks=True)
        with patch('interfaces.views.backup_view.pedir_backup', return_value=(True, '')):
            resposta = agendador.post(reverse('backup_agendado'), HTTP_AUTHORIZATION='Bearer segredo')
        self.assertEqual(resposta.status_code, 202)

    def test_sem_cabecalho_o_endereco_nao_existe(self):
        self.assertEqual(self.client.post(reverse('backup_agendado')).status_code, 404)
