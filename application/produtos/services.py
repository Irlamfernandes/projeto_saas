import logging
from functools import partial
from django.db import transaction
from application.auditoria.services import diferencas, fotografar, registrar_alteracao
from application.produtos.exceptions import FalhaNoEnvioDeImagem, ImagemInvalida, LimiteDeFotosExcedido, ProdutoSemLoja
from application.produtos.selectors import MAXIMO_DE_FOTOS
from infrastructure.models import Acao, Produto
from infrastructure.models.produto import ProdutoImagem
from infrastructure.utils.otimizacao_de_imagem import ImagemIlegivel, otimizar_imagem
from infrastructure.utils.supabase_storage import StorageError, SupabaseStorage

logger = logging.getLogger(__name__)

CAMPOS_DO_PRODUTO = (
    'nome', 'codigo_interno', 'categoria', 'preco_custo', 'preco_venda', 'unidade', 'controla_estoque', 'quantidade_estoque',
    'descricao', 'opcoes',
)


@transaction.atomic
def cadastrar_produto(produto, imagens=(), storage=None, usuario=None):
    """Salva o produto novo e anexa as imagens. Se algum envio falhar, nada é salvo."""
    if produto.loja_id is None:
        raise ProdutoSemLoja()
    _exigir_limite_de_fotos(ja_tem=0, novas=len(imagens))

    produto.save()
    _anexar_imagens(produto, imagens, storage or SupabaseStorage.from_settings())
    registrar_alteracao(
        loja=produto.loja, usuario=usuario, acao=Acao.PRODUTO_CADASTRADO, descricao=produto.nome,
        detalhes={'produto': fotografar(produto, CAMPOS_DO_PRODUTO), 'fotos': len(imagens)},
    )
    return produto


@transaction.atomic
def atualizar_produto(produto, imagens_novas=(), ids_imagens_remover=(), storage=None, usuario=None):
    """Salva as alterações, remove as imagens marcadas e anexa as novas, tudo ou nada."""
    mantidas = produto.imagens.exclude(pk__in=ids_imagens_remover).count()
    _exigir_limite_de_fotos(ja_tem=mantidas, novas=len(imagens_novas))
    storage = storage or SupabaseStorage.from_settings()
    antes = fotografar(Produto.objects.get(pk=produto.pk), CAMPOS_DO_PRODUTO)
    produto.save()
    removidas = _remover_imagens(produto, ids_imagens_remover, storage)
    _anexar_imagens(produto, imagens_novas, storage)
    _registrar_edicao(produto, usuario, diferencas(antes, fotografar(produto, CAMPOS_DO_PRODUTO)),
                      fotos_novas=len(imagens_novas), fotos_removidas=removidas)
    return produto


def _registrar_edicao(produto, usuario, alteracoes, *, fotos_novas, fotos_removidas):
    detalhes = {'alteracoes': alteracoes}
    if fotos_novas or fotos_removidas:
        detalhes['fotos'] = {'adicionadas': fotos_novas, 'removidas': fotos_removidas}
    if alteracoes or fotos_novas or fotos_removidas:
        registrar_alteracao(
            loja=produto.loja, usuario=usuario, acao=Acao.PRODUTO_EDITADO, descricao=produto.nome, detalhes=detalhes,
        )


def _exigir_limite_de_fotos(ja_tem, novas):
    """Checado antes de qualquer envio: nada sobe para o storage se passar do limite."""
    if ja_tem + novas > MAXIMO_DE_FOTOS:
        raise LimiteDeFotosExcedido(MAXIMO_DE_FOTOS, max(0, MAXIMO_DE_FOTOS - ja_tem))


def _anexar_imagens(produto, imagens, storage):
    enviadas = []
    try:
        for imagem in imagens:
            enviadas.append(_enviar(storage, imagem, produto.pk))
            ProdutoImagem.objects.create(produto=produto, imagem_url=enviadas[-1])
    except Exception:
        # O banco vai desfazer os registros; os arquivos já enviados precisam ser apagados à mão.
        for url in enviadas:
            storage.remover(url)
        raise


def _enviar(storage, imagem, pasta):
    """Otimiza a foto (menor e em WebP) antes de mandar para o storage."""
    try:
        otimizada = otimizar_imagem(imagem)
    except ImagemIlegivel as erro:
        raise ImagemInvalida(imagem.name) from erro

    try:
        return storage.enviar(otimizada, pasta)
    except StorageError as erro:
        logger.exception("Falha ao enviar imagem do produto %s", pasta)
        raise FalhaNoEnvioDeImagem() from erro


def _remover_imagens(produto, ids, storage):
    imagens = produto.imagens.filter(pk__in=ids)
    for url in imagens.values_list('imagem_url', flat=True):
        # O arquivo só é apagado do storage se a transação for confirmada.
        transaction.on_commit(partial(storage.remover, url))
    removidas, _ = imagens.delete()
    return removidas
