from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from application.a_receber.selectors import cobranca_do_cliente
from application.a_receber.services import registrar_lembrete
from application.clientes.selectors import clientes_do_usuario
from application.relatorios.periodos import hoje_local
from interfaces.decorators import loja_required


@loja_required
@require_POST
def lembrete_view(request, cliente_id):
    """Chamado pela tela quando o dono toca em "Cobrar": anota o lembrete com o valor que estava vencendo."""
    cliente = get_object_or_404(clientes_do_usuario(request.user).select_related('loja'), pk=cliente_id)
    cobranca = cobranca_do_cliente(cliente, hoje_local())
    if cobranca:
        registrar_lembrete(cliente, valor=cobranca.total, usuario=request.user)
    return HttpResponse(status=204)
