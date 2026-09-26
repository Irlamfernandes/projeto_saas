import logging
from functools import partial
from django.db import transaction
from application.produtos.exceptions import FalhaNoEnvioDeImagem, ProdutoSemLoja
from infrastructure.models.produto import ProdutoImagem
from infrastructure.utils.supabase_storage import StorageError, SupabaseStorage

logger = logging.getLogger(__name__)


@transaction.atomic
def cadastrar_produto(produto, imagens=(), storage=None):
    """Salva o produto novo e anexa as imagens. Se algum envio falhar, nada é salvo."""
    if produto.loja_id is None:
        raise ProdutoSemLoja()

    produto.save()
    _anexar_imagens(produto, imagens, storage or SupabaseStorage.from_settings())
    return produto


@transaction.atomic
def atualizar_produto(produto, imagens_novas=(), ids_imagens_remover=(), storage=None):
    """Salva as alterações, remove as imagens marcadas e anexa as novas, tudo ou nada."""
    storage = storage or SupabaseStorage.from_settings()
    produto.save()
    _remover_imagens(produto, ids_imagens_remover, storage)
    _anexar_imagens(produto, imagens_novas, storage)
    return produto


def _anexar_imagens(produto, imagens, storage):
    for imagem in imagens:
        ProdutoImagem.objects.create(produto=produto, imagem_url=_enviar(storage, imagem, produto.pk))


def _enviar(storage, imagem, pasta):
    try:
        return storage.enviar(imagem, pasta)
    except StorageError as erro:
        logger.exception("Falha ao enviar imagem do produto %s", pasta)
        raise FalhaNoEnvioDeImagem() from erro


def _remover_imagens(produto, ids, storage):
    imagens = produto.imagens.filter(pk__in=ids)
    for url in imagens.values_list('imagem_url', flat=True):
        # O arquivo só é apagado do storage se a transação for confirmada.
        transaction.on_commit(partial(storage.remover, url))
    imagens.delete()
