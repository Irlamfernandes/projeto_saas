"""Marca (logotipo) da loja: usada no topo do sistema e nos PDFs."""
import logging
from functools import partial
from django.db import transaction
from application.auditoria.services import registrar_alteracao
from application.lojas.exceptions import FalhaNoEnvioDaMarca, MarcaInvalida, UsuarioSemLoja
from infrastructure.models import Acao
from infrastructure.utils.otimizacao_de_imagem import ImagemIlegivel, otimizar_imagem
from infrastructure.utils.supabase_storage import StorageError, SupabaseStorage

logger = logging.getLogger(__name__)

# A marca aparece pequena (topo e cabeçalho do PDF): 512 px sobra e deixa o arquivo com poucos KB.
LADO_MAXIMO_DA_MARCA = 512
PASTA_DAS_MARCAS = 'lojas'


@transaction.atomic
def trocar_marca(loja, arquivo, *, usuario, storage=None):
    """Envia a nova marca já otimizada e apaga a antiga do storage depois de salvar."""
    _exigir_loja(loja)
    storage = storage or SupabaseStorage.from_settings()
    try:
        otimizada = otimizar_imagem(arquivo, lado_maximo=LADO_MAXIMO_DA_MARCA)
    except ImagemIlegivel as erro:
        raise MarcaInvalida() from erro
    try:
        nova_url = storage.enviar(otimizada, PASTA_DAS_MARCAS)
    except StorageError as erro:
        logger.exception("Falha ao enviar a marca da loja %s", loja.pk)
        raise FalhaNoEnvioDaMarca() from erro

    _substituir(loja, nova_url, storage)
    _registrar(loja, usuario, "Nova marca enviada")
    return loja


@transaction.atomic
def remover_marca(loja, *, usuario, storage=None):
    _exigir_loja(loja)
    if not loja.logo_url:
        return loja
    _substituir(loja, '', storage or SupabaseStorage.from_settings())
    _registrar(loja, usuario, "Marca removida")
    return loja


def _exigir_loja(loja):
    if loja is None:
        raise UsuarioSemLoja()


def _substituir(loja, nova_url, storage):
    antiga = loja.logo_url
    loja.logo_url = nova_url
    loja.save(update_fields=['logo_url'])
    if antiga:
        # O arquivo antigo só sai do storage se a troca for confirmada no banco.
        transaction.on_commit(partial(storage.remover, antiga))


def _registrar(loja, usuario, descricao):
    registrar_alteracao(loja=loja, usuario=usuario, acao=Acao.MARCA_ALTERADA, descricao=descricao)
