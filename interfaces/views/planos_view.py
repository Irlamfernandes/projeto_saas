"""Renovar o plano: escolher, gerar o Pix e acompanhar até o Mercado Pago confirmar.

Estas telas funcionam mesmo com o plano vencido (é justamente quando mais se precisa delas).
"""
from django.conf import settings
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from application.assinatura.selectors import cobrancas_da_loja, planos_disponiveis
from application.assinatura.services import conferir_cobranca, conferir_pendentes, gerar_cobranca
from application.assinatura.tempo import novo_vencimento
from application.exceptions import RegraDeNegocioError
from infrastructure.models import StatusDaCobranca
from interfaces.decorators import loja_required
from interfaces.forms import RenovarPlanoForm
from interfaces.views.comum import primeiro_erro

TEMPLATE_PLANOS = 'interfaces/planos.html'
TEMPLATE_COBRANCA = 'interfaces/cobranca.html'


@loja_required(trava_plano_vencido=False)
def planos_view(request):
    loja = _loja_do_usuario(request)
    if request.method != 'POST':
        return render(request, TEMPLATE_PLANOS, {
            'opcoes': _opcoes_com_novo_vencimento(loja),
            'email': loja.email_cobranca,
        })

    form = RenovarPlanoForm(request.POST)
    if not form.is_valid():
        messages.error(request, primeiro_erro(form))
        return redirect('planos')
    try:
        cobranca = gerar_cobranca(
            loja, form.cleaned_data['plano'], email=form.cleaned_data['email'], usuario=request.user,
        )
    except RegraDeNegocioError as erro:
        messages.error(request, str(erro))
        return redirect('planos')
    return redirect('cobranca', pk=cobranca.pk)


@loja_required(trava_plano_vencido=False)
def cobranca_view(request, pk):
    cobranca = conferir_cobranca(_cobranca_da_loja(request, pk))
    request.user.loja.refresh_from_db(fields=['vencimento'])  # a confirmação acabou de mudar o vencimento
    return render(request, TEMPLATE_COBRANCA, {
        'cobranca': cobranca,
        'pix_de_teste': settings.MERCADO_PAGO_ACCESS_TOKEN.startswith('TEST-'),
    })


@loja_required(trava_plano_vencido=False)
def cobranca_situacao_view(request, pk):
    """Consultada pela tela do Pix a cada poucos segundos até o pagamento ser confirmado."""
    cobranca = conferir_cobranca(_cobranca_da_loja(request, pk))
    return JsonResponse({'status': cobranca.status})


def conferir_pix_abertos(request):
    """Confirma Pix pagos com a tela fechada e devolve os que continuam aguardando pagamento."""
    loja = request.user.loja
    if loja is None:
        return []
    conferidas = conferir_pendentes(loja)
    if conferidas:
        loja.refresh_from_db(fields=['vencimento'])
    return [cobranca for cobranca in conferidas if cobranca.status == StatusDaCobranca.PENDENTE]


def _loja_do_usuario(request):
    if request.user.loja is None:
        raise Http404("Só lojas têm plano.")
    return request.user.loja


def _cobranca_da_loja(request, pk):
    return get_object_or_404(cobrancas_da_loja(_loja_do_usuario(request)), pk=pk)


def _opcoes_com_novo_vencimento(loja):
    hoje = timezone.localdate()
    return [
        (plano, novo_vencimento(loja.vencimento, hoje, plano.quantidade, plano.unidade))
        for plano in planos_disponiveis()
    ]
