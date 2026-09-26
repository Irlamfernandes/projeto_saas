from application.tenancy import filtrar_por_loja
from infrastructure.models import Cliente, Produto, Venda


def vendas_do_usuario(user):
    vendas = Venda.objects.select_related('cliente').prefetch_related('itens__produto')
    return filtrar_por_loja(vendas, user).order_by('-data_venda')


def clientes_do_usuario(user):
    return filtrar_por_loja(Cliente.objects.all(), user).order_by('nome')


def produtos_em_estoque_do_usuario(user):
    return filtrar_por_loja(Produto.objects.filter(quantidade_estoque__gt=0), user)


def clientes_da_loja(loja):
    return Cliente.objects.filter(loja=loja).order_by('nome')


def produtos_da_loja(loja):
    return Produto.objects.filter(loja=loja)


def buscar_produto(loja, termo):
    """Resolve o texto digitado no campo de produto, nesta ordem: código interno, nome exato, id."""
    termo = termo.strip()
    if not termo:
        return None

    produtos = produtos_da_loja(loja).order_by('pk')
    return (
        produtos.filter(codigo_interno__iexact=termo).first()
        or produtos.filter(nome__iexact=termo).first()
        or _buscar_por_id(produtos, termo)
    )


def _buscar_por_id(produtos, termo):
    if not termo.isdigit():
        return None
    return produtos.filter(pk=int(termo)).first()
