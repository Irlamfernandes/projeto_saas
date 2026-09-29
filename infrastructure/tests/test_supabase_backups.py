import io
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import requests
from django.test import override_settings
from infrastructure.utils.supabase_backups import BackupsNoSupabase
from infrastructure.utils.supabase_storage import SupabaseAPIError, SupabaseConfigError

URL = 'https://abc.supabase.co'


def _resposta(status=200, json=None, blocos=(), texto=''):
    return SimpleNamespace(status_code=status, json=lambda: json or {}, iter_content=lambda tamanho: iter(blocos), text=texto)


class Supabase:
    """Grava os pedidos feitos e responde na ordem combinada."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def __call__(self, metodo, url, **opcoes):
        corpo = opcoes['data'].read() if 'data' in opcoes else opcoes.get('json')
        self.pedidos.append((metodo, url.removeprefix(f'{URL}/storage/v1/'), corpo))
        assert opcoes['headers']['Authorization'] == 'Bearer segredo'
        return self.respostas.pop(0)


def _backups():
    return BackupsNoSupabase(URL, 'segredo')


def test_primeira_vez_cria_o_bucket_privado_e_envia(tmp_path):
    arquivo = tmp_path / 'b.enc'
    arquivo.write_bytes(b'cifrado')
    supabase = Supabase(_resposta(404), _resposta(200), _resposta(200))
    with patch('requests.request', supabase):
        _backups().enviar(arquivo, 'backup-1.enc')
    assert supabase.pedidos == [
        ('get', 'bucket/backups', None),
        ('post', 'bucket', {'id': 'backups', 'name': 'backups', 'public': False}),
        ('post', 'object/backups/backup-1.enc', b'cifrado'),
    ]


def test_bucket_ja_existe(tmp_path):
    arquivo = tmp_path / 'b.enc'
    arquivo.write_bytes(b'x')
    supabase = Supabase(_resposta(200, {'public': False}), _resposta(201))
    with patch('requests.request', supabase):
        _backups().enviar(arquivo, 'b.enc')
    assert [pedido[:2] for pedido in supabase.pedidos] == [('get', 'bucket/backups'), ('post', 'object/backups/b.enc')]


def test_recusa_bucket_publico(tmp_path):
    with patch('requests.request', Supabase(_resposta(200, {'public': True}))), \
            pytest.raises(SupabaseAPIError, match="está público"):
        _backups().enviar(tmp_path / 'nao-importa', 'b.enc')


def test_baixa_aos_poucos():
    destino = io.BytesIO()
    with patch('requests.request', Supabase(_resposta(blocos=[b'ab', b'cd']))) as supabase:
        _backups().baixar('b.enc', destino)
    assert destino.getvalue() == b'abcd'
    assert supabase.pedidos == [('get', 'object/backups/b.enc', None)]


def test_remove():
    with patch('requests.request', Supabase(_resposta(200))) as supabase:
        _backups().remover('b.enc')
    assert supabase.pedidos == [('delete', 'object/backups/b.enc', None)]


def test_erros_do_supabase():
    with patch('requests.request', Supabase(_resposta(500, texto='quebrou'))), \
            pytest.raises(SupabaseAPIError, match=r"\(500\): quebrou"):
        _backups().remover('b.enc')
    with patch('requests.request', side_effect=requests.ConnectionError("sem rede")), \
            pytest.raises(SupabaseAPIError, match="sem rede"):
        _backups().remover('b.enc')


def test_sem_credenciais():
    with pytest.raises(SupabaseConfigError):
        BackupsNoSupabase('', '').remover('b.enc')


@override_settings(SUPABASE_URL=f'{URL}/rest/v1/', SUPABASE_KEY='segredo')
def test_usa_as_configuracoes():
    with patch('requests.request', Supabase(_resposta(200))) as supabase:
        BackupsNoSupabase.from_settings().remover('b.enc')
    assert supabase.pedidos[0][1] == 'object/backups/b.enc'
