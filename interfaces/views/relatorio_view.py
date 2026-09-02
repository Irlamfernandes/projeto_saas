from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda, ItemVenda

@login_required
def relatorio_view(request):
    loja = request.user.loja
    hoje = timezone.now()
    
    # Períodos de tempo
    inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    vendas_loja = Venda.objects.filter(loja=loja).order_by('-data_venda')

    # Faturamento e Indicadores
    total_geral_vendas = vendas_loja.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_hoje_valor = vendas_loja.filter(data_venda__gte=inicio_hoje).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_semana_valor = vendas_loja.filter(data_venda__gte=inicio_semana).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_mes_valor = vendas_loja.filter(data_venda__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    vendas_ano_valor = vendas_loja.filter(data_venda__gte=inicio_ano).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    ticket_medio = vendas_loja.aggregate(Avg('valor_total'))['valor_total__avg'] or 0

    # Listas de Vendas por Período
    compras_do_dia = vendas_loja.filter(data_venda__gte=inicio_hoje)
    compras_do_mes = vendas_loja.filter(data_venda__gte=inicio_mes)
    ultimas_compras = vendas_loja[:10] # Últimas 10 compras gerais

    # Estoque Completo ordenado do menor para o maior
    estoque_ordenado = Produto.objects.filter(loja=loja).order_by('quantidade_estoque')

    # Clientes Endividados (Devendo) ordenados pelo maior valor de dívida
    clientes_todos = Cliente.objects.filter(loja=loja)
    clientes_devendo = sorted([c for c in clientes_todos if c.saldo_geral > 0], key=lambda x: x.saldo_geral, reverse=True)
    total_fiado_pendente = sum([c.saldo_geral for c in clientes_devendo])

    # Clientes com Crédito (Dinheiro em caixa/antecipado) ordenados pelo maior valor de crédito
    clientes_credito = sorted([c for c in clientes_todos if c.saldo_geral < 0], key=lambda x: x.saldo_geral) # do mais negativo (maior crédito) para cima
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
    }
    return render(request, 'interfaces/relatorio.html', context)