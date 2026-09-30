"""Fim do contrato (política de privacidade: 90 dias depois do fim do plano): apaga a loja com tudo o que é dela.

Vendas, clientes, produtos, gastos, usuários e histórico saem do banco; as fotos dos produtos e a marca saem do
Storage. As cópias de segurança criptografadas somem sozinhas na troca pelas mais novas.
"""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from infrastructure.models import ItemCompra, ItemVenda, Perda, ProdutoImagem
from infrastructure.utils.supabase_storage import SupabaseStorage

PRAZO_DEPOIS_DO_PLANO = timedelta(days=90)


def lojas_para_apagar(lojas, hoje=None):
    """As que passaram de 90 dias com o plano vencido."""
    hoje = hoje or timezone.localdate()
    return lojas.filter(vencimento__lt=hoje - PRAZO_DEPOIS_DO_PLANO)


def apagar_loja(loja, storage=None):
    storage = storage or SupabaseStorage.from_settings()
    arquivos = list(ProdutoImagem.objects.filter(produto__loja=loja).values_list('imagem_url', flat=True))
    if loja.logo_url:
        arquivos.append(loja.logo_url)
    with transaction.atomic():
        # Estes protegem o produto contra exclusão avulsa; aqui a loja inteira sai, então vão antes.
        ItemVenda.objects.filter(venda__loja=loja).delete()
        ItemCompra.objects.filter(compra__loja=loja).delete()
        Perda.objects.filter(loja=loja).delete()
        loja.delete()
    for arquivo in arquivos:
        storage.remover(arquivo)  # melhor esforço: uma foto que não sai não desfaz a exclusão
