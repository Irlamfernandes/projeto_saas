from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from application.assinatura.selectors import em_teste_gratis
from application.exceptions import RegraDeNegocioError
from application.lojas.services import remover_marca, trocar_marca
from interfaces.decorators import loja_required
from interfaces.desenvolvedor import CORSARIOS_CODE
from interfaces.forms import MarcaForm
from interfaces.forms.produto_form import TAMANHO_MAXIMO_MB
from interfaces.views.comum import executar_formulario
from interfaces.views.planos_view import conferir_pix_abertos

TEMPLATE_CONFIGURACOES = 'interfaces/configuracoes.html'


@loja_required(trava_plano_vencido=False)
def configuracoes_view(request):
    pix_aguardando = conferir_pix_abertos(request)
    loja = request.user.loja
    return render(request, TEMPLATE_CONFIGURACOES, {
        'tamanho_maximo_mb': TAMANHO_MAXIMO_MB,
        'em_teste_gratis': loja is not None and em_teste_gratis(loja),
        'pix_aguardando': pix_aguardando,
        'link_suporte': CORSARIOS_CODE.link_suporte(loja.nome_loja if loja else 'Painel global'),
    })


@require_POST
@loja_required(trava_plano_vencido=False)
def marca_enviar_view(request):
    form = MarcaForm(request.POST, request.FILES)
    executar_formulario(
        request, form,
        acao=lambda: trocar_marca(request.user.loja, form.cleaned_data['marca'], usuario=request.user),
        mensagem_sucesso="Marca atualizada! Ela já aparece no topo e nos PDFs.",
    )
    return redirect('configuracoes')


@require_POST
@loja_required(trava_plano_vencido=False)
def marca_remover_view(request):
    try:
        remover_marca(request.user.loja, usuario=request.user)
    except RegraDeNegocioError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Marca removida.")
    return redirect('configuracoes')
