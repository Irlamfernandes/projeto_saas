from django.core.exceptions import PermissionDenied


def verificar_acesso_loja(user):
    """Garante que o usuário opera sobre uma loja ativa. Superusuário não tem restrição."""
    if user.is_superuser:
        return
    if user.loja is None:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")
    if not user.loja.ativo:
        raise PermissionDenied("Acesso negado: esta loja está desativada.")


def filtrar_por_loja(queryset, user):
    """Restringe o queryset à loja do usuário. Superusuário enxerga todas as lojas."""
    if user.is_superuser:
        return queryset
    return queryset.filter(loja=user.loja)
