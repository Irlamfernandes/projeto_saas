from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from infrastructure.models import Produto, Cliente, Venda

@login_required
def dashboard_view(request):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        vendas_loja = Venda.objects.all()
        produtos_loja = Produto.objects.all()
        clientes_loja = Cliente.objects.all()
    else:
        vendas_loja = Venda.objects.filter(loja=request.user.loja)
        produtos_loja = Produto.objects.filter(loja=request.user.loja)
        clientes_loja = Cliente.objects.filter(loja=request.user.loja)

    hoje = timezone.now()
    inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    
    inicio_semana = inicio_hoje - timedelta(days=6)
    inicio_quinzena = inicio_hoje - timedelta(days=14)
    inicio_bimestre = inicio_hoje - timedelta(days=59)
    inicio_trimestre = inicio_hoje - timedelta(days=89)

    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    total_geral = vendas_loja.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_hoje = vendas_loja.filter(data_venda__gte=inicio_hoje).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_semana = vendas_loja.filter(data_venda__gte=inicio_semana).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_quinzena = vendas_loja.filter(data_venda__gte=inicio_quinzena).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_mes = vendas_loja.filter(data_venda__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_bimestre = vendas_loja.filter(data_venda__gte=inicio_bimestre).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_trimestre = vendas_loja.filter(data_venda__gte=inicio_trimestre).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_ano = vendas_loja.filter(data_venda__gte=inicio_ano).aggregate(Sum('valor_total'))['valor_total__sum'] or 0

    total_produtos = produtos_loja.count()
    total_clientes = clientes_loja.count()

    try:
        limite_estoque = int(request.GET.get('limite_estoque', 5))
    except (ValueError, TypeError):
        limite_estoque = 5

    produtos_baixo_estoque = produtos_loja.filter(quantidade_estoque__lte=limite_estoque).order_by('quantidade_estoque')

    context = {
        'total_produtos': total_produtos,
        'total_clientes': total_clientes,
        'total_geral': total_geral,
        'vendas_hoje': vendas_hoje,
        'vendas_semana': vendas_semana,
        'vendas_quinzena': vendas_quinzena,
        'vendas_mes': vendas_mes,
        'vendas_bimestre': vendas_bimestre,
        'vendas_trimestre': vendas_trimestre,
        'vendas_ano': vendas_ano,
        'produtos_baixo_estoque': produtos_baixo_estoque,
        'limite_estoque': limite_estoque,
    }
    return render(request, 'interfaces/dashboard.html', context)