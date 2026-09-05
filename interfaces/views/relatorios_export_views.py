import io
from datetime import datetime, timedelta
from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda
from django.db.models import Sum, Avg
from django.utils import timezone
from infrastructure.utils.relatorios_export import gerar_relatorio_pdf_secao, gerar_relatorio_excel_secao


def _obter_querysets(loja_contexto):
    """Retorna os querysets de vendas, clientes e produtos com base no contexto da loja."""
    if loja_contexto is None:
        return (
            Venda.objects.all(),
            Cliente.objects.all(),
            Produto.objects.all().order_by('quantidade_estoque')
        )
    return (
        Venda.objects.filter(loja=loja_contexto),
        Cliente.objects.filter(loja=loja_contexto),
        Produto.objects.filter(loja=loja_contexto).order_by('quantidade_estoque')
    )


def _filtrar_vendas_por_requisicao(vendas_loja, request):
    """Aplica os filtros de data inicial e final da requisição nas vendas."""
    vendas_filtradas = vendas_loja
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    if data_inicio_str:
        try:
            dt_ini = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            vendas_filtradas = vendas_filtradas.filter(
                data_venda__gte=timezone.make_aware(dt_ini.replace(hour=0, minute=0, second=0))
            )
        except ValueError:
            pass

    if data_fim_str:
        try:
            dt_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
            vendas_filtradas = vendas_filtradas.filter(
                data_venda__lte=timezone.make_aware(dt_fim.replace(hour=23, minute=59, second=59))
            )
        except ValueError:
            pass

    return vendas_filtradas


def _montar_contexto_relatorio(loja_contexto, request=None):
    hoje = timezone.now()
    inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_ano = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    vendas_loja, clientes_todos, produtos_loja = _obter_querysets(loja_contexto)
    vendas_filtradas = _filtrar_vendas_por_requisicao(vendas_loja, request)

    clientes_devendo = [c for c in clientes_todos if c.saldo_geral > 0]
    clientes_credito = [c for c in clientes_todos if c.saldo_geral < 0]

    return {
        'total_geral_vendas': vendas_filtradas.aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_hoje_valor': vendas_loja.filter(data_venda__gte=inicio_hoje).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_semana_valor': vendas_loja.filter(data_venda__gte=inicio_semana).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_mes_valor': vendas_loja.filter(data_venda__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'vendas_ano_valor': vendas_loja.filter(data_venda__gte=inicio_ano).aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
        'ticket_medio': vendas_filtradas.aggregate(Avg('valor_total'))['valor_total__avg'] or 0,
        'estoque_ordenado': produtos_loja,
        'clientes_devendo': clientes_devendo,
        'total_fiado_pendente': sum(c.saldo_geral for c in clientes_devendo),
        'total_credito_clientes': sum(abs(c.saldo_geral) for c in clientes_credito),
    }


@login_required
def exportar_pdf_modular_view(request, tipo):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_contexto = None if request.user.is_superuser else request.user.loja

    tipos_permitidos = {'vendas', 'estoque', 'clientes', 'financeiro', 'geral', 'resumo', 'temporal', 'devendo', 'credito'}
    tipo_limpo = tipo.strip().lower()
    if tipo_limpo not in tipos_permitidos:
        raise Http404("Seção de relatório inválida.")

    dados = _montar_contexto_relatorio(loja_contexto, request)

    buffer = io.BytesIO()
    gerar_relatorio_pdf_secao(tipo_limpo, dados, buffer)
    buffer.seek(0)

    filename = f"relatorio_{tipo_limpo}.pdf"
    return FileResponse(buffer, content_type='application/pdf', as_attachment=True, filename=filename)


@login_required
def exportar_excel_modular_view(request, tipo):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_contexto = None if request.user.is_superuser else request.user.loja

    tipos_permitidos = {'vendas', 'estoque', 'clientes', 'financeiro', 'geral', 'resumo', 'temporal', 'devendo', 'credito'}
    tipo_limpo = tipo.strip().lower()
    if tipo_limpo not in tipos_permitidos:
        raise Http404("Seção de relatório inválida.")

    dados = _montar_contexto_relatorio(loja_contexto, request)

    buffer = io.BytesIO()
    gerar_relatorio_excel_secao(tipo_limpo, dados, buffer)
    buffer.seek(0)

    filename = f"relatorio_{tipo_limpo}.xlsx"
    return FileResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, filename=filename)