import gzip
import io
from unittest.mock import patch
import pytest
from infrastructure.utils import backup_cripto
from infrastructure.utils.backup_cripto import CABECALHO, ChaveDeBackupInvalida, criptografar, descriptografar

DADOS = b'[{"model": "infrastructure.lojamodel", "fields": {"nome_loja": "Padaria"}}]' * 50


def _cifrado(tmp_path, dados=DADOS, senha='senha-forte'):
    caminho = tmp_path / 'backup.enc'
    with open(caminho, 'wb') as saida:
        criptografar(io.BytesIO(dados), saida, senha)
    return caminho


def _aberto(caminho, senha='senha-forte'):
    saida = io.BytesIO()
    descriptografar(caminho, saida, senha)
    return saida.getvalue()


def test_ida_e_volta(tmp_path):
    caminho = _cifrado(tmp_path)
    conteudo = caminho.read_bytes()
    assert conteudo.startswith(CABECALHO)
    assert b'Padaria' not in conteudo  # nada legível no arquivo guardado
    assert len(conteudo) < len(DADOS)  # e compactado
    assert _aberto(caminho) == DADOS


def test_arquivo_grande_passa_em_varios_blocos(tmp_path):
    with patch.object(backup_cripto, 'BLOCO', 7):
        assert _aberto(_cifrado(tmp_path)) == DADOS


def test_cada_arquivo_usa_sal_e_nonce_novos(tmp_path):
    um = _cifrado(tmp_path).read_bytes()
    outro = _cifrado(tmp_path).read_bytes()
    assert um != outro


def test_dentro_e_um_gzip_comum(tmp_path):
    """Com a senha, o conteúdo decifrado (antes de descompactar) é um .json.gz que qualquer programa abre."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    conteudo = _cifrado(tmp_path).read_bytes()
    sal = conteudo[len(CABECALHO):len(CABECALHO) + 16]
    nonce = conteudo[len(CABECALHO) + 16:len(CABECALHO) + 28]
    decifrador = Cipher(algorithms.AES(backup_cripto._chave('senha-forte', sal)), modes.GCM(nonce, conteudo[-16:])).decryptor()
    decifrador.authenticate_additional_data(conteudo[:len(CABECALHO) + 28])
    compactado = decifrador.update(conteudo[len(CABECALHO) + 28:-16]) + decifrador.finalize()
    assert gzip.decompress(compactado) == DADOS


def test_senha_errada(tmp_path):
    with pytest.raises(ChaveDeBackupInvalida, match="Senha errada"):
        _aberto(_cifrado(tmp_path), senha='outra')


@pytest.mark.parametrize('posicao', [3, 20, 60, -5])  # cabeçalho, sal, dados, tag
def test_qualquer_byte_alterado_e_recusado(tmp_path, posicao):
    caminho = _cifrado(tmp_path)
    conteudo = bytearray(caminho.read_bytes())
    conteudo[posicao] ^= 1
    caminho.write_bytes(bytes(conteudo))
    with pytest.raises(ChaveDeBackupInvalida):
        _aberto(caminho)


def test_arquivo_que_nao_e_backup(tmp_path):
    curto = tmp_path / 'curto'
    curto.write_bytes(CABECALHO)
    outro = tmp_path / 'outro'
    outro.write_bytes(b'x' * 200)
    for caminho in (curto, outro):
        with pytest.raises(ChaveDeBackupInvalida, match="não é um backup"):
            _aberto(caminho)


def test_sem_senha_configurada(tmp_path):
    with pytest.raises(ChaveDeBackupInvalida, match="BACKUP_CHAVE"):
        _cifrado(tmp_path, senha='')
