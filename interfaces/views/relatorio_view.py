from django.shortcuts import render
from interfaces.decorators import loja_required
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda

TEMPLATE_RELATORIO = 'interfaces/relatorio.html'


def _obter_dados_base_loja(user):
    """Retorna os querysets filtrados com base nas permissões da loja ou superuser."""
    if user.is_superuser:
        return (
            Venda.objects.all().order_by('-data_venda'),
            Produto.objects.all().order_by('quantidade_estoque'),
            Cliente.objects.all()
        )
    return (
        Venda.objects.filter(loja=user.loja).order_by('-data_venda'),
        Produto.objects.filter(loja=user.loja).order_by('quantidade_estoque'),
        Cliente.objects.filter(loja=user.loja)
    )


def _filtrar_vendas_por_data(vendas_qs, request):
    """Aplica filtros de data inicial e final nas vendas."""
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    vendas_filtradas = vendas_qs

    if data_inicio_str:
        try:
            dt_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            dt_inicio = timezone.make_aware(dt_inicio.replace(hour=0, minute=0, second=0))
            vendas_filtradas = vendas_filtradas.filter(data_venda__gte=dt_inicio)
        except ValueError:
            pass

    if data_fim_str:
        try:
            dt_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
            dt_fim = timezone.make_aware(dt_fim.replace(hour=23, minute=59, second=59))
            vendas_filtradas = vendas_filtradas.filter(data_venda__lte=dt_fim)
        except ValueError:
            pass

    return vendas_filtradas, data_inicio_str, data_fim_str


def _processar_clientes_saldos(clientes_qs):
    """Calcula clientes devendo e com crédito pendente."""
    clientes_devendo = sorted([c for c in clientes_qs if c.saldo_geral > 0], key=lambda x: x.saldo_geral, reverse=True)
    total_fiado_pendente = sum(c.saldo_geral for c in clientes_devendo)

    clientes_credito = sorted([c for c in clientes_qs if c.saldo_geral < 0], key=lambda x: x.saldo_geral)
    total_credito_clientes = sum(abs(c.saldo_geral) for c in clientes_credito)

    return clientes_devendo, total_fiado_pendente, clientes_credito, total_credito_clientes


@loja_required
def relatorio_view(request):
    vendas_loja, produtos_loja, clientes_todos = _obter_dados_base_loja(request.user)
    vendas_filtradas, data_inicio_str, data_fim_str = _filtrar_vendas_por_data(vendas_loja, request)

    hoje = timezone.now()
    inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    total_geral_vendas = vendas_filtradas.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    ticket_medio = vendas_filtradas.aggregate(Avg('valor_total'))['valor_total__avg'] or 0

    vendas_hoje_valor = vendas_loja.filter(data_venda__gte=inicio_hoje).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_semana_valor = vendas_loja.filter(data_venda__gte=inicio_semana).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_mes_valor = vendas_loja.filter(data_venda__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_ano_valor = vendas_loja.filter(data_venda__gte=inicio_ano).aggregate(Sum('valor_total'))['valor_total__sum'] or 0

    clientes_devendo, total_fiado_pendente, clientes_credito, total_credito_clientes = _processar_clientes_saldos(clientes_todos)

    context = {
        'total_geral_vendas': total_geral_vendas,
        'vendas_hoje_valor': vendas_hoje_valor,
        'vendas_semana_valor': vendas_semana_valor,
        'vendas_mes_valor': vendas_mes_valor,
        'vendas_ano_valor': vendas_ano_valor,
        'ticket_medio': ticket_medio,
        'compras_do_dia': vendas_loja.filter(data_venda__gte=inicio_hoje),
        'compras_do_mes': vendas_loja.filter(data_venda__gte=inicio_mes),
        'ultimas_compras': vendas_filtradas[:10],
        'estoque_ordenado': produtos_loja,
        'clientes_devendo': clientes_devendo,
        'total_fiado_pendente': total_fiado_pendente,
        'clientes_credito': clientes_credito,
        'total_credito_clientes': total_credito_clientes,
        'data_inicio': data_inicio_str or '',
        'data_fim': data_fim_str or '',
    }
    return render(request, TEMPLATE_RELATORIO, context)