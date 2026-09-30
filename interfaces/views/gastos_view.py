"""Gastos e resultado do mês: lançar compras, despesas e perdas, e ver quanto sobrou."""
from dataclasses import dataclass
from collections.abc import Callable
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from application.exceptions import RegraDeNegocioError
from application.gastos import services
from application.gastos.selectors import (
    categorias_usadas, compras_do_mes, despesas_do_mes, mes_escolhido, meses_para_escolher, perdas_do_mes,
    resultado_do_mes,
)
from application.produtos.selectors import produtos_do_usuario
from application.relatorios.periodos import hoje_local
from application.tenancy import filtrar_por_loja
from infrastructure.models import Compra, Despesa, Perda
from interfaces.decorators import loja_required
from interfaces.forms import CompraForm, DespesaForm, PerdaForm
from interfaces.forms.gastos_form import MOTIVOS_SUGERIDOS
from interfaces.views.comum import executar_formulario

TEMPLATE_GASTOS = 'interfaces/gastos.html'
ABA_PADRAO = 'despesa'
ABAS = (('despesa', 'Despesa'), ('compra', 'Compra'), ('perda', 'Perda'))
SEM_LOJA = "Entre com um usuário de loja para lançar gastos."


@dataclass(frozen=True)
class TipoDeGasto:
    modelo: type
    formulario: Callable
    registrar: Callable
    excluir: Callable
    registrado: str
    excluido: str


TIPOS = {
    'despesa': TipoDeGasto(Despesa, lambda request: DespesaForm(request.POST), services.registrar_despesa,
                           services.excluir_despesa, "Despesa lançada!", "Despesa excluída."),
    'compra': TipoDeGasto(Compra, lambda request: CompraForm(request.POST), services.registrar_compra,
                          services.excluir_compra, "Compra lançada! O estoque foi atualizado.",
                          "Compra excluída. O estoque foi corrigido."),
    'perda': TipoDeGasto(Perda, lambda request: PerdaForm(request.POST, produtos=produtos_do_usuario(request.user)),
                         services.registrar_perda, services.excluir_perda, "Perda lançada. O estoque foi baixado.",
                         "Perda excluída. O estoque foi devolvido."),
}


@loja_required
def gastos_view(request):
    hoje = hoje_local()
    mes = mes_escolhido(request.GET.get('mes'), hoje)
    aba = request.GET.get('aba') if request.GET.get('aba') in TIPOS else ABA_PADRAO
    user = request.user
    context = {
        'mes': mes,
        'meses': meses_para_escolher(hoje),
        'aba': aba,
        'abas': ABAS,
        'hoje': hoje,
        'resultado': resultado_do_mes(user, mes),
        'despesas': despesas_do_mes(user, mes),
        'compras': compras_do_mes(user, mes),
        'perdas': perdas_do_mes(user, mes),
        'produtos': produtos_do_usuario(user).order_by('nome'),
        'categorias': categorias_usadas(user),
        'motivos': MOTIVOS_SUGERIDOS,
    }
    return render(request, TEMPLATE_GASTOS, context)


@loja_required
@require_POST
def registrar_gasto_view(request, tipo):
    gasto = _tipo(tipo)
    loja = request.user.loja
    if loja is None:
        messages.error(request, SEM_LOJA)
        return redirect(_voltar(tipo))
    form = gasto.formulario(request)
    salvou = executar_formulario(
        request, form,
        acao=lambda: gasto.registrar(loja=loja, **form.parametros(), usuario=request.user),
        mensagem_sucesso=gasto.registrado,
    )
    return redirect(_voltar(tipo, form.cleaned_data['data'] if salvou else None))


@loja_required
@require_POST
def excluir_gasto_view(request, tipo, pk):
    gasto = _tipo(tipo)
    registro = get_object_or_404(filtrar_por_loja(gasto.modelo.objects.all(), request.user), pk=pk)
    data = registro.data
    try:
        gasto.excluir(registro, usuario=request.user)
    except RegraDeNegocioError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, gasto.excluido)
    return redirect(_voltar(tipo, data))


def _tipo(tipo):
    if tipo not in TIPOS:
        raise Http404
    return TIPOS[tipo]


def _voltar(tipo, data=None):
    """Volta para a aba do tipo lançado, no mês do lançamento."""
    mes = f"&mes={data:%Y-%m}" if data else ''
    return f"{reverse('gastos')}?aba={tipo}{mes}"
