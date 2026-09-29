from datetime import timedelta
from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.utils import timezone
from application.contas.tentativas import (
    MAXIMO_DE_FALHAS, TEMPO_DE_BLOQUEIO, esquecer_falhas, minutos_bloqueado, registrar_falha,
)
from infrastructure.models import LojaModel, TentativasDeLogin

AGORA = timezone.now()


def errar(usuario, vezes, agora=AGORA):
    for _ in range(vezes):
        registrar_falha(usuario, agora)


class TentativasDeLoginTest(TestCase):
    """5 senhas erradas seguidas: 15 minutos sem entrar."""

    def test_so_bloqueia_na_quinta_falha_seguida(self):
        errar('ana', MAXIMO_DE_FALHAS - 1)
        self.assertEqual(minutos_bloqueado('ana', AGORA), 0)

        errar('ana', 1)
        self.assertEqual(minutos_bloqueado('ana', AGORA), 15)

    def test_minutos_arredondam_para_cima_e_o_bloqueio_acaba(self):
        errar('ana', MAXIMO_DE_FALHAS)
        self.assertEqual(minutos_bloqueado('ana', AGORA + timedelta(minutes=14, seconds=30)), 1)
        self.assertEqual(minutos_bloqueado('ana', AGORA + TEMPO_DE_BLOQUEIO), 0)

    def test_maiusculas_e_espacos_nao_escapam_do_bloqueio(self):
        errar(' Ana ', MAXIMO_DE_FALHAS)
        self.assertEqual(minutos_bloqueado('ANA', AGORA), 15)
        self.assertEqual(minutos_bloqueado('bia', AGORA), 0)

    def test_erros_antigos_nao_se_acumulam(self):
        errar('ana', MAXIMO_DE_FALHAS - 1)
        errar('ana', 1, AGORA + TEMPO_DE_BLOQUEIO + timedelta(seconds=1))
        self.assertEqual(TentativasDeLogin.objects.get(usuario='ana').falhas, 1)

    def test_depois_do_bloqueio_a_contagem_recomeca(self):
        errar('ana', MAXIMO_DE_FALHAS)
        depois = AGORA + TEMPO_DE_BLOQUEIO + timedelta(minutes=1)
        errar('ana', MAXIMO_DE_FALHAS - 1, depois)
        self.assertEqual(minutos_bloqueado('ana', depois), 0)

    def test_acertar_a_senha_esquece_os_erros(self):
        errar('ana', MAXIMO_DE_FALHAS - 1)
        esquecer_falhas('Ana')
        self.assertFalse(TentativasDeLogin.objects.exists())

    def test_nomes_parados_ha_mais_de_um_dia_saem_da_tabela(self):
        errar('inventado', 1, AGORA - timedelta(days=2))
        errar('ana', 1)
        self.assertEqual(list(TentativasDeLogin.objects.values_list('usuario', flat=True)), ['ana'])

    def test_texto_no_admin(self):
        errar('ana', 2)
        self.assertEqual(str(TentativasDeLogin.objects.get()), "ana · 2 erro(s)")


class BackendComBloqueioTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja", ativo=True)
        get_user_model().objects.create_user(username="caixa", password="certa", loja=loja, deve_trocar_senha=False)

    def test_bloqueado_nao_entra_nem_com_a_senha_certa(self):
        for _ in range(MAXIMO_DE_FALHAS):
            self.assertIsNone(authenticate(username="caixa", password="errada"))

        self.assertIsNone(authenticate(username="caixa", password="certa"))
        self.assertEqual(minutos_bloqueado("caixa"), 15)

    def test_senha_certa_zera_os_erros(self):
        authenticate(username="caixa", password="errada")
        self.assertIsNotNone(authenticate(username="caixa", password="certa"))
        self.assertFalse(TentativasDeLogin.objects.exists())

    def test_aceita_o_usuario_pelo_nome_do_campo_e_ignora_sem_usuario(self):
        self.assertIsNotNone(authenticate(**{get_user_model().USERNAME_FIELD: "caixa", 'password': "certa"}))
        self.assertIsNone(authenticate(password="certa"))
        self.assertFalse(TentativasDeLogin.objects.exists())
