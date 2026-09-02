import io
import re
from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import timedelta
from infrastructure.utils.relatorios_export import gerar_relatorio_pdf_secao, gerar_relatorio_excel_secao

def _montar_contexto_relatorio(loja_contexto):
    hoje = timezone.now()
    inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    if loja_contexto is None:
        vendas_loja = Venda.objects.all()
        clientes_todos = Cliente.objects.all()
        produtos_loja = Produto.objects.all().order_by('quantidade_estoque')
    else:
        vendas_loja = Venda.objects.filter(loja=loja_contexto)
        clientes_todos = Cliente.objects.filter(loja=loja_contexto)
        produtos_loja = Produto.objects.filter(loja=loja_contexto).order_by('quantidade_estoque')

    clientes_devendo = [c for c in clientes_todos if c.saldo_geral > 0]
    clientes_credito = [c for c in clientes_todos if c.saldo_geral < 0]

    return {
        'total_geral_vendas': vendas_loja.aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_hoje_valor': vendas_loja.filter(data_venda__gte=inicio_hoje).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_semana_valor': vendas_loja.filter(data_venda__gte=inicio_semana).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_mes_valor': vendas_loja.filter(data_venda__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_ano_valor': vendas_loja.filter(data_venda__gte=inicio_ano).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'ticket_medio': vendas_loja.aggregate(Avg('valor_total'))['valor_total__avg'] or 0,
        'estoque_ordenado': produtos_loja,
        'clientes_devendo': clientes_devendo,
        'total_fiado_pendente': sum([c.saldo_geral for c in clientes_devendo]),
        'total_credito_clientes': sum([abs(c.saldo_geral) for c in clientes_credito]),
    }

@login_required
def exportar_pdf_modular_view(request, tipo):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_contexto = None if request.user.is_superuser else request.user.loja

    tipos_permitidos = {'vendas', 'estoque', 'clientes', 'financeiro', 'geral'}
    tipo_limpo = tipo.strip().lower()
    if tipo_limpo not in tipos_permitidos:
        raise Http404("Seção de relatório inválida.")

    dados = _montar_contexto_relatorio(loja_contexto)

    buffer = io.BytesIO()
    gerar_relatorio_pdf_secao(tipo_limpo, dados, buffer)
    buffer.seek(0)

    filename = f"relatorio_{tipo_limpo}.pdf"
    return FileResponse(
        buffer, 
        content_type='application/pdf', 
        as_attachment=True, 
        filename=filename
    )

@login_required
def exportar_excel_modular_view(request, tipo):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_contexto = None if request.user.is_superuser else request.user.loja

    tipos_permitidos = {'vendas', 'estoque', 'clientes', 'financeiro', 'geral'}
    tipo_limpo = tipo.strip().lower()
    if tipo_limpo not in tipos_permitidos:
        raise Http404("Seção de relatório inválida.")

    dados = _montar_contexto_relatorio(loja_contexto)

    buffer = io.BytesIO()
    gerar_relatorio_excel_secao(tipo_limpo, dados, buffer)
    buffer.seek(0)

    filename = f"relatorio_{tipo_limpo}.xlsx"
    return FileResponse(
        buffer, 
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
        as_attachment=True, 
        filename=filename
    )