"""Compacta e criptografa o arquivo de backup — e o caminho de volta — sem carregar tudo na memória.

Formato: CABECALHO (7 bytes) + sal (16) + nonce (12) + dados (gzip, cifrados com AES-256-GCM) + tag (16).
A chave vem de BACKUP_CHAVE via scrypt, com um sal novo a cada arquivo. O cabeçalho entra na autenticação:
qualquer byte alterado, no cabeçalho ou nos dados, faz a leitura falhar em vez de devolver lixo.
"""
import os
import zlib
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

CABECALHO = b'GLBKP01'
TAMANHO_SAL = 16
TAMANHO_NONCE = 12
TAMANHO_TAG = 16
BLOCO = 1024 * 1024
GZIP = 31  # zlib com cabeçalho gzip: o arquivo aberto também é um .json.gz comum


class ChaveDeBackupInvalida(Exception):
    """Senha errada, arquivo corrompido ou que não é um backup deste sistema."""


def _chave(senha, sal):
    if not senha:
        raise ChaveDeBackupInvalida("Defina BACKUP_CHAVE no ambiente.")
    return Scrypt(salt=sal, length=32, n=2 ** 15, r=8, p=1).derive(senha.encode())


def criptografar(entrada, saida, senha):
    """Lê `entrada` (arquivo aberto em binário) e escreve em `saida` compactado e criptografado."""
    sal, nonce = os.urandom(TAMANHO_SAL), os.urandom(TAMANHO_NONCE)
    inicio = CABECALHO + sal + nonce
    cifrador = Cipher(algorithms.AES(_chave(senha, sal)), modes.GCM(nonce)).encryptor()
    cifrador.authenticate_additional_data(inicio)
    compactador = zlib.compressobj(9, zlib.DEFLATED, GZIP)
    saida.write(inicio)
    while bloco := entrada.read(BLOCO):
        saida.write(cifrador.update(compactador.compress(bloco)))
    saida.write(cifrador.update(compactador.flush()))
    saida.write(cifrador.finalize())
    saida.write(cifrador.tag)


def descriptografar(caminho, saida, senha):
    """Lê o arquivo em `caminho` e escreve em `saida` os dados originais (já descompactados)."""
    tamanho = os.path.getsize(caminho)
    minimo = len(CABECALHO) + TAMANHO_SAL + TAMANHO_NONCE + TAMANHO_TAG
    with open(caminho, 'rb') as arquivo:
        inicio = arquivo.read(len(CABECALHO) + TAMANHO_SAL + TAMANHO_NONCE)
        if tamanho < minimo or not inicio.startswith(CABECALHO):
            raise ChaveDeBackupInvalida("Este arquivo não é um backup do sistema.")
        sal, nonce = inicio[len(CABECALHO):-TAMANHO_NONCE], inicio[-TAMANHO_NONCE:]
        arquivo.seek(-TAMANHO_TAG, os.SEEK_END)
        tag = arquivo.read(TAMANHO_TAG)
        arquivo.seek(len(inicio))
        decifrador = Cipher(algorithms.AES(_chave(senha, sal)), modes.GCM(nonce, tag)).decryptor()
        decifrador.authenticate_additional_data(inicio)
        descompactador = zlib.decompressobj(GZIP)
        restante = tamanho - len(inicio) - TAMANHO_TAG
        # Só depois do finalize os dados são dados como autênticos: quem chama descarta `saida` se der erro.
        try:
            while restante > 0:
                bloco = arquivo.read(min(BLOCO, restante))
                restante -= len(bloco)
                saida.write(descompactador.decompress(decifrador.update(bloco)))
            decifrador.finalize()
        except (InvalidTag, zlib.error):
            raise ChaveDeBackupInvalida("Senha errada ou arquivo alterado/corrompido.") from None
        saida.write(descompactador.flush())
