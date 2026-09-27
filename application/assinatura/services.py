"""Renovação do plano por Pix.

Regra de ouro: o vencimento só avança depois de o próprio Mercado Pago dizer que o pagamento foi aprovado,
com o valor certo e a referência desta cobrança. Nada que chegue de fora é aceito sem essa consulta.
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from application.assinatura.exceptions import PagamentoIndisponivel, PixRecusado, PlanoIndisponivel
from application.assinatura.tempo import novo_vencimento
from application.auditoria.services import registrar_alteracao
from application.formatacao import reais
from infrastructure.models import Acao, Cobranca, LojaModel, StatusDaCobranca
from infrastructure.pagamentos.mercado_pago import MercadoPago, MercadoPagoError, MercadoPagoRecusou

logger = logging.getLogger(__name__)

MINUTOS_PARA_PAGAR = 30
# Um Pix aberto é reaproveitado se ainda sobrar tempo para pagar; senão, gera outro.
MINUTOS_MINIMOS_PARA_REAPROVEITAR = 5
# Depois de expirar, ainda espera um pouco antes de desistir (o Pix pode ter sido pago no último minuto).
MARGEM_APOS_EXPIRAR = timedelta(minutes=10)
STATUS_SEM_VOLTA = {'cancelled', 'rejected'}


@transaction.atomic
def gerar_cobranca(loja, plano, *, email, usuario, gateway=None):
    """Cria a cobrança e o Pix no Mercado Pago. Se o Mercado Pago falhar, nada fica salvo."""
    if not plano.ativo:
        raise PlanoIndisponivel()
    aberta = _cobranca_aberta(loja, plano, email)
    if aberta:
        return aberta

    cobranca = Cobranca.objects.create(
        loja=loja, plano=plano, usuario=usuario,
        plano_nome=plano.nome, quantidade=plano.quantidade, unidade=plano.unidade, valor=plano.preco,
        email_pagador=email, expira_em=timezone.now() + timedelta(minutes=MINUTOS_PARA_PAGAR),
    )
    pix = _criar_pix(gateway or MercadoPago.from_settings(), cobranca)
    cobranca.pagamento_id = pix.pagamento_id
    cobranca.pix_copia_e_cola = pix.copia_e_cola
    cobranca.pix_qr_code = pix.qr_code_base64
    cobranca.save(update_fields=['pagamento_id', 'pix_copia_e_cola', 'pix_qr_code'])

    loja.email_cobranca = email
    loja.save(update_fields=['email_cobranca'])
    return cobranca


def conferir_cobranca(cobranca, *, gateway=None):
    """Consulta o Mercado Pago e confirma a cobrança só se tudo bater. Pode ser chamada quantas vezes for."""
    if cobranca.status == StatusDaCobranca.PAGA or not cobranca.pagamento_id:
        return cobranca
    try:
        pagamento = (gateway or MercadoPago.from_settings()).consultar(cobranca.pagamento_id)
    except MercadoPagoError:
        logger.warning("Não deu para consultar a cobrança %s agora", cobranca.pk, exc_info=True)
        return cobranca

    if pagamento.aprovado:
        if _confere(cobranca, pagamento):
            return _confirmar(cobranca.pk)
        logger.error(
            "Pagamento %s aprovado não confere com a cobrança %s (valor %s, moeda %s, referência %s)",
            pagamento.pagamento_id, cobranca.pk, pagamento.valor, pagamento.moeda, pagamento.referencia,
        )
        return cobranca
    if pagamento.status in STATUS_SEM_VOLTA or timezone.now() > cobranca.expira_em + MARGEM_APOS_EXPIRAR:
        Cobranca.objects.filter(pk=cobranca.pk, status=StatusDaCobranca.PENDENTE).update(status=StatusDaCobranca.EXPIRADA)
        cobranca.refresh_from_db()
    return cobranca


def _cobranca_aberta(loja, plano, email):
    minimo = timezone.now() + timedelta(minutes=MINUTOS_MINIMOS_PARA_REAPROVEITAR)
    return (
        Cobranca.objects
        .filter(loja=loja, plano=plano, valor=plano.preco, email_pagador=email,
                status=StatusDaCobranca.PENDENTE, expira_em__gt=minimo)
        .exclude(pagamento_id='')
        .first()
    )


def _criar_pix(gateway, cobranca):
    try:
        return gateway.criar_pix(
            valor=cobranca.valor,
            descricao=f"Plano {cobranca.plano_nome} - {cobranca.loja.nome_loja}",
            email=cobranca.email_pagador,
            referencia=str(cobranca.referencia),
            expira_em=timezone.localtime(cobranca.expira_em),
        )
    except MercadoPagoRecusou as erro:
        raise PixRecusado(str(erro)) from erro
    except MercadoPagoError as erro:
        logger.exception("Falha ao gerar o Pix da cobrança da loja %s", cobranca.loja_id)
        raise PagamentoIndisponivel() from erro


def _confere(cobranca, pagamento):
    return (
        pagamento.pagamento_id == cobranca.pagamento_id
        and pagamento.referencia == str(cobranca.referencia)
        and pagamento.valor == cobranca.valor
        and pagamento.moeda == 'BRL'
    )


@transaction.atomic
def _confirmar(cobranca_id):
    """Trava a cobrança e a loja: duas conferências ao mesmo tempo não somam o tempo duas vezes."""
    cobranca = Cobranca.objects.select_for_update().get(pk=cobranca_id)
    if cobranca.status == StatusDaCobranca.PAGA:
        return cobranca
    loja = LojaModel.objects.select_for_update().get(pk=cobranca.loja_id)

    anterior = loja.vencimento
    loja.vencimento = novo_vencimento(anterior, timezone.localdate(), cobranca.quantidade, cobranca.unidade)
    loja.save(update_fields=['vencimento'])

    cobranca.status = StatusDaCobranca.PAGA
    cobranca.paga_em = timezone.now()
    cobranca.vencimento_anterior = anterior
    cobranca.vencimento_novo = loja.vencimento
    cobranca.save(update_fields=['status', 'paga_em', 'vencimento_anterior', 'vencimento_novo'])

    registrar_alteracao(
        loja=loja, usuario=cobranca.usuario, acao=Acao.PLANO_RENOVADO,
        descricao=f"Plano {cobranca.plano_nome} · {reais(cobranca.valor)} · até {loja.vencimento:%d/%m/%Y}",
        detalhes={
            'vencimento': [anterior.isoformat(), loja.vencimento.isoformat()],
            'pagamento_id': cobranca.pagamento_id,
        },
    )
    return cobranca
