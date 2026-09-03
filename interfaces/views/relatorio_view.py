from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda, ItemVenda

@login_required
def relatorio_view(request):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        vendas_loja = Venda.objects.all().order_by('-data_venda')
        produtos_loja = Produto.objects.all().order_by('quantidade_estoque')
        clientes_todos = Cliente.objects.all()
    else:
        vendas_loja = Venda.objects.filter(loja=request.user.loja).order_by('-data_venda')
        produtos_loja = Produto.objects.filter(loja=request.user.loja).order_by('quantidade_estoque')
        clientes_todos = Cliente.objects.filter(loja=request.user.loja)

    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    vendas_filtradas = vendas_loja
    if data_inicio_str:
        try:
            data_inicio_dt = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            data_inicio_dt = timezone.make_aware(data_inicio_dt.replace(hour=0, minute=0, second=0))
            vendas_filtradas = vendas_filtradas.filter(data_venda__gte=data_inicio_dt)
        except ValueError:
            pass

    if data_fim_str:
        try:
            data_fim_dt = datetime.strptime(data_fim_str, '%Y-%m-%d')
            data_fim_dt = timezone.make_aware(data_fim_dt.replace(hour=23, minute=59, second=59))
            vendas_filtradas = vendas_filtradas.filter(data_venda__lte=data_fim_dt)
        except ValueError:
            pass

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

    compras_do_dia = vendas_loja.filter(data_venda__gte=inicio_hoje)
    compras_do_mes = vendas_loja.filter(data_venda__gte=inicio_mes)
    ultimas_compras = vendas_filtradas[:10]

    estoque_ordenado = produtos_loja

    clientes_devendo = sorted([c for c in clientes_todos if c.saldo_geral > 0], key=lambda x: x.saldo_geral, reverse=True)
    total_fiado_pendente = sum([c.saldo_geral for c in clientes_devendo])

    clientes_credito = sorted([c for c in clientes_todos if c.saldo_geral < 0], key=lambda x: x.saldo_geral)
    total_credito_clientes = sum([abs(c.saldo_geral) for c in clientes_credito])

    context = {
        'total_geral_vendas': total_geral_vendas,
        'vendas_hoje_valor': vendas_hoje_valor,
        'vendas_semana_valor': vendas_semana_valor,
        'vendas_mes_valor': vendas_mes_valor,
        'vendas_ano_valor': vendas_ano_valor,
        'ticket_medio': ticket_medio,
        'compras_do_dia': compras_do_dia,
        'compras_do_mes': compras_do_mes,
        'ultimas_compras': ultimas_compras,
        'estoque_ordenado': estoque_ordenado,
        'clientes_devendo': clientes_devendo,
        'total_fiado_pendente': total_fiado_pendente,
        'clientes_credito': clientes_credito,
        'total_credito_clientes': total_credito_clientes,
        'data_inicio': data_inicio_str or '',
        'data_fim': data_fim_str or '',
    }
    return render(request, 'interfaces/relatorio.html', context)