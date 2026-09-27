from django.db import transaction
from application.auditoria.services import registrar_alteracao
from infrastructure.models import Acao, LembreteDePagamento
from infrastructure.utils.formatacao import reais


@transaction.atomic
def registrar_lembrete(cliente, *, valor, usuario=None):
    """Anota que o lembrete foi enviado (o envio em si é o dono tocando em enviar no WhatsApp)."""
    lembrete = LembreteDePagamento.objects.create(loja=cliente.loja, cliente=cliente, usuario=usuario, valor=valor)
    registrar_alteracao(
        loja=cliente.loja, usuario=usuario, acao=Acao.LEMBRETE_ENVIADO,
        descricao=f"{cliente.nome} · {reais(valor)}",
    )
    return lembrete
