from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse

URL = '/interno/backup/'


@override_settings(BACKUP_TOKEN='token-do-agendador')
class BackupAgendadoViewTest(TestCase):

    def _chamar(self, token='token-do-agendador', **extras):
        return self.client.post(URL, HTTP_AUTHORIZATION=f'Bearer {token}', **extras)

    def test_endereco(self):
        self.assertEqual(reverse('backup_agendado'), URL)

    def test_token_certo_pede_o_backup_agendado(self):
        with patch('interfaces.views.backup_view.pedir_backup', return_value=(True, "Backup iniciado.")) as pedir:
            resposta = self._chamar()
        pedir.assert_called_once_with('agendado')
        self.assertEqual(resposta.status_code, 202)
        self.assertEqual(resposta.json(), {'iniciado': True, 'motivo': "Backup iniciado."})

    def test_fora_da_hora_responde_sem_fazer(self):
        with patch('interfaces.views.backup_view.pedir_backup', return_value=(False, "Backup automático desligado.")):
            resposta = self._chamar()
        self.assertEqual((resposta.status_code, resposta.json()['iniciado']), (200, False))

    def test_token_errado_ou_ausente_parece_que_nem_existe(self):
        with patch('interfaces.views.backup_view.pedir_backup') as pedir:
            self.assertEqual(self._chamar('outro').status_code, 404)
            self.assertEqual(self.client.post(URL).status_code, 404)
        pedir.assert_not_called()

    def test_so_aceita_post(self):
        self.assertEqual(self.client.get(URL, HTTP_AUTHORIZATION='Bearer token-do-agendador').status_code, 405)

    @override_settings(BACKUP_TOKEN='')
    def test_sem_token_configurado_fica_desligado(self):
        self.assertEqual(self._chamar('').status_code, 404)
