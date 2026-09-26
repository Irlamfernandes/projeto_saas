import io
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException
from infrastructure.utils.supabase_storage import (
    SupabaseAPIError, SupabaseConfigError, SupabaseStorage, gerar_nome_unico,
)

BASE = "https://xyz.supabase.co"


def _arquivo(nome="foto.JPG", conteudo=b"bytes"):
    arquivo = io.BytesIO(conteudo)
    arquivo.name = nome
    return arquivo


def _resposta(status, texto=""):
    resposta = MagicMock(status_code=status, text=texto)
    return resposta


class GerarNomeUnicoTest(SimpleTestCase):

    def test_preserva_apenas_a_extensao_em_minusculas(self):
        nome = gerar_nome_unico("Minha Foto Çá.JPG")
        self.assertRegex(nome, r"^[0-9a-f]{32}\.jpg$")

    def test_descarta_extensao_com_caracteres_perigosos(self):
        """Regressão: o nome original ia para a URL e permitia injetar JavaScript no template."""
        self.assertRegex(gerar_nome_unico("x.png');alert(1)"), r"^[0-9a-f]{32}$")

    def test_sem_nome_ou_sem_extensao(self):
        self.assertRegex(gerar_nome_unico(None), r"^[0-9a-f]{32}$")
        self.assertRegex(gerar_nome_unico("arquivo"), r"^[0-9a-f]{32}$")

    def test_nomes_nunca_se_repetem(self):
        self.assertNotEqual(gerar_nome_unico("a.png"), gerar_nome_unico("a.png"))


@patch('infrastructure.utils.supabase_storage.requests')
class EnviarTest(SimpleTestCase):

    def setUp(self):
        self.storage = SupabaseStorage(f"{BASE}/rest/v1/", "chave")

    def test_envia_com_nome_unico_e_retorna_url_publica(self, requests_mock):
        requests_mock.post.return_value = _resposta(200)

        url = self.storage.enviar(_arquivo(), pasta=10)

        chamada = requests_mock.post.call_args
        caminho = chamada.args[0].removeprefix(f"{BASE}/storage/v1/object/imagens/")
        self.assertRegex(caminho, r"^10/[0-9a-f]{32}\.jpg$")
        self.assertEqual(url, f"{BASE}/storage/v1/object/public/imagens/{caminho}")
        self.assertEqual(chamada.kwargs['data'], b"bytes")
        self.assertEqual(chamada.kwargs['timeout'], SupabaseStorage.TIMEOUT_SEGUNDOS)
        headers = chamada.kwargs['headers']
        self.assertEqual(headers['Content-Type'], 'image/jpeg')
        self.assertEqual(headers['Authorization'], 'Bearer chave')
        self.assertNotIn('x-upsert', headers)

    def test_tipo_desconhecido_vira_octet_stream(self, requests_mock):
        requests_mock.post.return_value = _resposta(201)

        self.storage.enviar(_arquivo(nome="sem_extensao"), pasta=1)

        self.assertEqual(requests_mock.post.call_args.kwargs['headers']['Content-Type'], 'application/octet-stream')

    def test_sem_credenciais_nao_envia(self, requests_mock):
        for url, chave in [("", "chave"), (BASE, None)]:
            with self.subTest(url=url, chave=chave), self.assertRaises(SupabaseConfigError):
                SupabaseStorage(url, chave).enviar(_arquivo(), pasta=1)
        requests_mock.post.assert_not_called()

    def test_status_de_erro(self, requests_mock):
        requests_mock.post.return_value = _resposta(400, "Bad Request")

        with self.assertRaisesMessage(SupabaseAPIError, "(400): Bad Request"):
            self.storage.enviar(_arquivo(), pasta=1)

    def test_falha_de_rede(self, requests_mock):
        requests_mock.RequestException = RequestException
        requests_mock.post.side_effect = RequestException("timeout")

        with self.assertRaisesMessage(SupabaseAPIError, "timeout"):
            self.storage.enviar(_arquivo(), pasta=1)


@patch('infrastructure.utils.supabase_storage.requests')
class RemoverTest(SimpleTestCase):
    URL = f"{BASE}/storage/v1/object/public/imagens/10/abc.jpg"

    def setUp(self):
        self.storage = SupabaseStorage(BASE, "chave")

    def test_remove_o_objeto_da_url_publica(self, requests_mock):
        requests_mock.delete.return_value = _resposta(200)

        self.storage.remover(self.URL)

        requests_mock.delete.assert_called_once_with(
            f"{BASE}/storage/v1/object/imagens/10/abc.jpg",
            headers={'apikey': 'chave', 'Authorization': 'Bearer chave'},
            timeout=SupabaseStorage.TIMEOUT_SEGUNDOS,
        )

    def test_ignora_urls_que_nao_sao_do_bucket(self, requests_mock):
        for url in [None, "", "https://outro.site/foto.jpg", f"{BASE}/storage/v1/object/public/imagens/"]:
            with self.subTest(url=url):
                self.storage.remover(url)
        requests_mock.delete.assert_not_called()

    def test_sem_credenciais_nao_tenta_remover(self, requests_mock):
        SupabaseStorage(BASE, "").remover(self.URL)
        requests_mock.delete.assert_not_called()

    def test_falhas_sao_registradas_e_nao_propagadas(self, requests_mock):
        requests_mock.RequestException = RequestException
        casos = {
            'rede': {'side_effect': RequestException("caiu")},
            'status': {'side_effect': None, 'return_value': _resposta(500)},
        }
        for caso, comportamento in casos.items():
            with self.subTest(caso), self.assertLogs('infrastructure.utils.supabase_storage', 'WARNING'):
                requests_mock.delete.configure_mock(**comportamento)
                self.storage.remover(self.URL)


class FromSettingsTest(SimpleTestCase):

    @override_settings(SUPABASE_URL=f"{BASE}/rest/v1", SUPABASE_KEY="chave-settings")
    @patch('infrastructure.utils.supabase_storage.requests')
    def test_usa_credenciais_do_settings(self, requests_mock):
        requests_mock.post.return_value = _resposta(200)

        url = SupabaseStorage.from_settings().enviar(_arquivo(), pasta=1)

        self.assertTrue(url.startswith(f"{BASE}/storage/v1/object/public/imagens/1/"))
        self.assertEqual(requests_mock.post.call_args.kwargs['headers']['apikey'], "chave-settings")
