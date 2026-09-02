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
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    inicio_quinzena = hoje - timedelta(days=15)
    inicio_bimestre = hoje - timedelta(days=60)
    inicio_trimestre = hoje - timedelta(days=90)
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
    }
    return render(request, 'interfaces/dashboard.html', context)