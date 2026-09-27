import io
from django.http import FileResponse, Http404
from application.relatorios.selectors import montar_relatorio
from infrastructure.utils.relatorios_export import TIPOS_DE_RELATORIO, gerar_relatorio_excel, gerar_relatorio_pdf
from interfaces.decorators import loja_required
from interfaces.desenvolvedor import CORSARIOS_CODE
from interfaces.forms import PeriodoForm

FORMATOS = {
    'pdf': (gerar_relatorio_pdf, 'application/pdf', 'pdf'),
    'excel': (gerar_relatorio_excel, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'),
}


@loja_required
def exportar_pdf_modular_view(request, tipo):
    return _exportar(request, tipo, 'pdf')


@loja_required
def exportar_excel_modular_view(request, tipo):
    return _exportar(request, tipo, 'excel')


def _exportar(request, tipo, formato):
    tipo = tipo.strip().lower()
    if tipo not in TIPOS_DE_RELATORIO:
        raise Http404("Seção de relatório inválida.")

    gerar, content_type, extensao = FORMATOS[formato]
    inicio, fim = PeriodoForm(request.GET).intervalo()
    arquivo = io.BytesIO()
    relatorio = montar_relatorio(request.user, inicio, fim)
    if formato == 'pdf':
        gerar(tipo, relatorio, arquivo, loja=request.user.loja, assinatura=CORSARIOS_CODE.assinatura)
    else:
        gerar(tipo, relatorio, arquivo)
    arquivo.seek(0)
    return FileResponse(arquivo, content_type=content_type, as_attachment=True, filename=f"relatorio_{tipo}.{extensao}")
