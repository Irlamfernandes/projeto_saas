from django.core.exceptions import PermissionDenied


def verificar_acesso_loja(user):
    """Garante que o usuário opera sobre uma loja ativa. Superusuário não tem restrição."""
    if user.is_superuser:
        return
    if user.loja is None:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")
    if loja_desativada(user):
        raise PermissionDenied("Acesso negado: esta loja está desativada.")


def filtrar_por_loja(queryset, user, campo='loja'):
    """Restringe o queryset à loja do usuário. Superusuário enxerga todas as lojas.

    `campo` aponta para a loja quando ela vem por relação (ex.: 'venda__loja' em itens de venda).
    """
    if user.is_superuser:
        return queryset
    return queryset.filter(**{campo: user.loja})


def loja_desativada(user):
    """Indica se o usuário pertence a uma loja que foi colocada fora do ar."""
    return user.loja is not None and not user.loja.ativo
